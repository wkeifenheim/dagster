import time

import pendulum
import pytest
from click.testing import CliRunner
from dagster.core.test_utils import instance_for_test
from dagster.daemon.cli import run_command
from dagster.daemon.controller import daemon_controller_from_instance
from dagster.daemon.daemon import SchedulerDaemon
from dagster.daemon.run_coordinator.queued_run_coordinator_daemon import QueuedRunCoordinatorDaemon


def test_scheduler_instance():
    with instance_for_test(
        overrides={
            "scheduler": {
                "module": "dagster.core.scheduler",
                "class": "DagsterDaemonScheduler",
            },
        }
    ) as instance:
        with daemon_controller_from_instance(instance) as controller:
            daemons = controller.daemons

            assert len(daemons) == 3

            assert any(isinstance(daemon, SchedulerDaemon) for daemon in daemons)


def test_run_coordinator_instance():
    with instance_for_test(
        overrides={
            "run_coordinator": {
                "module": "dagster.core.run_coordinator.queued_run_coordinator",
                "class": "QueuedRunCoordinator",
            },
        }
    ) as instance:
        with daemon_controller_from_instance(instance) as controller:
            daemons = controller.daemons

            assert len(daemons) == 4
            assert any(isinstance(daemon, QueuedRunCoordinatorDaemon) for daemon in daemons)


def _scheduler_ran(caplog):
    count = 0
    for log_tuple in caplog.record_tuples:
        logger_name, _level, text = log_tuple

        if (
            logger_name == "dagster.daemon.SchedulerDaemon"
            and "Not checking for any runs since no schedules have been started." in text
        ):
            count = count + 1

    return count


def _run_coordinator_ran(caplog):
    count = 0
    for log_tuple in caplog.record_tuples:
        logger_name, _level, text = log_tuple

        if (
            logger_name == "dagster.daemon.QueuedRunCoordinatorDaemon"
            and "Poll returned no queued runs." in text
        ):
            count = count + 1

    return count


def _sensor_ran(caplog):
    count = 0
    for log_tuple in caplog.record_tuples:
        logger_name, _level, text = log_tuple

        if (
            logger_name == "dagster.daemon.SensorDaemon"
            and "Not checking for any runs since no sensors have been started." in text
        ):
            count = count + 1

    return count


def test_ephemeral_instance():
    runner = CliRunner()
    with pytest.raises(Exception, match="DAGSTER_HOME is not set"):
        runner.invoke(run_command, env={"DAGSTER_HOME": ""}, catch_exceptions=False)


def test_different_intervals(caplog):
    with instance_for_test(
        overrides={
            "scheduler": {
                "module": "dagster.core.scheduler",
                "class": "DagsterDaemonScheduler",
            },
            "run_coordinator": {
                "module": "dagster.core.run_coordinator.queued_run_coordinator",
                "class": "QueuedRunCoordinator",
                "config": {"dequeue_interval_seconds": 5},
            },
        }
    ) as instance:
        init_time = pendulum.now("UTC")
        with daemon_controller_from_instance(instance):
            while True:
                now = pendulum.now("UTC")
                # Wait until the run coordinator has run three times
                # Scheduler has only run once
                if _run_coordinator_ran(caplog) == 3:
                    assert _scheduler_ran(caplog) == 1
                    break

                if (now - init_time).total_seconds() > 45:
                    raise Exception("Timed out waiting for run queue daemon to execute twice")

                time.sleep(0.5)

            init_time = pendulum.now("UTC")
