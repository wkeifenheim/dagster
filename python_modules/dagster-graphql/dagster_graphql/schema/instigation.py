import sys

import graphene
import pendulum
import yaml
from dagster import check
from dagster.core.definitions.schedule_definition import ScheduleExecutionData
from dagster.core.definitions.sensor_definition import RunRequest
from dagster.core.scheduler.instigation import (
    InstigatorState,
    InstigatorStatus,
    InstigatorTick,
    InstigatorType,
    ScheduleInstigatorData,
    SensorInstigatorData,
)
from dagster.core.storage.pipeline_run import PipelineRunsFilter
from dagster.core.storage.tags import TagType, get_tag_type
from dagster.seven.compat.pendulum import to_timezone
from dagster.utils.error import SerializableErrorInfo, serializable_error_info_from_exc_info

from ..implementation.fetch_schedules import get_schedule_next_tick
from ..implementation.fetch_sensors import get_sensor_next_tick
from .errors import GraphenePythonError
from .repository_origin import GrapheneRepositoryOrigin
from .tags import GraphenePipelineTag
from .util import non_null_list


class GrapheneInstigationType(graphene.Enum):
    SCHEDULE = "SCHEDULE"
    SENSOR = "SENSOR"

    class Meta:
        name = "InstigationType"


class GrapheneInstigationStatus(graphene.Enum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"

    class Meta:
        name = "InstigationStatus"


class GrapheneInstigationTickStatus(graphene.Enum):
    STARTED = "STARTED"
    SKIPPED = "SKIPPED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"

    class Meta:
        name = "InstigationTickStatus"


class GrapheneSensorData(graphene.ObjectType):
    lastTickTimestamp = graphene.Float()
    lastRunKey = graphene.String()

    class Meta:
        name = "SensorData"

    def __init__(self, job_specific_data):
        check.inst_param(job_specific_data, "job_specific_data", SensorInstigatorData)
        super().__init__(
            lastTickTimestamp=job_specific_data.last_tick_timestamp,
            lastRunKey=job_specific_data.last_run_key,
        )


class GrapheneScheduleData(graphene.ObjectType):
    cronSchedule = graphene.NonNull(graphene.String)
    startTimestamp = graphene.Float()

    class Meta:
        name = "ScheduleData"

    def __init__(self, job_specific_data):
        check.inst_param(job_specific_data, "job_specific_data", ScheduleInstigatorData)
        super().__init__(
            cronSchedule=job_specific_data.cron_schedule,
            startTimestamp=job_specific_data.start_timestamp,
        )


class GrapheneInstigationTypeSpecificData(graphene.Union):
    class Meta:
        types = (GrapheneSensorData, GrapheneScheduleData)
        name = "InstigationTypeSpecificData"


class GrapheneInstigationTick(graphene.ObjectType):
    id = graphene.NonNull(graphene.ID)
    status = graphene.NonNull(GrapheneInstigationTickStatus)
    timestamp = graphene.NonNull(graphene.Float)
    runIds = non_null_list(graphene.String)
    error = graphene.Field(GraphenePythonError)
    skipReason = graphene.String()
    runs = non_null_list("dagster_graphql.schema.pipelines.pipeline.GrapheneRun")
    originRunIds = non_null_list(graphene.String)

    class Meta:
        name = "InstigationTick"

    def __init__(self, _, job_tick):
        self._job_tick = check.inst_param(job_tick, "job_tick", InstigatorTick)

        super().__init__(
            status=job_tick.status,
            timestamp=job_tick.timestamp,
            runIds=job_tick.run_ids,
            error=job_tick.error,
            skipReason=job_tick.skip_reason,
            originRunIds=job_tick.origin_run_ids,
        )

    def resolve_id(self, _):
        return "%s:%s" % (self._job_tick.job_origin_id, self._job_tick.timestamp)

    def resolve_runs(self, graphene_info):
        from .pipelines.pipeline import GrapheneRun

        instance = graphene_info.context.instance
        if self._job_tick.origin_run_ids:
            return [
                GrapheneRun(instance.get_run_by_id(run_id))
                for run_id in self._job_tick.origin_run_ids
                if instance.has_run(run_id)
            ]
        return [
            GrapheneRun(instance.get_run_by_id(run_id))
            for run_id in self._job_tick.run_ids
            if instance.has_run(run_id)
        ]


class GrapheneFutureInstigationTick(graphene.ObjectType):
    timestamp = graphene.NonNull(graphene.Float)
    evaluationResult = graphene.Field(lambda: GrapheneTickEvaluation)

    class Meta:
        name = "FutureInstigationTick"

    def __init__(self, job_state, timestamp):
        self._job_state = check.inst_param(job_state, "job_state", InstigatorState)
        self._timestamp = timestamp
        super().__init__(
            timestamp=check.float_param(timestamp, "timestamp"),
        )

    def resolve_evaluationResult(self, graphene_info):
        if self._job_state.status != InstigatorStatus.RUNNING:
            return None

        if self._job_state.job_type != InstigatorType.SCHEDULE:
            return None

        repository_origin = self._job_state.origin.external_repository_origin
        if not graphene_info.context.has_repository_location(
            repository_origin.repository_location_origin.location_name
        ):
            return None

        repository_location = graphene_info.context.get_repository_location(
            repository_origin.repository_location_origin.location_name
        )
        if not repository_location.has_repository(repository_origin.repository_name):
            return None

        repository = repository_location.get_repository(repository_origin.repository_name)
        external_schedule = repository.get_external_schedule(self._job_state.name)
        timezone_str = external_schedule.execution_timezone
        if not timezone_str:
            timezone_str = "UTC"

        next_tick_datetime = next(external_schedule.execution_time_iterator(self._timestamp))
        schedule_time = to_timezone(pendulum.instance(next_tick_datetime), timezone_str)
        try:
            schedule_data = repository_location.get_external_schedule_execution_data(
                instance=graphene_info.context.instance,
                repository_handle=repository.handle,
                schedule_name=external_schedule.name,
                scheduled_execution_time=schedule_time,
            )
        except Exception:
            schedule_data = serializable_error_info_from_exc_info(sys.exc_info())

        return GrapheneTickEvaluation(schedule_data)


class GrapheneTickEvaluation(graphene.ObjectType):
    runRequests = graphene.List(lambda: GrapheneRunRequest)
    skipReason = graphene.String()
    error = graphene.Field(GraphenePythonError)

    class Meta:
        name = "TickEvaluation"

    def __init__(self, schedule_data):
        check.inst_param(
            schedule_data,
            "schedule_data",
            (ScheduleExecutionData, SerializableErrorInfo),
        )
        error = schedule_data if isinstance(schedule_data, SerializableErrorInfo) else None
        skip_reason = (
            schedule_data.skip_message if isinstance(schedule_data, ScheduleExecutionData) else None
        )
        self._run_requests = (
            schedule_data.run_requests if isinstance(schedule_data, ScheduleExecutionData) else None
        )
        super().__init__(skipReason=skip_reason, error=error)

    def resolve_runRequests(self, _graphene_info):
        if not self._run_requests:
            return self._run_requests

        return [GrapheneRunRequest(run_request) for run_request in self._run_requests]


class GrapheneRunRequest(graphene.ObjectType):
    runKey = graphene.String()
    tags = non_null_list(GraphenePipelineTag)
    runConfigYaml = graphene.NonNull(graphene.String)

    class Meta:
        name = "RunRequest"

    def __init__(self, run_request):
        super().__init__(runKey=run_request.run_key)
        self._run_request = check.inst_param(run_request, "run_request", RunRequest)

    def resolve_tags(self, _graphene_info):
        return [
            GraphenePipelineTag(key=key, value=value)
            for key, value in self._run_request.tags.items()
            if get_tag_type(key) != TagType.HIDDEN
        ]

    def resolve_runConfigYaml(self, _graphene_info):
        return yaml.dump(self._run_request.run_config, default_flow_style=False, allow_unicode=True)


class GrapheneFutureInstigationTicks(graphene.ObjectType):
    results = non_null_list(GrapheneFutureInstigationTick)
    cursor = graphene.NonNull(graphene.Float)

    class Meta:
        name = "FutureInstigationTicks"


class GrapheneInstigationState(graphene.ObjectType):
    id = graphene.NonNull(graphene.ID)
    name = graphene.NonNull(graphene.String)
    instigationType = graphene.NonNull(GrapheneInstigationType)
    status = graphene.NonNull(GrapheneInstigationStatus)
    repositoryOrigin = graphene.NonNull(GrapheneRepositoryOrigin)
    typeSpecificData = graphene.Field(GrapheneInstigationTypeSpecificData)
    runs = graphene.Field(
        non_null_list("dagster_graphql.schema.pipelines.pipeline.GrapheneRun"),
        limit=graphene.Int(),
    )
    runsCount = graphene.NonNull(graphene.Int)
    tick = graphene.Field(GrapheneInstigationTick, timestamp=graphene.Float())
    ticks = graphene.Field(
        non_null_list(GrapheneInstigationTick),
        dayRange=graphene.Int(),
        dayOffset=graphene.Int(),
        limit=graphene.Int(),
    )
    nextTick = graphene.Field(GrapheneFutureInstigationTick)
    runningCount = graphene.NonNull(graphene.Int)  # remove with cron scheduler

    class Meta:
        name = "InstigationState"

    def __init__(self, job_state):
        self._job_state = check.inst_param(job_state, "job_state", InstigatorState)
        super().__init__(
            id=job_state.job_origin_id,
            name=job_state.name,
            instigationType=job_state.job_type,
            status=job_state.status,
        )

    def resolve_repositoryOrigin(self, _graphene_info):
        origin = self._job_state.origin.external_repository_origin
        return GrapheneRepositoryOrigin(origin)

    def resolve_typeSpecificData(self, _graphene_info):
        if not self._job_state.job_specific_data:
            return None

        if self._job_state.job_type == InstigatorType.SENSOR:
            return GrapheneSensorData(self._job_state.job_specific_data)

        if self._job_state.job_type == InstigatorType.SCHEDULE:
            return GrapheneScheduleData(self._job_state.job_specific_data)

        return None

    def resolve_runs(self, graphene_info, **kwargs):
        from .pipelines.pipeline import GrapheneRun

        if self._job_state.job_type == InstigatorType.SENSOR:
            filters = PipelineRunsFilter.for_sensor(self._job_state)
        else:
            filters = PipelineRunsFilter.for_schedule(self._job_state)
        return [
            GrapheneRun(r)
            for r in graphene_info.context.instance.get_runs(
                filters=filters,
                limit=kwargs.get("limit"),
            )
        ]

    def resolve_runsCount(self, graphene_info):
        if self._job_state.job_type == InstigatorType.SENSOR:
            filters = PipelineRunsFilter.for_sensor(self._job_state)
        else:
            filters = PipelineRunsFilter.for_schedule(self._job_state)
        return graphene_info.context.instance.get_runs_count(filters=filters)

    def resolve_tick(self, graphene_info, timestamp):
        tick = graphene_info.context.instance.get_job_tick(
            self._job_state.job_origin_id, timestamp=timestamp
        )
        return GrapheneInstigationTick(graphene_info, tick) if tick else None

    def resolve_ticks(self, graphene_info, dayRange=None, dayOffset=None, limit=None):
        before = pendulum.now("UTC").subtract(days=dayOffset).timestamp() if dayOffset else None
        after = (
            pendulum.now("UTC").subtract(days=dayRange + (dayOffset or 0)).timestamp()
            if dayRange
            else None
        )
        return [
            GrapheneInstigationTick(graphene_info, tick)
            for tick in graphene_info.context.instance.get_job_ticks(
                self._job_state.job_origin_id, before=before, after=after, limit=limit
            )
        ]

    def resolve_nextTick(self, graphene_info):
        # sensor
        if self._job_state.job_type == InstigatorType.SENSOR:
            return get_sensor_next_tick(graphene_info, self._job_state)
        else:
            return get_schedule_next_tick(graphene_info, self._job_state)

    def resolve_runningCount(self, _graphene_info):
        return 1 if self._job_state.status == InstigatorStatus.RUNNING else 0


class GrapheneInstigationStates(graphene.ObjectType):
    results = non_null_list(GrapheneInstigationState)

    class Meta:
        name = "InstigationStates"


class GrapheneInstigationStateOrError(graphene.Union):
    class Meta:
        name = "InstigationStateOrError"
        types = (GrapheneInstigationState, GraphenePythonError)


class GrapheneInstigationStatesOrError(graphene.Union):
    class Meta:
        types = (GrapheneInstigationStates, GraphenePythonError)
        name = "InstigationStatesOrError"


types = [
    GrapheneFutureInstigationTick,
    GrapheneFutureInstigationTicks,
    GrapheneInstigationTypeSpecificData,
    GrapheneInstigationState,
    GrapheneInstigationStateOrError,
    GrapheneInstigationStates,
    GrapheneInstigationStatesOrError,
    GrapheneInstigationTick,
    GrapheneScheduleData,
    GrapheneSensorData,
]
