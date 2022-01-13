import pendulum
import pytest
from dagster.core.definitions.run_request import InstigatorType
from dagster.core.instance import DagsterInstance
from dagster.core.scheduler.instigation import InstigatorState, InstigatorStatus, TickStatus
from dagster.core.storage.pipeline_run import PipelineRunStatus
from dagster.core.storage.tags import RUN_KEY_TAG, SENSOR_NAME_TAG
from dagster.core.test_utils import (
    cleanup_test_instance,
    create_test_daemon_workspace,
    get_crash_signals,
    get_logger_output_from_capfd,
)
from dagster.daemon import get_default_daemon_logger
from dagster.daemon.sensor import execute_sensor_iteration
from dagster.seven import IS_WINDOWS, multiprocessing
from dagster.seven.compat.pendulum import create_pendulum_time, to_timezone

from .test_sensor_run import instance_with_sensors, repos, wait_for_all_runs_to_start


def _test_launch_sensor_runs_in_subprocess(instance_ref, execution_datetime, debug_crash_flags):
    with DagsterInstance.from_ref(instance_ref) as instance:
        try:
            with pendulum.test(execution_datetime), create_test_daemon_workspace() as workspace:
                list(
                    execute_sensor_iteration(
                        instance,
                        get_default_daemon_logger("SensorDaemon"),
                        workspace,
                        debug_crash_flags=debug_crash_flags,
                    )
                )
        finally:
            cleanup_test_instance(instance)


@pytest.mark.skipif(
    IS_WINDOWS, reason="Windows keeps resources open after termination in a flaky way"
)
@pytest.mark.parametrize("external_repo_context", repos())
@pytest.mark.parametrize("crash_location", ["TICK_CREATED", "TICK_HELD"])
@pytest.mark.parametrize("crash_signal", get_crash_signals())
def test_failure_before_run_created(external_repo_context, crash_location, crash_signal, capfd):
    frozen_datetime = to_timezone(
        create_pendulum_time(year=2019, month=2, day=28, hour=0, minute=0, second=1, tz="UTC"),
        "US/Central",
    )
    with instance_with_sensors(external_repo_context) as (
        instance,
        _grpc_server_registry,
        external_repo,
    ):
        with pendulum.test(frozen_datetime):
            external_sensor = external_repo.get_external_sensor("simple_sensor")
            instance.add_job_state(
                InstigatorState(
                    external_sensor.get_external_origin(),
                    InstigatorType.SENSOR,
                    InstigatorStatus.RUNNING,
                )
            )

            # create a tick
            launch_process = multiprocessing.Process(
                target=_test_launch_sensor_runs_in_subprocess,
                args=[instance.get_ref(), frozen_datetime, None],
            )
            launch_process.start()
            launch_process.join(timeout=60)
            ticks = instance.get_job_ticks(external_sensor.get_external_origin_id())
            assert len(ticks) == 1
            assert ticks[0].status == TickStatus.SKIPPED
            capfd.readouterr()

            # create a starting tick, but crash
            debug_crash_flags = {external_sensor.name: {crash_location: crash_signal}}
            launch_process = multiprocessing.Process(
                target=_test_launch_sensor_runs_in_subprocess,
                args=[instance.get_ref(), frozen_datetime.add(seconds=31), debug_crash_flags],
            )
            launch_process.start()
            launch_process.join(timeout=60)

            assert launch_process.exitcode != 0

            capfd.readouterr()

            ticks = instance.get_job_ticks(external_sensor.get_external_origin_id())
            assert len(ticks) == 2
            assert ticks[0].status == TickStatus.STARTED
            assert not int(ticks[0].timestamp) % 2  # skip condition for simple_sensor
            assert instance.get_runs_count() == 0

            # create another tick, but ensure that the last evaluation time used is from the first,
            # successful tick rather than the failed tick
            launch_process = multiprocessing.Process(
                target=_test_launch_sensor_runs_in_subprocess,
                args=[instance.get_ref(), frozen_datetime.add(seconds=62), None],
            )
            launch_process.start()
            launch_process.join(timeout=60)

            assert launch_process.exitcode == 0
            wait_for_all_runs_to_start(instance)

            assert instance.get_runs_count() == 1
            run = instance.get_runs()[0]
            assert (
                get_logger_output_from_capfd(capfd, "dagster.daemon.SensorDaemon")
                == f"""2019-02-27 18:01:03 -0600 - dagster.daemon.SensorDaemon - INFO - Checking for new runs for sensor: simple_sensor
2019-02-27 18:01:03 -0600 - dagster.daemon.SensorDaemon - INFO - Launching run for simple_sensor
2019-02-27 18:01:03 -0600 - dagster.daemon.SensorDaemon - INFO - Completed launch of run {run.run_id} for simple_sensor"""
            )

            ticks = instance.get_job_ticks(external_sensor.get_external_origin_id())
            assert len(ticks) == 3
            assert ticks[0].status == TickStatus.SUCCESS


