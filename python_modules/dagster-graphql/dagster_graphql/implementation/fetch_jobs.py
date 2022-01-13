from dagster import check
from dagster.core.definitions.run_request import InstigatorType
from dagster.core.host_representation import InstigationSelector
from dagster.core.scheduler.instigation import InstigatorStatus

from .utils import capture_error


@capture_error
def get_unloadable_job_states_or_error(graphene_info, job_type=None):
    from ..schema.instigation import GrapheneInstigationState, GrapheneInstigationStates

    check.opt_inst_param(job_type, "job_type", InstigatorType)
    job_states = graphene_info.context.instance.all_stored_job_state(job_type=job_type)
    external_jobs = [
        job
        for repository_location in graphene_info.context.repository_locations
        for repository in repository_location.get_repositories().values()
        for job in repository.get_external_schedules() + repository.get_external_sensors()
    ]

    job_origin_ids = {job.get_external_origin_id() for job in external_jobs}

    unloadable_states = [
        job_state
        for job_state in job_states
        if job_state.job_origin_id not in job_origin_ids
        and job_state.status == InstigatorStatus.RUNNING
    ]

    return GrapheneInstigationStates(
        results=[GrapheneInstigationState(job_state=job_state) for job_state in unloadable_states]
    )


@capture_error
def get_job_state_or_error(graphene_info, selector):
    from ..schema.instigation import GrapheneInstigationState

    check.inst_param(selector, "selector", InstigationSelector)
    location = graphene_info.context.get_repository_location(selector.location_name)
    repository = location.get_repository(selector.repository_name)

    if repository.has_external_sensor(selector.name):
        external_sensor = repository.get_external_sensor(selector.name)
        job_state = graphene_info.context.instance.get_job_state(
            external_sensor.get_external_origin_id()
        )
        if not job_state:
            job_state = external_sensor.get_default_instigation_state()
    elif repository.has_external_schedule(selector.name):
        external_schedule = repository.get_external_schedule(selector.name)
        job_state = graphene_info.context.instance.get_job_state(
            external_schedule.get_external_origin_id()
        )
        if not job_state:
            job_state = external_schedule.get_default_instigation_state()
    else:
        check.failed(f"Could not find a definition for {selector.name}")

    return GrapheneInstigationState(job_state=job_state)
