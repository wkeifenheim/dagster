from dagster import check
from dagster.core.definitions.run_request import InstigatorType
from dagster.core.host_representation import PipelineSelector, RepositorySelector, SensorSelector
from dagster.core.scheduler.instigation import InstigatorState, InstigatorStatus
from dagster.seven import get_current_datetime_in_utc, get_timestamp_from_utc_datetime
from graphql.execution.base import ResolveInfo

from .utils import UserFacingGraphQLError, capture_error


@capture_error
def get_sensors_or_error(graphene_info, repository_selector):
    from ..schema.sensors import GrapheneSensor, GrapheneSensors

    check.inst_param(graphene_info, "graphene_info", ResolveInfo)
    check.inst_param(repository_selector, "repository_selector", RepositorySelector)

    location = graphene_info.context.get_repository_location(repository_selector.location_name)
    repository = location.get_repository(repository_selector.repository_name)
    sensors = repository.get_external_sensors()
    sensor_states_by_name = {
        state.name: state
        for state in graphene_info.context.instance.all_stored_job_state(
            repository_origin_id=repository.get_external_origin_id(),
            job_type=InstigatorType.SENSOR,
        )
    }
    return GrapheneSensors(
        results=[
            GrapheneSensor(
                sensor,
                sensor_states_by_name.get(sensor.name),
            )
            for sensor in sensors
        ]
    )


@capture_error
def get_sensor_or_error(graphene_info, selector):
    from ..schema.errors import GrapheneSensorNotFoundError
    from ..schema.sensors import GrapheneSensor

    check.inst_param(graphene_info, "graphene_info", ResolveInfo)
    check.inst_param(selector, "selector", SensorSelector)
    location = graphene_info.context.get_repository_location(selector.location_name)
    repository = location.get_repository(selector.repository_name)

    if not repository.has_external_sensor(selector.sensor_name):
        raise UserFacingGraphQLError(GrapheneSensorNotFoundError(selector.sensor_name))
    external_sensor = repository.get_external_sensor(selector.sensor_name)
    sensor_state = graphene_info.context.instance.get_job_state(
        external_sensor.get_external_origin_id()
    )

    return GrapheneSensor(external_sensor, sensor_state)


@capture_error
def start_sensor(graphene_info, sensor_selector):
    from ..schema.errors import GrapheneSensorNotFoundError
    from ..schema.sensors import GrapheneSensor

    check.inst_param(graphene_info, "graphene_info", ResolveInfo)
    check.inst_param(sensor_selector, "sensor_selector", SensorSelector)

    location = graphene_info.context.get_repository_location(sensor_selector.location_name)
    repository = location.get_repository(sensor_selector.repository_name)
    if not repository.has_external_sensor(sensor_selector.sensor_name):
        raise UserFacingGraphQLError(GrapheneSensorNotFoundError(sensor_selector.sensor_name))
    external_sensor = repository.get_external_sensor(sensor_selector.sensor_name)
    graphene_info.context.instance.start_sensor(external_sensor)
    sensor_state = graphene_info.context.instance.get_job_state(
        external_sensor.get_external_origin_id()
    )
    return GrapheneSensor(external_sensor, sensor_state)


@capture_error
def stop_sensor(graphene_info, job_origin_id):
    from ..schema.sensors import GrapheneStopSensorMutationResult

    check.inst_param(graphene_info, "graphene_info", ResolveInfo)
    check.str_param(job_origin_id, "job_origin_id")
    instance = graphene_info.context.instance
    job_state = instance.get_job_state(job_origin_id)
    if not job_state:
        return GrapheneStopSensorMutationResult(job_state=None)

    instance.stop_sensor(job_origin_id)
    return GrapheneStopSensorMutationResult(
        job_state=job_state.with_status(InstigatorStatus.STOPPED)
    )


@capture_error
def get_unloadable_sensor_states_or_error(graphene_info):
    from ..schema.instigation import GrapheneInstigationState, GrapheneInstigationStates

    sensor_states = graphene_info.context.instance.all_stored_job_state(
        job_type=InstigatorType.SENSOR
    )
    external_sensors = [
        sensor
        for repository_location in graphene_info.context.repository_locations
        for repository in repository_location.get_repositories().values()
        for sensor in repository.get_external_sensors()
    ]

    sensor_origin_ids = {
        external_sensor.get_external_origin_id() for external_sensor in external_sensors
    }

    unloadable_states = [
        sensor_state
        for sensor_state in sensor_states
        if sensor_state.job_origin_id not in sensor_origin_ids
    ]

    return GrapheneInstigationStates(
        results=[GrapheneInstigationState(job_state=job_state) for job_state in unloadable_states]
    )


def get_sensors_for_pipeline(graphene_info, pipeline_selector):
    from ..schema.sensors import GrapheneSensor

    check.inst_param(graphene_info, "graphene_info", ResolveInfo)
    check.inst_param(pipeline_selector, "pipeline_selector", PipelineSelector)

    location = graphene_info.context.get_repository_location(pipeline_selector.location_name)
    repository = location.get_repository(pipeline_selector.repository_name)
    external_sensors = repository.get_external_sensors()

    results = []
    for external_sensor in external_sensors:
        if pipeline_selector.pipeline_name not in [
            target.pipeline_name for target in external_sensor.get_external_targets()
        ]:
            continue

        sensor_state = graphene_info.context.instance.get_job_state(
            external_sensor.get_external_origin_id()
        )
        results.append(GrapheneSensor(external_sensor, sensor_state))

    return results


def get_sensor_next_tick(graphene_info, sensor_state):
    from ..schema.instigation import GrapheneFutureInstigationTick

    check.inst_param(graphene_info, "graphene_info", ResolveInfo)
    check.inst_param(sensor_state, "sensor_state", InstigatorState)

    repository_origin = sensor_state.origin.external_repository_origin
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
    external_sensor = repository.get_external_sensor(sensor_state.name)

    if sensor_state.status != InstigatorStatus.RUNNING:
        return None

    latest_tick = graphene_info.context.instance.get_latest_job_tick(sensor_state.job_origin_id)
    if not latest_tick:
        return None

    next_timestamp = latest_tick.timestamp + external_sensor.min_interval_seconds
    if next_timestamp < get_timestamp_from_utc_datetime(get_current_datetime_in_utc()):
        return None
    return GrapheneFutureInstigationTick(sensor_state, next_timestamp)
