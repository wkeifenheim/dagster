import graphene
from dagster import check
from dagster.core.host_representation import ExternalSchedule
from dagster.core.scheduler.instigation import InstigatorState
from dagster.seven import get_current_datetime_in_utc, get_timestamp_from_utc_datetime

from ..errors import (
    GraphenePythonError,
    GrapheneRepositoryNotFoundError,
    GrapheneScheduleNotFoundError,
)
from ..instigation import (
    GrapheneFutureInstigationTick,
    GrapheneFutureInstigationTicks,
    GrapheneInstigationState,
)
from ..util import non_null_list


class GrapheneSchedule(graphene.ObjectType):
    id = graphene.NonNull(graphene.ID)
    name = graphene.NonNull(graphene.String)
    cron_schedule = graphene.NonNull(graphene.String)
    pipeline_name = graphene.NonNull(graphene.String)
    solid_selection = graphene.List(graphene.String)
    mode = graphene.NonNull(graphene.String)
    execution_timezone = graphene.Field(graphene.String)
    description = graphene.String()
    scheduleState = graphene.NonNull(GrapheneInstigationState)
    partition_set = graphene.Field("dagster_graphql.schema.partition_sets.GraphenePartitionSet")
    futureTicks = graphene.NonNull(
        GrapheneFutureInstigationTicks,
        cursor=graphene.Float(),
        limit=graphene.Int(),
        until=graphene.Float(),
    )
    futureTick = graphene.NonNull(
        GrapheneFutureInstigationTick, tick_timestamp=graphene.NonNull(graphene.Int)
    )

    class Meta:
        name = "Schedule"

    def __init__(self, external_schedule, schedule_state):
        self._external_schedule = check.inst_param(
            external_schedule, "external_schedule", ExternalSchedule
        )
        self._schedule_state = check.opt_inst_param(
            schedule_state, "schedule_state", InstigatorState
        )
        if not self._schedule_state:
            self._schedule_state = external_schedule.get_default_instigation_state()

        super().__init__(
            name=external_schedule.name,
            cron_schedule=external_schedule.cron_schedule,
            pipeline_name=external_schedule.pipeline_name,
            solid_selection=external_schedule.solid_selection,
            mode=external_schedule.mode,
            scheduleState=GrapheneInstigationState(self._schedule_state),
            execution_timezone=(
                self._external_schedule.execution_timezone
                if self._external_schedule.execution_timezone
                else "UTC"
            ),
            description=external_schedule.description,
        )

    def resolve_id(self, _):
        return self._external_schedule.get_external_origin_id()

    def resolve_partition_set(self, graphene_info):
        from ..partition_sets import GraphenePartitionSet

        if self._external_schedule.partition_set_name is None:
            return None

        repository = graphene_info.context.get_repository_location(
            self._external_schedule.handle.location_name
        ).get_repository(self._external_schedule.handle.repository_name)
        external_partition_set = repository.get_external_partition_set(
            self._external_schedule.partition_set_name
        )

        return GraphenePartitionSet(
            external_repository_handle=repository.handle,
            external_partition_set=external_partition_set,
        )

    def resolve_futureTicks(self, _graphene_info, **kwargs):
        cursor = kwargs.get(
            "cursor", get_timestamp_from_utc_datetime(get_current_datetime_in_utc())
        )
        tick_times = []
        time_iter = self._external_schedule.execution_time_iterator(cursor)

        until = float(kwargs.get("until")) if kwargs.get("until") else None

        if until:
            currentTime = None
            while (not currentTime or currentTime < until) and (
                not kwargs.get("limit") or len(tick_times) < kwargs.get("limit")
            ):
                try:
                    currentTime = next(time_iter).timestamp()
                    if currentTime < until:
                        tick_times.append(currentTime)
                except StopIteration:
                    break
        else:
            limit = kwargs.get("limit", 10)

            for _ in range(limit):
                tick_times.append(next(time_iter).timestamp())

        future_ticks = [
            GrapheneFutureInstigationTick(self._schedule_state, tick_time)
            for tick_time in tick_times
        ]

        return GrapheneFutureInstigationTicks(results=future_ticks, cursor=tick_times[-1] + 1)

    def resolve_futureTick(self, _graphene_info, tick_timestamp):
        return GrapheneFutureInstigationTick(self._schedule_state, float(tick_timestamp))


class GrapheneScheduleOrError(graphene.Union):
    class Meta:
        types = (GrapheneSchedule, GrapheneScheduleNotFoundError, GraphenePythonError)
        name = "ScheduleOrError"


class GrapheneSchedules(graphene.ObjectType):
    results = non_null_list(GrapheneSchedule)

    class Meta:
        name = "Schedules"


class GrapheneSchedulesOrError(graphene.Union):
    class Meta:
        types = (GrapheneSchedules, GrapheneRepositoryNotFoundError, GraphenePythonError)
        name = "SchedulesOrError"
