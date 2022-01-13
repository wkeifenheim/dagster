import base64
import os
import subprocess
import sys
from collections import namedtuple
from contextlib import contextmanager

from dagster import check
from dagster.core.code_pointer import FileCodePointer
from dagster.core.definitions.reconstructable import (
    ReconstructablePipeline,
    ReconstructableRepository,
)
from dagster.core.execution.api import create_execution_plan
from dagster.core.execution.build_resources import build_resources
from dagster.core.execution.context.output import build_output_context
from dagster.core.host_representation import (
    ExternalPipeline,
    ExternalSchedule,
    InProcessRepositoryLocationOrigin,
    RepositoryLocation,
)
from dagster.core.host_representation.origin import (
    ExternalJobOrigin,
    ExternalPipelineOrigin,
    ExternalRepositoryOrigin,
)
from dagster.core.origin import (
    DEFAULT_DAGSTER_ENTRY_POINT,
    PipelinePythonOrigin,
    RepositoryPythonOrigin,
)
from dagster.core.test_utils import in_process_test_workspace
from dagster.serdes import whitelist_for_serdes
from dagster.utils import file_relative_path, git_repository_root

IS_BUILDKITE = os.getenv("BUILDKITE") is not None


def cleanup_memoized_results(pipeline_def, mode_str, instance, run_config):
    # Clean up any memoized outputs from the s3 bucket
    from dagster_aws.s3 import s3_resource, s3_pickle_io_manager

    execution_plan = create_execution_plan(
        pipeline_def, run_config=run_config, instance_ref=instance.get_ref(), mode=mode_str
    )

    with build_resources(
        {"s3": s3_resource, "io_manager": s3_pickle_io_manager},
        resource_config=run_config["resources"],
    ) as resources:
        io_manager = resources.io_manager
        for step_output_handle, version in execution_plan.step_output_versions.items():
            output_context = build_output_context(
                step_key=step_output_handle.step_key,
                name=step_output_handle.output_name,
                version=version,
            )
            # pylint: disable=protected-access
            key = io_manager._get_path(output_context)
            io_manager._rm_object(key)


def get_test_repo_path():
    return os.path.join(
        git_repository_root(), "python_modules", "dagster-test", "dagster_test", "test_project"
    )


def get_test_project_environments_path():
    return os.path.join(get_test_repo_path(), "environments")


def get_buildkite_registry_config():
    import boto3

    ecr_client = boto3.client("ecr", region_name="us-west-2")
    token = ecr_client.get_authorization_token()
    username, password = (
        base64.b64decode(token["authorizationData"][0]["authorizationToken"])
        .decode("utf-8")
        .split(":")
    )
    registry = token["authorizationData"][0]["proxyEndpoint"]

    return {
        "url": registry,
        "username": username,
        "password": password,
    }


def find_local_test_image(docker_image):
    import docker

    try:
        client = docker.from_env()
        client.images.get(docker_image)
        print(  # pylint: disable=print-call
            "Found existing image tagged {image}, skipping image build. To rebuild, first run: "
            "docker rmi {image}".format(image=docker_image)
        )
    except docker.errors.ImageNotFound:
        build_and_tag_test_image(docker_image)


def build_and_tag_test_image(tag):
    check.str_param(tag, "tag")

    base_python = "3.8.8"

    # Build and tag local dagster test image
    return subprocess.check_output(["./build.sh", base_python, tag], cwd=get_test_repo_path())


def get_test_project_recon_pipeline(pipeline_name, container_image=None):
    return ReOriginatedReconstructablePipelineForTest(
        ReconstructableRepository.for_file(
            file_relative_path(__file__, "test_pipelines/repo.py"),
            "define_demo_execution_repo",
            container_image=container_image,
        ).get_reconstructable_pipeline(pipeline_name)
    )


class ReOriginatedReconstructablePipelineForTest(ReconstructablePipeline):
    def __new__(  # pylint: disable=signature-differs
        cls,
        reconstructable_pipeline,
    ):
        return super(ReOriginatedReconstructablePipelineForTest, cls).__new__(
            cls,
            reconstructable_pipeline.repository,
            reconstructable_pipeline.pipeline_name,
            reconstructable_pipeline.solid_selection_str,
            reconstructable_pipeline.solids_to_execute,
        )

    def get_python_origin(self):
        """
        Hack! Inject origin that the docker-celery images will use. The BK image uses a different
        directory structure (/workdir/python_modules/dagster-test/dagster_test/test_project) than
        the test that creates the ReconstructablePipeline. As a result the normal origin won't
        work, we need to inject this one.
        """

        return PipelinePythonOrigin(
            self.pipeline_name,
            RepositoryPythonOrigin(
                executable_path="python",
                code_pointer=FileCodePointer(
                    "/dagster_test/test_project/test_pipelines/repo.py",
                    "define_demo_execution_repo",
                ),
                container_image=self.repository.container_image,
                entry_point=DEFAULT_DAGSTER_ENTRY_POINT,
            ),
        )


