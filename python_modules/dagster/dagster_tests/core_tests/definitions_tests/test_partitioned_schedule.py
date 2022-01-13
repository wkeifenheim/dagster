from datetime import datetime

import pendulum
from dagster import build_schedule_context, graph, repository, solid
from dagster.core.definitions.partitioned_schedule import build_schedule_from_partitioned_job
from dagster.core.definitions.time_window_partitions import (
    TimeWindow,
    daily_partitioned_config,
    hourly_partitioned_config,
    monthly_partitioned_config,
    weekly_partitioned_config,
)

DATE_FORMAT = "%Y-%m-%d"


def time_window(start: str, end: str) -> TimeWindow:
    return TimeWindow(pendulum.parse(start), pendulum.parse(end))


def schedule_for_partitioned_config(
    partitioned_config, minute_of_hour=None, hour_of_day=None, day_of_week=None, day_of_month=None
):
    @solid
    def my_solid():
        pass

    @graph
    def my_graph():
        my_solid()

    return build_schedule_from_partitioned_job(
        my_graph.to_job(config=partitioned_config),
        minute_of_hour=minute_of_hour,
        hour_of_day=hour_of_day,
        day_of_week=day_of_week,
        day_of_month=day_of_month,
    )


def test_daily_schedule():
    @daily_partitioned_config(start_date="2021-05-05")
    def my_partitioned_config(start, end):
        return {"start": str(start), "end": str(end)}

    assert my_partitioned_config(datetime(2021, 5, 7), datetime(2021, 5, 8)) == {
        "start": "2021-05-07 00:00:00",
        "end": "2021-05-08 00:00:00",
    }

    my_schedule = schedule_for_partitioned_config(
        my_partitioned_config, hour_of_day=9, minute_of_hour=30
    )
    assert my_schedule.cron_schedule == "30 9 * * *"

    assert my_schedule.evaluate_tick(
        build_schedule_context(
            scheduled_execution_time=datetime.strptime("2021-05-08", DATE_FORMAT)
        )
    ).run_requests[0].run_config == {
        "start": "2021-05-07T00:00:00+00:00",
        "end": "2021-05-08T00:00:00+00:00",
    }

    @repository
    def _repo():
        return [my_schedule]


def test_hourly_schedule():
    @hourly_partitioned_config(start_date=datetime(2021, 5, 5))
    def my_partitioned_config(start, end):
        return {"start": str(start), "end": str(end)}

    assert my_partitioned_config(datetime(2021, 5, 7, 23), datetime(2021, 5, 8)) == {
        "start": "2021-05-07 23:00:00",
        "end": "2021-05-08 00:00:00",
    }

    my_schedule = schedule_for_partitioned_config(my_partitioned_config, minute_of_hour=30)
    assert my_schedule.cron_schedule == "30 * * * *"

    assert my_schedule.evaluate_tick(
        build_schedule_context(
            scheduled_execution_time=datetime.strptime("2021-05-08", DATE_FORMAT)
        )
    ).run_requests[0].run_config == {
        "start": "2021-05-07T23:00:00+00:00",
        "end": "2021-05-08T00:00:00+00:00",
    }

    @repository
    def _repo():
        return [my_schedule]


def test_weekly_schedule():
    @weekly_partitioned_config(start_date="2021-05-05")
    def my_partitioned_config(start, end):
        return {"start": str(start), "end": str(end)}

    assert my_partitioned_config(datetime(2021, 12, 13), datetime(2021, 12, 19)) == {
        "start": "2021-12-13 00:00:00",
        "end": "2021-12-19 00:00:00",
    }

    my_schedule = schedule_for_partitioned_config(
        my_partitioned_config, hour_of_day=9, minute_of_hour=30, day_of_week=2
    )
    assert my_schedule.cron_schedule == "30 9 * * 2"

    assert my_schedule.evaluate_tick(
        build_schedule_context(
            scheduled_execution_time=datetime.strptime("2021-05-21", DATE_FORMAT)
        )
    ).run_requests[0].run_config == {
        "start": "2021-05-09T00:00:00+00:00",
        "end": "2021-05-16T00:00:00+00:00",
    }

    @repository
    def _repo():
        return [my_schedule]


def test_monthly_schedule():
    @monthly_partitioned_config(start_date="2021-05-05")
    def my_partitioned_config(start, end):
        return {"start": str(start), "end": str(end)}

    assert my_partitioned_config(datetime(2021, 11, 1), datetime(2021, 11, 30)) == {
        "start": "2021-11-01 00:00:00",
        "end": "2021-11-30 00:00:00",
    }

    my_schedule = schedule_for_partitioned_config(
        my_partitioned_config, hour_of_day=9, minute_of_hour=30, day_of_month=2
    )
    assert my_schedule.cron_schedule == "30 9 2 * *"

    assert my_schedule.evaluate_tick(
        build_schedule_context(
            scheduled_execution_time=datetime.strptime("2021-07-21", DATE_FORMAT)
        )
    ).run_requests[0].run_config == {
        "start": "2021-06-01T00:00:00+00:00",
        "end": "2021-07-01T00:00:00+00:00",
    }

    @repository
    def _repo():
        return [my_schedule]
