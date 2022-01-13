import abc
import os
from collections import namedtuple

from dagster import check
from dagster.config import Field
from dagster.config.source import IntSource
from dagster.core.definitions.run_request import InstigatorType
from dagster.core.errors import DagsterError
from dagster.core.host_representation import ExternalSchedule
from dagster.core.instance import DagsterInstance
from dagster.core.scheduler.instigation import (
    InstigatorState,
    InstigatorStatus,
    ScheduleInstigatorData,
)
from dagster.serdes import ConfigurableClass
from dagster.seven import get_current_datetime_in_utc
from dagster.utils import mkdir_p


class DagsterSchedulerError(DagsterError):
    """Base class for all Dagster Scheduler errors"""


class DagsterScheduleDoesNotExist(DagsterSchedulerError):
    """Errors raised when ending a job for a schedule."""


class SchedulerDebugInfo(
    namedtuple("SchedulerDebugInfo", "errors scheduler_config_info scheduler_info schedule_storage")
):
    def __new__(cls, errors, scheduler_config_info, scheduler_info, schedule_storage):
        return super(SchedulerDebugInfo, cls).__new__(
            cls,
            errors=check.list_param(errors, "errors", of_type=str),
            scheduler_config_info=check.str_param(scheduler_config_info, "scheduler_config_info"),
            scheduler_info=check.str_param(scheduler_info, "scheduler_info"),
            schedule_storage=check.list_param(schedule_storage, "schedule_storage", of_type=str),
        )


class Scheduler(abc.ABC):
    """Abstract base class for a scheduler. This component is responsible for interfacing with
    an external system such as cron to ensure scheduled repeated execution according.
    """

    def _get_schedule_state(self, instance, external_origin_id):
        schedule_state = instance.get_job_state(external_origin_id)
        if not schedule_state:
            raise DagsterScheduleDoesNotExist(
                "You have attempted to start the job for schedule id {id}, but its state is not in storage.".format(
                    id=external_origin_id
                )
            )

        return schedule_state

    def _create_new_schedule_state(self, instance, external_schedule):
        schedule_state = InstigatorState(
            external_schedule.get_external_origin(),
            InstigatorType.SCHEDULE,
            InstigatorStatus.STOPPED,
            ScheduleInstigatorData(external_schedule.cron_schedule),
        )

        instance.add_job_state(schedule_state)
        return schedule_state

    def start_schedule_and_update_storage_state(self, instance, external_schedule):
        """
        Updates the status of the given schedule to `InstigatorStatus.RUNNING` in schedule storage,
        then calls `start_schedule`.

        This should not be overridden by subclasses.

        Args:
            instance (DagsterInstance): The current instance.
            external_schedule (ExternalSchedule): The schedule to start

        """

        check.inst_param(instance, "instance", DagsterInstance)
        check.inst_param(external_schedule, "external_schedule", ExternalSchedule)

        schedule_state = instance.get_job_state(external_schedule.get_external_origin_id())

        if not schedule_state:
            schedule_state = self._create_new_schedule_state(instance, external_schedule)

        if schedule_state.status == InstigatorStatus.RUNNING:
            raise DagsterSchedulerError(
                "You have attempted to start schedule {name}, but it is already running".format(
                    name=external_schedule.name
                )
            )

        self.start_schedule(instance, external_schedule)
        started_schedule = schedule_state.with_status(InstigatorStatus.RUNNING).with_data(
            ScheduleInstigatorData(
                external_schedule.cron_schedule,
                get_current_datetime_in_utc().timestamp(),
            )
        )
        instance.update_job_state(started_schedule)
        return started_schedule

    def stop_schedule_and_update_storage_state(self, instance, schedule_origin_id):
        """
        Updates the status of the given schedule to `InstigatorStatus.STOPPED` in schedule storage,
        then calls `stop_schedule`.

        This should not be overridden by subclasses.

        Args:
            schedule_origin_id (string): The id of the schedule target to stop running.
        """

        check.str_param(schedule_origin_id, "schedule_origin_id")

        schedule_state = self._get_schedule_state(instance, schedule_origin_id)

        self.stop_schedule(instance, schedule_origin_id)
        stopped_schedule = schedule_state.with_status(InstigatorStatus.STOPPED).with_data(
            ScheduleInstigatorData(
                cron_schedule=schedule_state.job_specific_data.cron_schedule,
            )
        )
        instance.update_job_state(stopped_schedule)
        return stopped_schedule

    def stop_schedule_and_delete_from_storage(self, instance, schedule_origin_id):
        """
        Deletes a schedule from schedule storage, then calls `stop_schedule`.

        This should not be overridden by subclasses.

        Args:
            instance (DagsterInstance): The current instance.
            schedule_origin_id (string): The id of the schedule target to start running.
        """

        check.inst_param(instance, "instance", DagsterInstance)
        check.str_param(schedule_origin_id, "schedule_origin_id")

        schedule = self._get_schedule_state(instance, schedule_origin_id)
        self.stop_schedule(instance, schedule_origin_id)
        instance.delete_job_state(schedule_origin_id)
        return schedule

    def refresh_schedule(self, instance, external_schedule):
        """Refresh a running schedule. This is called when user reconciles the schedule state.

        By default, this method will call stop_schedule and then start_schedule but can be
        overriden. For example, in the K8s Scheduler we patch the existing cronjob
        (without stopping it) to minimize downtime.

        Args:
            instance (DagsterInstance): The current instance.
            external_schedule (ExternalSchedule): The schedule to start running.
        """
        check.inst_param(instance, "instance", DagsterInstance)
        check.inst_param(external_schedule, "external_schedule", ExternalSchedule)

        self.stop_schedule(instance, external_schedule.get_external_origin_id())
        self.start_schedule(instance, external_schedule)

    @abc.abstractmethod
    def debug_info(self):
        """Returns debug information about the scheduler"""

    @abc.abstractmethod
    def start_schedule(self, instance, external_schedule):
        """Start running a schedule. This method is called by `start_schedule_and_update_storage_state`,
        which first updates the status of the schedule in schedule storage to `InstigatorStatus.RUNNING`,
        then calls this method.

        For example, in the cron scheduler, this method writes a cron job to the cron tab
        for the given schedule.

        Args:
            instance (DagsterInstance): The current instance.
            external_schedule (ExternalSchedule): The schedule to start running.
        """

    @abc.abstractmethod
    def stop_schedule(self, instance, schedule_origin_id):
        """Stop running a schedule.

        This method is called by
        1) `stop_schedule_and_update_storage_state`,
        which first updates the status of the schedule in schedule storage to `InstigatorStatus.STOPPED`,
        then calls this method.
        2) `stop_schedule_and_delete_from_storage`, which deletes the schedule from schedule storage
        then calls this method.

        For example, in the cron scheduler, this method deletes the cron job for a given scheduler
        from the cron tab.

        Args:
            instance (DagsterInstance): The current instance.
            schedule_origin_id (string): The id of the schedule target to stop running.
        """

    @abc.abstractmethod
    def running_schedule_count(self, instance, schedule_origin_id):
        """Returns the number of jobs currently running for the given schedule. This method is used
        for detecting when the scheduler is out of sync with schedule storage.

        For example, when:
        - There are duplicate jobs runnning for a single schedule
        - There are no jobs runnning for a schedule that is set to be running
        - There are still jobs running for a schedule that is set to be stopped

        When the scheduler and schedule storage are in sync, this method should return:
        - 1 when a schedule is set to be running
        - 0 when a schedule is set to be stopped

        Args:
            instance (DagsterInstance): The current instance.
            schedule_origin_id (string): The id of the schedule target to return the number of jobs for
        """

    @abc.abstractmethod
    def get_logs_path(self, instance, schedule_origin_id):
        """Get path to store logs for schedule

        Args:
            schedule_origin_id (string): The id of the schedule target to retrieve the log path for
        """


