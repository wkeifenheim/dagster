from collections import namedtuple
from enum import Enum

from dagster import check
from dagster.core.definitions.run_request import InstigatorType
from dagster.core.host_representation.origin import ExternalJobOrigin
from dagster.serdes.serdes import (
    register_serdes_enum_fallbacks,
    register_serdes_tuple_fallbacks,
    whitelist_for_serdes,
)
from dagster.utils import merge_dicts
from dagster.utils.error import SerializableErrorInfo


@whitelist_for_serdes
class InstigatorStatus(Enum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"


register_serdes_enum_fallbacks({"JobStatus": InstigatorStatus})
# for internal backcompat
JobStatus = InstigatorStatus


@whitelist_for_serdes
class SensorInstigatorData(
    namedtuple("_SensorInstigatorData", "last_tick_timestamp last_run_key min_interval cursor")
):
    def __new__(cls, last_tick_timestamp=None, last_run_key=None, min_interval=None, cursor=None):
        return super(SensorInstigatorData, cls).__new__(
            cls,
            check.opt_float_param(last_tick_timestamp, "last_tick_timestamp"),
            check.opt_str_param(last_run_key, "last_run_key"),
            check.opt_int_param(min_interval, "min_interval"),
            check.opt_str_param(cursor, "cursor"),
        )


register_serdes_tuple_fallbacks({"SensorJobData": SensorInstigatorData})
# for internal backcompat
SensorJobData = SensorInstigatorData


@whitelist_for_serdes
class ScheduleInstigatorData(
    namedtuple("_ScheduleInstigatorData", "cron_schedule start_timestamp")
):
    # removed scheduler, 1/5/2022 (0.13.13)
    def __new__(cls, cron_schedule, start_timestamp=None):
        return super(ScheduleInstigatorData, cls).__new__(
            cls,
            check.str_param(cron_schedule, "cron_schedule"),
            # Time in UTC at which the user started running the schedule (distinct from
            # `start_date` on partition-based schedules, which is used to define
            # the range of partitions)
            check.opt_float_param(start_timestamp, "start_timestamp"),
        )


register_serdes_tuple_fallbacks({"ScheduleJobData": ScheduleInstigatorData})
# for internal backcompat
ScheduleJobData = ScheduleInstigatorData


def check_job_data(job_type, job_specific_data):
    check.inst_param(job_type, "job_type", InstigatorType)
    if job_type == InstigatorType.SCHEDULE:
        check.inst_param(job_specific_data, "job_specific_data", ScheduleInstigatorData)
    elif job_type == InstigatorType.SENSOR:
        check.opt_inst_param(job_specific_data, "job_specific_data", SensorInstigatorData)
    else:
        check.failed(
            "Unexpected job type {}, expected one of InstigatorType.SENSOR, InstigatorType.SCHEDULE".format(
                job_type
            )
        )

    return job_specific_data


@whitelist_for_serdes
class InstigatorState(namedtuple("_InstigationState", "origin job_type status job_specific_data")):
    def __new__(cls, origin, job_type, status, job_specific_data=None):
        return super(InstigatorState, cls).__new__(
            cls,
            check.inst_param(origin, "origin", ExternalJobOrigin),
            check.inst_param(job_type, "job_type", InstigatorType),
            check.inst_param(status, "status", InstigatorStatus),
            check_job_data(job_type, job_specific_data),
        )

    @property
    def name(self):
        return self.origin.job_name

    @property
    def job_name(self):
        return self.origin.job_name

    @property
    def repository_origin_id(self):
        return self.origin.external_repository_origin.get_id()

    @property
    def job_origin_id(self):
        return self.origin.get_id()

    def with_status(self, status):
        check.inst_param(status, "status", InstigatorStatus)
        return InstigatorState(
            self.origin,
            job_type=self.job_type,
            status=status,
            job_specific_data=self.job_specific_data,
        )

    def with_data(self, job_specific_data):
        check_job_data(self.job_type, job_specific_data)
        return InstigatorState(
            self.origin,
            job_type=self.job_type,
            status=self.status,
            job_specific_data=job_specific_data,
        )


register_serdes_tuple_fallbacks({"JobState": InstigatorState})
# for internal backcompat
JobState = InstigatorState


@whitelist_for_serdes
class TickStatus(Enum):
    STARTED = "STARTED"
    SKIPPED = "SKIPPED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


register_serdes_enum_fallbacks({"JobTickStatus": TickStatus})
# for internal backcompat
JobTickStatus = TickStatus


@whitelist_for_serdes
class InstigatorTick(namedtuple("_InstigatorTick", "tick_id job_tick_data")):
    def __new__(cls, tick_id, job_tick_data):
        return super(InstigatorTick, cls).__new__(
            cls,
            check.int_param(tick_id, "tick_id"),
            check.inst_param(job_tick_data, "job_tick_data", TickData),
        )

    def with_status(self, status, **kwargs):
        check.inst_param(status, "status", TickStatus)
        return self._replace(job_tick_data=self.job_tick_data.with_status(status, **kwargs))

    def with_reason(self, skip_reason):
        check.opt_str_param(skip_reason, "skip_reason")
        return self._replace(job_tick_data=self.job_tick_data.with_reason(skip_reason))

    def with_run(self, run_id, run_key=None):
        return self._replace(job_tick_data=self.job_tick_data.with_run(run_id, run_key))

    def with_cursor(self, cursor):
        return self._replace(job_tick_data=self.job_tick_data.with_cursor(cursor))

    def with_origin_run(self, origin_run_id):
        return self._replace(job_tick_data=self.job_tick_data.with_origin_run(origin_run_id))

    @property
    def job_origin_id(self):
        return self.job_tick_data.job_origin_id

    @property
    def job_name(self):
        return self.job_tick_data.job_name

    @property
    def job_type(self):
        return self.job_tick_data.job_type

    @property
    def timestamp(self):
        return self.job_tick_data.timestamp

    @property
    def status(self):
        return self.job_tick_data.status

    @property
    def run_ids(self):
        return self.job_tick_data.run_ids

    @property
    def run_keys(self):
        return self.job_tick_data.run_keys

    @property
    def error(self):
        return self.job_tick_data.error

    @property
    def skip_reason(self):
        return self.job_tick_data.skip_reason

    @property
    def cursor(self):
        return self.job_tick_data.cursor

    @property
    def origin_run_ids(self):
        return self.job_tick_data.origin_run_ids

    @property
    def failure_count(self) -> int:
        return self.job_tick_data.failure_count


register_serdes_tuple_fallbacks({"JobTick": InstigatorTick})
# for internal backcompat
JobTick = InstigatorTick


@whitelist_for_serdes
class TickData(
    namedtuple(
        "_TickData",
        "job_origin_id job_name job_type status timestamp run_ids run_keys error skip_reason cursor origin_run_ids failure_count",
    )
):
    def __new__(
        cls,
        job_origin_id,
        job_name,
        job_type,
        status,
        timestamp,
        run_ids=None,
        run_keys=None,
        error=None,
        skip_reason=None,
        cursor=None,
        origin_run_ids=None,
        failure_count=None,
    ):
        """
        This class defines the data that is serialized and stored in ``JobStorage``. We depend
        on the job storage implementation to provide job tick ids, and therefore
        separate all other data into this serializable class that can be stored independently of the
        id

        Arguments:
            job_origin_id (str): The id of the job target for this tick
            job_name (str): The name of the job for this tick
            job_type (InstigatorType): The type of this job for this tick
            status (TickStatus): The status of the tick, which can be updated
            timestamp (float): The timestamp at which this job evaluation started

        Keyword Arguments:
            run_id (str): The run created by the tick.
            error (SerializableErrorInfo): The error caught during job execution. This is set
                only when the status is ``TickStatus.Failure``
            skip_reason (str): message for why the tick was skipped
            origin_run_ids (List[str]): The runs originating the job.
            failure_count (int): The number of times this tick has failed. If the status is not
                FAILED, this is the number of previous failures before it reached the current state.
        """
        _validate_job_tick_args(job_type, status, run_ids, error, skip_reason)
        return super(TickData, cls).__new__(
            cls,
            check.str_param(job_origin_id, "job_origin_id"),
            check.str_param(job_name, "job_name"),
            check.inst_param(job_type, "job_type", InstigatorType),
            check.inst_param(status, "status", TickStatus),
            check.float_param(timestamp, "timestamp"),
            check.opt_list_param(run_ids, "run_ids", of_type=str),
            check.opt_list_param(run_keys, "run_keys", of_type=str),
            error,  # validated in _validate_job_tick_args
            skip_reason,  # validated in _validate_job_tick_args
            cursor=check.opt_str_param(cursor, "cursor"),
            origin_run_ids=check.opt_list_param(origin_run_ids, "origin_run_ids", of_type=str),
            failure_count=check.opt_int_param(failure_count, "failure_count", 0),
        )

    def with_status(self, status, error=None, timestamp=None, failure_count=None):
        return TickData(
            **merge_dicts(
                self._asdict(),
                {
                    "status": status,
                    "error": error,
                    "timestamp": timestamp if timestamp is not None else self.timestamp,
                    "failure_count": (
                        failure_count if failure_count is not None else self.failure_count
                    ),
                },
            )
        )

    def with_run(self, run_id, run_key=None):
        check.str_param(run_id, "run_id")
        return TickData(
            **merge_dicts(
                self._asdict(),
                {
                    "run_ids": [*self.run_ids, run_id],
                    "run_keys": [*self.run_keys, run_key] if run_key else self.run_keys,
                },
            )
        )

    def with_failure_count(self, failure_count):
        return JobTickData(
            **merge_dicts(
                self._asdict(),
                {
                    "failure_count": failure_count,
                },
            )
        )

    def with_reason(self, skip_reason):
        return TickData(
            **merge_dicts(
                self._asdict(), {"skip_reason": check.opt_str_param(skip_reason, "skip_reason")}
            )
        )

    def with_cursor(self, cursor):
        return TickData(
            **merge_dicts(self._asdict(), {"cursor": check.opt_str_param(cursor, "cursor")})
        )

    def with_origin_run(self, origin_run_id):
        check.str_param(origin_run_id, "origin_run_id")
        return TickData(
            **merge_dicts(
                self._asdict(),
                {"origin_run_ids": [*self.origin_run_ids, origin_run_id]},
            )
        )


register_serdes_tuple_fallbacks({"JobTickData": TickData})
# for internal backcompat
JobTickData = TickData


def _validate_job_tick_args(job_type, status, run_ids=None, error=None, skip_reason=None):
    check.inst_param(job_type, "job_type", InstigatorType)
    check.inst_param(status, "status", TickStatus)

    if status == TickStatus.SUCCESS:
        check.list_param(run_ids, "run_ids", of_type=str)
        check.invariant(error is None, desc="Job tick status is SUCCESS, but error was provided")
    elif status == TickStatus.FAILURE:
        check.inst_param(error, "error", SerializableErrorInfo)
    else:
        check.invariant(error is None, "Job tick status was not FAILURE but error was provided")

    if skip_reason:
        check.invariant(
            status == TickStatus.SKIPPED,
            "Job tick status was not SKIPPED but skip_reason was provided",
        )


class TickStatsSnapshot(
    namedtuple(
        "TickStatsSnapshot",
        ("ticks_started ticks_succeeded ticks_skipped ticks_failed"),
    )
):
    def __new__(
        cls,
        ticks_started,
        ticks_succeeded,
        ticks_skipped,
        ticks_failed,
    ):
        return super(TickStatsSnapshot, cls).__new__(
            cls,
            ticks_started=check.int_param(ticks_started, "ticks_started"),
            ticks_succeeded=check.int_param(ticks_succeeded, "ticks_succeeded"),
            ticks_skipped=check.int_param(ticks_skipped, "ticks_skipped"),
            ticks_failed=check.int_param(ticks_failed, "ticks_failed"),
        )


# for internal backcompat
JobTickStatsSnapshot = TickStatsSnapshot
