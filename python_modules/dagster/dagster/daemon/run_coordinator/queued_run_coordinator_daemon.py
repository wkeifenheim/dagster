import logging
import sys
import time
from collections import defaultdict
from typing import Dict

from dagster import DagsterEvent, DagsterEventType, check
from dagster.core.events.log import EventLogEntry
from dagster.core.instance import DagsterInstance
from dagster.core.storage.pipeline_run import (
    IN_PROGRESS_RUN_STATUSES,
    PipelineRun,
    PipelineRunStatus,
    PipelineRunsFilter,
)
from dagster.core.storage.tags import PRIORITY_TAG
from dagster.core.workspace import IWorkspace
from dagster.daemon.daemon import IntervalDaemon
from dagster.utils.error import serializable_error_info_from_exc_info


class _TagConcurrencyLimitsCounter:
    """
    Helper object that keeps track of when the tag concurrency limits are met
    """

    def __init__(self, tag_concurrency_limits, in_progress_runs):
        check.opt_list_param(tag_concurrency_limits, "tag_concurrency_limits", of_type=dict)
        check.list_param(in_progress_runs, "in_progress_runs", of_type=PipelineRun)

        self._key_limits: Dict[str, int] = {}
        self._key_value_limits: Dict[(str, str), int] = {}
        self._unique_value_limits: Dict[str, int] = {}

        for tag_limit in tag_concurrency_limits:
            key = tag_limit["key"]
            value = tag_limit.get("value")
            limit = tag_limit["limit"]

            if isinstance(value, str):
                self._key_value_limits[(key, value)] = limit
            elif not value or not value["applyLimitPerUniqueValue"]:
                self._key_limits[key] = limit
            else:
                self._unique_value_limits[key] = limit

        self._key_counts: Dict[str, int] = defaultdict(lambda: 0)
        self._key_value_counts: Dict[(str, str), int] = defaultdict(lambda: 0)
        self._unique_value_counts: Dict[(str, str), int] = defaultdict(lambda: 0)

        # initialize counters based on current in progress runs
        for run in in_progress_runs:
            self.update_counters_with_launched_run(run)

    def is_run_blocked(self, run):
        """
        True if there are in progress runs which are blocking this run based on tag limits
        """
        for key, value in run.tags.items():
            if key in self._key_limits and self._key_counts[key] >= self._key_limits[key]:
                return True

            tag_tuple = (key, value)
            if (
                tag_tuple in self._key_value_limits
                and self._key_value_counts[tag_tuple] >= self._key_value_limits[tag_tuple]
            ):
                return True

            if (
                key in self._unique_value_limits
                and self._unique_value_counts[tag_tuple] >= self._unique_value_limits[key]
            ):
                return True

        return False

    def update_counters_with_launched_run(self, run):
        """
        Add a new in progress run to the counters
        """
        for key, value in run.tags.items():
            if key in self._key_limits:
                self._key_counts[key] += 1

            tag_tuple = (key, value)
            if tag_tuple in self._key_value_limits:
                self._key_value_counts[tag_tuple] += 1

            if key in self._unique_value_limits:
                self._unique_value_counts[tag_tuple] += 1


class QueuedRunCoordinatorDaemon(IntervalDaemon):
    """
    Used with the QueuedRunCoordinator on the instance. This process finds queued runs from the run
    store and launches them.
    """

    @classmethod
    def daemon_type(cls):
        return "QUEUED_RUN_COORDINATOR"

    def run_iteration(self, instance, workspace):
        check.inst_param(instance, "instance", DagsterInstance)
        check.inst_param(workspace, "workspace", IWorkspace)

        run_queue_config = instance.run_coordinator.get_run_queue_config()

        max_concurrent_runs = run_queue_config.max_concurrent_runs
        tag_concurrency_limits = run_queue_config.tag_concurrency_limits

        in_progress_runs = self._get_in_progress_runs(instance)
        max_runs_to_launch = max_concurrent_runs - len(in_progress_runs)

        # Possibly under 0 if runs were launched without queuing
        if max_runs_to_launch <= 0:
            self._logger.info(
                "{} runs are currently in progress. Maximum is {}, won't launch more.".format(
                    len(in_progress_runs), max_concurrent_runs
                )
            )
            return

        queued_runs = self._get_queued_runs(instance)

        if not queued_runs:
            self._logger.info("Poll returned no queued runs.")
        else:
            self._logger.info("Retrieved {} queued runs, checking limits.".format(len(queued_runs)))

        # place in order
        sorted_runs = self._priority_sort(queued_runs)

        # launch until blocked by limit rules
        num_dequeued_runs = 0
        tag_concurrency_limits_counter = _TagConcurrencyLimitsCounter(
            tag_concurrency_limits, in_progress_runs
        )

        for run in sorted_runs:
            if num_dequeued_runs >= max_runs_to_launch:
                break

            if tag_concurrency_limits_counter.is_run_blocked(run):
                continue

            error_info = None

            try:
                self._dequeue_run(instance, run, workspace)
            except Exception:
                error_info = serializable_error_info_from_exc_info(sys.exc_info())

                message = (
                    f"Caught an error for run {run.run_id} while removing it from the queue."
                    " Marking the run as failed and dropping it from the queue"
                )
                message_with_full_error = f"{message}: {error_info.to_string()}"

                self._logger.error(message_with_full_error)
                instance.report_run_failed(run, message_with_full_error)

                # modify the original error, so that the extra message appears in heartbeats
                error_info = error_info._replace(message=f"{message}: {error_info.message}")

            else:
                tag_concurrency_limits_counter.update_counters_with_launched_run(run)
                num_dequeued_runs += 1

            yield error_info

        self._logger.info("Launched {} runs.".format(num_dequeued_runs))

    def _get_queued_runs(self, instance):
        queued_runs_filter = PipelineRunsFilter(statuses=[PipelineRunStatus.QUEUED])

        # Reversed for fifo ordering
        # Note: should add a maximum fetch limit https://github.com/dagster-io/dagster/issues/3339
        runs = instance.get_runs(filters=queued_runs_filter)[::-1]
        return runs

    def _get_in_progress_runs(self, instance):
        # Note: should add a maximum fetch limit https://github.com/dagster-io/dagster/issues/3339
        return instance.get_runs(filters=PipelineRunsFilter(statuses=IN_PROGRESS_RUN_STATUSES))

    def _priority_sort(self, runs):
        def get_priority(run):
            priority_tag_value = run.tags.get(PRIORITY_TAG, "0")
            try:
                return int(priority_tag_value)
            except ValueError:
                return 0

        # sorted is stable, so fifo is maintained
        return sorted(runs, key=get_priority, reverse=True)

    def _dequeue_run(self, instance, run, workspace):
        # double check that the run is still queued before dequeing
        reloaded_run = instance.get_run_by_id(run.run_id)

        if reloaded_run.status != PipelineRunStatus.QUEUED:
            self._logger.info(
                "Run {run_id} is now {status} instead of QUEUED, skipping".format(
                    run_id=reloaded_run.run_id, status=reloaded_run.status
                )
            )
            return

        dequeued_event = DagsterEvent(
            event_type_value=DagsterEventType.PIPELINE_DEQUEUED.value,
            pipeline_name=run.pipeline_name,
        )
        event_record = EventLogEntry(
            message="",
            user_message="",
            level=logging.INFO,
            pipeline_name=run.pipeline_name,
            run_id=run.run_id,
            error_info=None,
            timestamp=time.time(),
            dagster_event=dequeued_event,
        )
        instance.handle_new_event(event_record)

        instance.launch_run(run.run_id, workspace)