DEFAULT_MAX_CATCHUP_RUNS = 5


class DagsterDaemonScheduler(Scheduler, ConfigurableClass):
    """Default scheduler implementation that submits runs from the `dagster-daemon`
    long-lived process. Periodically checks each running schedule for execution times that don't
    have runs yet and launches them.

    Args:
        max_catchup_runs (int): For partitioned schedules, controls the maximum number of past
            partitions for each schedule that will be considered when looking for missing
            runs (defaults to 5). Generally this parameter will only come into play if the scheduler
            falls behind or launches after experiencing downtime. This parameter will not be checked for
            schedules without partition sets (for example, schedules created using the @schedule
            decorator) - only the most recent execution time will be considered for those schedules.

            Note that no matter what this value is, the scheduler will never launch a run from a time
            before the schedule was turned on (even if the start_date on the schedule is earlier) - if
            you want to launch runs for earlier partitions, launch a backfill.
        max_tick_retries (int): For each schedule tick that raises an error, how many times to retry
            that tick (defaults to 0).
    """

    def __init__(
        self, max_catchup_runs=DEFAULT_MAX_CATCHUP_RUNS, max_tick_retries=0, inst_data=None
    ):
        self.max_catchup_runs = check.opt_int_param(
            max_catchup_runs, "max_catchup_runs", DEFAULT_MAX_CATCHUP_RUNS
        )
        self.max_tick_retries = check.opt_int_param(max_tick_retries, "max_tick_retries", 0)
        self._inst_data = inst_data

    @property
    def inst_data(self):
        return self._inst_data

    @classmethod
    def config_type(cls):
        return {
            "max_catchup_runs": Field(IntSource, is_required=False),
            "max_tick_retries": Field(IntSource, is_required=False),
        }

    @staticmethod
    def from_config_value(inst_data, config_value):
        return DagsterDaemonScheduler(inst_data=inst_data, **config_value)

    def debug_info(self):
        return ""

    def start_schedule(self, instance, external_schedule):
        # Automatically picked up by the `dagster scheduler run` command
        pass

    def stop_schedule(self, instance, schedule_origin_id):
        # Automatically picked up by the `dagster scheduler run` command
        pass

    def running_schedule_count(self, instance, schedule_origin_id):
        state = instance.get_job_state(schedule_origin_id)
        if not state:
            return 0
        return 1 if state.status == InstigatorStatus.RUNNING else 0

    def wipe(self, instance):
        pass

    def _get_or_create_logs_directory(self, instance, schedule_origin_id):
        check.inst_param(instance, "instance", DagsterInstance)
        check.str_param(schedule_origin_id, "schedule_origin_id")

        logs_directory = os.path.join(instance.schedules_directory(), "logs", schedule_origin_id)
        if not os.path.isdir(logs_directory):
            mkdir_p(logs_directory)

        return logs_directory

    def get_logs_path(self, instance, schedule_origin_id):
        check.inst_param(instance, "instance", DagsterInstance)
        check.str_param(schedule_origin_id, "schedule_origin_id")

        logs_directory = self._get_or_create_logs_directory(instance, schedule_origin_id)
        return os.path.join(logs_directory, "scheduler.log")