@pytest.mark.skipif(
    IS_WINDOWS, reason="Windows keeps resources open after termination in a flaky way"
)
@pytest.mark.parametrize("external_repo_context", repos())
@pytest.mark.parametrize("crash_location", ["RUN_CREATED"])
@pytest.mark.parametrize("crash_signal", get_crash_signals())
def test_failure_after_run_created_before_run_launched(
    external_repo_context, crash_location, crash_signal, capfd
):
    frozen_datetime = to_timezone(
        create_pendulum_time(year=2019, month=2, day=28, hour=0, minute=0, second=0, tz="UTC"),
        "US/Central",
    )
    with instance_with_sensors(external_repo_context) as (
        instance,
        _grpc_server_registry,
        external_repo,
    ):
        with pendulum.test(frozen_datetime):
            external_sensor = external_repo.get_external_sensor("run_key_sensor")
            instance.add_job_state(
                InstigatorState(
                    external_sensor.get_external_origin(),
                    InstigatorType.SENSOR,
                    InstigatorStatus.RUNNING,
                )
            )

            # create a starting tick, but crash
            debug_crash_flags = {external_sensor.name: {crash_location: crash_signal}}
            launch_process = multiprocessing.Process(
                target=_test_launch_sensor_runs_in_subprocess,
                args=[instance.get_ref(), frozen_datetime, debug_crash_flags],
            )
            launch_process.start()
            launch_process.join(timeout=60)

            assert launch_process.exitcode != 0

            ticks = instance.get_job_ticks(external_sensor.get_external_origin_id())

            assert len(ticks) == 1
            assert ticks[0].status == TickStatus.STARTED
            assert instance.get_runs_count() == 1

            run = instance.get_runs()[0]
            # Run was created, but hasn't launched yet
            assert run.status == PipelineRunStatus.NOT_STARTED
            assert run.tags.get(SENSOR_NAME_TAG) == "run_key_sensor"
            assert run.tags.get(RUN_KEY_TAG) == "only_once"

            # clear output
            capfd.readouterr()

            launch_process = multiprocessing.Process(
                target=_test_launch_sensor_runs_in_subprocess,
                args=[instance.get_ref(), frozen_datetime.add(seconds=1), None],
            )
            launch_process.start()
            launch_process.join(timeout=60)

            assert launch_process.exitcode == 0
            wait_for_all_runs_to_start(instance)

            assert instance.get_runs_count() == 1
            run = instance.get_runs()[0]
            captured = capfd.readouterr()

            assert (
                f"Run {run.run_id} already created with the run key `only_once` for run_key_sensor"
                in captured.out
            )

            ticks = instance.get_job_ticks(external_sensor.get_external_origin_id())
            assert len(ticks) == 2
            assert ticks[0].status == TickStatus.SUCCESS


@pytest.mark.skipif(
    IS_WINDOWS, reason="Windows keeps resources open after termination in a flaky way"
)
@pytest.mark.parametrize("external_repo_context", repos())
@pytest.mark.parametrize("crash_location", ["RUN_LAUNCHED"])
@pytest.mark.parametrize("crash_signal", get_crash_signals())
def test_failure_after_run_launched(external_repo_context, crash_location, crash_signal, capfd):
    frozen_datetime = to_timezone(
        create_pendulum_time(
            year=2019,
            month=2,
            day=28,
            hour=0,
            minute=0,
            second=0,
            tz="UTC",
        ),
        "US/Central",
    )
    with instance_with_sensors(external_repo_context) as (
        instance,
        _grpc_server_registry,
        external_repo,
    ):
        with pendulum.test(frozen_datetime):
            external_sensor = external_repo.get_external_sensor("run_key_sensor")
            instance.add_job_state(
                InstigatorState(
                    external_sensor.get_external_origin(),
                    InstigatorType.SENSOR,
                    InstigatorStatus.RUNNING,
                )
            )

            # create a run, launch but crash
            debug_crash_flags = {external_sensor.name: {crash_location: crash_signal}}
            launch_process = multiprocessing.Process(
                target=_test_launch_sensor_runs_in_subprocess,
                args=[instance.get_ref(), frozen_datetime, debug_crash_flags],
            )
            launch_process.start()
            launch_process.join(timeout=60)

            assert launch_process.exitcode != 0

            ticks = instance.get_job_ticks(external_sensor.get_external_origin_id())

            assert len(ticks) == 1
            assert ticks[0].status == TickStatus.STARTED
            assert instance.get_runs_count() == 1

            run = instance.get_runs()[0]
            wait_for_all_runs_to_start(instance)
            assert run.tags.get(SENSOR_NAME_TAG) == "run_key_sensor"
            assert run.tags.get(RUN_KEY_TAG) == "only_once"
            capfd.readouterr()

            launch_process = multiprocessing.Process(
                target=_test_launch_sensor_runs_in_subprocess,
                args=[instance.get_ref(), frozen_datetime.add(seconds=1), None],
            )
            launch_process.start()
            launch_process.join(timeout=60)

            assert launch_process.exitcode == 0
            wait_for_all_runs_to_start(instance)

            assert instance.get_runs_count() == 1
            run = instance.get_runs()[0]
            captured = capfd.readouterr()

            assert (
                'Skipping 1 run for sensor run_key_sensor already completed with run keys: ["only_once"]'
                in captured.out
            )

            ticks = instance.get_job_ticks(external_sensor.get_external_origin_id())
            assert len(ticks) == 2
            assert ticks[0].status == TickStatus.SKIPPED