class ReOriginatedExternalPipelineForTest(ExternalPipeline):
    def __init__(
        self,
        external_pipeline,
        container_image=None,
    ):
        self._container_image = container_image
        super(ReOriginatedExternalPipelineForTest, self).__init__(
            external_pipeline.external_pipeline_data,
            external_pipeline.repository_handle,
        )

    def get_python_origin(self):
        """
        Hack! Inject origin that the k8s images will use. The BK image uses a different directory
        structure (/workdir/python_modules/dagster-test/dagster_test/test_project) than the images
        inside the kind cluster (/dagster_test/test_project). As a result the normal origin won't
        work, we need to inject this one.
        """

        return PipelinePythonOrigin(
            self._pipeline_index.name,
            RepositoryPythonOrigin(
                executable_path="python",
                code_pointer=FileCodePointer(
                    "/dagster_test/test_project/test_pipelines/repo.py",
                    "define_demo_execution_repo",
                ),
                container_image=self._container_image,
                entry_point=DEFAULT_DAGSTER_ENTRY_POINT,
            ),
        )

    def get_external_origin(self):
        """
        Hack! Inject origin that the k8s images will use. The BK image uses a different directory
        structure (/workdir/python_modules/dagster-test/dagster_test/test_project) than the images
        inside the kind cluster (/dagster_test/test_project). As a result the normal origin won't
        work, we need to inject this one.
        """

        return ExternalPipelineOrigin(
            external_repository_origin=ExternalRepositoryOrigin(
                repository_location_origin=InProcessRepositoryLocationOrigin(
                    recon_repo=ReconstructableRepository(
                        pointer=FileCodePointer(
                            python_file="/dagster_test/test_project/test_pipelines/repo.py",
                            fn_name="define_demo_execution_repo",
                        ),
                        container_image=self._container_image,
                        executable_path="python",
                        entry_point=DEFAULT_DAGSTER_ENTRY_POINT,
                    )
                ),
                repository_name="demo_execution_repo",
            ),
            pipeline_name=self._pipeline_index.name,
        )


class ReOriginatedExternalScheduleForTest(ExternalSchedule):
    def __init__(
        self,
        external_schedule,
        container_image=None,
    ):
        self._container_image = container_image
        super(ReOriginatedExternalScheduleForTest, self).__init__(
            external_schedule._external_schedule_data,
            external_schedule.handle.repository_handle,
        )

    def get_external_origin(self):
        """
        Hack! Inject origin that the k8s images will use. The BK image uses a different directory
        structure (/workdir/python_modules/dagster-test/dagster_test/test_project) than the images
        inside the kind cluster (/dagster_test/test_project). As a result the normal origin won't
        work, we need to inject this one.
        """

        return ExternalJobOrigin(
            external_repository_origin=ExternalRepositoryOrigin(
                repository_location_origin=InProcessRepositoryLocationOrigin(
                    recon_repo=ReconstructableRepository(
                        pointer=FileCodePointer(
                            python_file="/dagster_test/test_project/test_pipelines/repo.py",
                            fn_name="define_demo_execution_repo",
                        ),
                        container_image=self._container_image,
                        executable_path="python",
                        entry_point=DEFAULT_DAGSTER_ENTRY_POINT,
                    )
                ),
                repository_name="demo_execution_repo",
            ),
            job_name=self.name,
        )


@contextmanager
def get_test_project_workspace(instance, container_image=None):
    with in_process_test_workspace(
        instance,
        recon_repo=ReconstructableRepository.for_file(
            file_relative_path(__file__, "test_pipelines/repo.py"),
            "define_demo_execution_repo",
            container_image=container_image,
        ),
    ) as workspace:
        yield workspace


@contextmanager
def get_test_project_external_pipeline_hierarchy(instance, pipeline_name, container_image=None):
    with get_test_project_workspace(instance, container_image) as workspace:
        location = workspace.get_repository_location(workspace.repository_location_names[0])
        repo = location.get_repository("demo_execution_repo")
        pipeline = repo.get_full_external_pipeline(pipeline_name)
        yield workspace, location, repo, pipeline


@contextmanager
def get_test_project_external_repo(instance, container_image=None):
    with get_test_project_workspace(instance, container_image) as workspace:
        location = workspace.get_repository_location(workspace.repository_location_names[0])
        yield location, location.get_repository("demo_execution_repo")


@contextmanager
def get_test_project_workspace_and_external_pipeline(instance, pipeline_name, container_image=None):
    with get_test_project_external_pipeline_hierarchy(instance, pipeline_name, container_image) as (
        workspace,
        _location,
        _repo,
        pipeline,
    ):
        yield workspace, pipeline


@contextmanager
def get_test_project_external_schedule(instance, schedule_name, container_image=None):
    with get_test_project_external_repo(instance, container_image=container_image) as (_, repo):
        yield repo.get_external_schedule(schedule_name)


def get_test_project_docker_image():
    docker_repository = os.getenv("DAGSTER_DOCKER_REPOSITORY")
    image_name = os.getenv("DAGSTER_DOCKER_IMAGE", "buildkite-test-image")
    docker_image_tag = os.getenv("DAGSTER_DOCKER_IMAGE_TAG")

    if IS_BUILDKITE:
        assert docker_image_tag is not None, (
            "This test requires the environment variable DAGSTER_DOCKER_IMAGE_TAG to be set "
            "to proceed"
        )
        assert docker_repository is not None, (
            "This test requires the environment variable DAGSTER_DOCKER_REPOSITORY to be set "
            "to proceed"
        )

    # This needs to be a domain name to avoid the k8s machinery automatically prefixing it with
    # `docker.io/` and attempting to pull images from Docker Hub
    if not docker_repository:
        docker_repository = "dagster.io.priv"

    if not docker_image_tag:
        # Detect the python version we're running on
        majmin = str(sys.version_info.major) + str(sys.version_info.minor)

        docker_image_tag = "py{majmin}-{image_version}".format(
            majmin=majmin, image_version="latest"
        )

    final_docker_image = "{repository}/{image_name}:{tag}".format(
        repository=docker_repository, image_name=image_name, tag=docker_image_tag
    )
    print("Using Docker image: %s" % final_docker_image)  # pylint: disable=print-call
    return final_docker_image
