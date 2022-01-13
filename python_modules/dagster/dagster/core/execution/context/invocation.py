# pylint: disable=super-init-not-called
from typing import AbstractSet, Any, Dict, NamedTuple, Optional, Union, cast

from dagster import check
from dagster.config import Shape
from dagster.core.definitions.composition import PendingNodeInvocation
from dagster.core.definitions.dependency import Node, NodeHandle
from dagster.core.definitions.hook_definition import HookDefinition
from dagster.core.definitions.mode import ModeDefinition
from dagster.core.definitions.op_definition import OpDefinition
from dagster.core.definitions.pipeline_definition import PipelineDefinition
from dagster.core.definitions.resource_definition import (
    IContainsGenerator,
    Resources,
    ScopedResourcesBuilder,
)
from dagster.core.definitions.solid_definition import SolidDefinition
from dagster.core.definitions.step_launcher import StepLauncher
from dagster.core.errors import (
    DagsterInvalidConfigError,
    DagsterInvalidInvocationError,
    DagsterInvalidPropertyError,
    DagsterInvariantViolationError,
)
from dagster.core.execution.build_resources import build_resources
from dagster.core.instance import DagsterInstance
from dagster.core.log_manager import DagsterLogManager
from dagster.core.storage.pipeline_run import PipelineRun
from dagster.core.types.dagster_type import DagsterType
from dagster.utils import merge_dicts
from dagster.utils.forked_pdb import ForkedPdb

from .compute import OpExecutionContext
from .system import StepExecutionContext, TypeCheckContext


def _property_msg(prop_name: str, method_name: str) -> str:
    return (
        f"The {prop_name} {method_name} is not set on the context when a solid is directly invoked."
    )


class UnboundSolidExecutionContext(OpExecutionContext):
    """The ``context`` object available as the first argument to a solid's compute function when
    being invoked directly. Can also be used as a context manager.
    """

    def __init__(
        self,
        solid_config: Any,
        resources_dict: Optional[Dict[str, Any]],
        resources_config: Dict[str, Any],
        instance: Optional[DagsterInstance],
        partition_key: Optional[str],
    ):  # pylint: disable=super-init-not-called
        from dagster.core.execution.context_creation_pipeline import initialize_console_manager
        from dagster.core.execution.api import ephemeral_instance_if_missing

        self._solid_config = solid_config

        self._instance_provided = (
            check.opt_inst_param(instance, "instance", DagsterInstance) is not None
        )
        # Construct ephemeral instance if missing
        self._instance_cm = ephemeral_instance_if_missing(instance)
        # Pylint can't infer that the ephemeral_instance context manager has an __enter__ method,
        # so ignore lint error
        self._instance = self._instance_cm.__enter__()  # pylint: disable=no-member

        self._resources_config = resources_config
        # Open resource context manager
        self._resources_contain_cm = False
        self._resources_cm = build_resources(
            resources=check.opt_dict_param(resources_dict, "resources_dict", key_type=str),
            instance=instance,
            resource_config=resources_config,
        )
        self._resources = self._resources_cm.__enter__()  # pylint: disable=no-member
        self._resources_contain_cm = isinstance(self._resources, IContainsGenerator)

        self._log = initialize_console_manager(None)
        self._pdb: Optional[ForkedPdb] = None
        self._cm_scope_entered = False
        self._partition_key = partition_key

    def __enter__(self):
        self._cm_scope_entered = True
        return self

    def __exit__(self, *exc):
        self._resources_cm.__exit__(*exc)  # pylint: disable=no-member
        if self._instance_provided:
            self._instance_cm.__exit__(*exc)  # pylint: disable=no-member

    def __del__(self):
        if self._resources_contain_cm and not self._cm_scope_entered:
            self._resources_cm.__exit__(None, None, None)  # pylint: disable=no-member
        if self._instance_provided and not self._cm_scope_entered:
            self._instance_cm.__exit__(None, None, None)  # pylint: disable=no-member

    @property
    def solid_config(self) -> Any:
        return self._solid_config

    @property
    def resources(self) -> Resources:
        if self._resources_contain_cm and not self._cm_scope_entered:
            raise DagsterInvariantViolationError(
                "At least one provided resource is a generator, but attempting to access "
                "resources outside of context manager scope. You can use the following syntax to "
                "open a context manager: `with build_solid_context(...) as context:`"
            )
        return self._resources

    @property
    def pipeline_run(self) -> PipelineRun:
        raise DagsterInvalidPropertyError(_property_msg("pipeline_run", "property"))

    @property
    def instance(self) -> DagsterInstance:
        return self._instance

    @property
    def pdb(self) -> ForkedPdb:
        """dagster.utils.forked_pdb.ForkedPdb: Gives access to pdb debugging from within the solid.

        Example:

        .. code-block:: python

            @solid
            def debug_solid(context):
                context.pdb.set_trace()

        """
        if self._pdb is None:
            self._pdb = ForkedPdb()

        return self._pdb

    @property
    def step_launcher(self) -> Optional[StepLauncher]:
        raise DagsterInvalidPropertyError(_property_msg("step_launcher", "property"))

    @property
    def run_id(self) -> str:
        """str: Hard-coded value to indicate that we are directly invoking solid."""
        return "EPHEMERAL"

    @property
    def run_config(self) -> dict:
        raise DagsterInvalidPropertyError(_property_msg("run_config", "property"))

    @property
    def pipeline_def(self) -> PipelineDefinition:
        raise DagsterInvalidPropertyError(_property_msg("pipeline_def", "property"))

    @property
    def pipeline_name(self) -> str:
        raise DagsterInvalidPropertyError(_property_msg("pipeline_name", "property"))

    @property
    def mode_def(self) -> ModeDefinition:
        raise DagsterInvalidPropertyError(_property_msg("mode_def", "property"))

    @property
    def log(self) -> DagsterLogManager:
        """DagsterLogManager: A console manager constructed for this context."""
        return self._log

    @property
    def solid_handle(self) -> NodeHandle:
        raise DagsterInvalidPropertyError(_property_msg("solid_handle", "property"))

    @property
    def solid(self) -> Node:
        raise DagsterInvalidPropertyError(_property_msg("solid", "property"))

    @property
    def solid_def(self) -> SolidDefinition:
        raise DagsterInvalidPropertyError(_property_msg("solid_def", "property"))

    @property
    def has_partition_key(self) -> bool:
        return self._partition_key is not None

    @property
    def partition_key(self) -> str:
        if self._partition_key:
            return self._partition_key
        else:
            check.failed("Tried to access partition_key for a non-partitioned run")

    def has_tag(self, key: str) -> bool:
        raise DagsterInvalidPropertyError(_property_msg("has_tag", "method"))

    def get_tag(self, key: str) -> str:
        raise DagsterInvalidPropertyError(_property_msg("get_tag", "method"))

    def get_step_execution_context(self) -> StepExecutionContext:
        raise DagsterInvalidPropertyError(_property_msg("get_step_execution_context", "methods"))

    def bind(
        self, solid_def_or_invocation: Union[SolidDefinition, PendingNodeInvocation]
    ) -> "BoundSolidExecutionContext":

        solid_def = (
            solid_def_or_invocation
            if isinstance(solid_def_or_invocation, SolidDefinition)
            else solid_def_or_invocation.node_def.ensure_solid_def()
        )

        _validate_resource_requirements(self.resources, solid_def)

        solid_config = _resolve_bound_config(self.solid_config, solid_def)

        return BoundSolidExecutionContext(
            solid_def=solid_def,
            solid_config=solid_config,
            resources=self.resources,
            resources_config=self._resources_config,
            instance=self.instance,
            log_manager=self.log,
            pdb=self.pdb,
            tags=solid_def_or_invocation.tags
            if isinstance(solid_def_or_invocation, PendingNodeInvocation)
            else None,
            hook_defs=solid_def_or_invocation.hook_defs
            if isinstance(solid_def_or_invocation, PendingNodeInvocation)
            else None,
            alias=solid_def_or_invocation.given_alias
            if isinstance(solid_def_or_invocation, PendingNodeInvocation)
            else None,
        )


def _validate_resource_requirements(resources: "Resources", solid_def: SolidDefinition) -> None:
    """Validate correctness of resources against required resource keys"""

    resources_dict = resources._asdict()  # type: ignore[attr-defined]

    required_resource_keys: AbstractSet[str] = solid_def.required_resource_keys or set()
    for resource_key in required_resource_keys:
        if resource_key not in resources_dict:
            raise DagsterInvalidInvocationError(
                f'{solid_def.node_type_str} "{solid_def.name}" requires resource "{resource_key}", but no resource '
                "with that key was found on the context."
            )


def _resolve_bound_config(solid_config: Any, solid_def: SolidDefinition) -> Any:
    """Validate config against config schema, and return validated config."""
    from dagster.config.validate import process_config

    # Config processing system expects the top level config schema to be a dictionary, but solid
    # config schema can be scalar. Thus, we wrap it in another layer of indirection.
    outer_config_shape = Shape({"config": solid_def.get_config_field()})
    config_evr = process_config(
        outer_config_shape, {"config": solid_config} if solid_config else {}
    )
    if not config_evr.success:
        raise DagsterInvalidConfigError(
            f"Error in config for {solid_def.node_type_str} ",
            config_evr.errors,
            solid_config,
        )
    validated_config = cast(Dict, config_evr.value).get("config")
    mapped_config_evr = solid_def.apply_config_mapping({"config": validated_config})
    if not mapped_config_evr.success:
        raise DagsterInvalidConfigError(
            f"Error in config for {solid_def.node_type_str} ",
            mapped_config_evr.errors,
            solid_config,
        )
    validated_config = cast(Dict, mapped_config_evr.value).get("config")
    return validated_config


class BoundSolidExecutionContext(OpExecutionContext):
    """The solid execution context that is passed to the compute function during invocation.

    This context is bound to a specific solid definition, for which the resources and config have
    been validated.
    """

    def __init__(
        self,
        solid_def: SolidDefinition,
        solid_config: Any,
        resources: "Resources",
        resources_config: Dict[str, Any],
        instance: DagsterInstance,
        log_manager: DagsterLogManager,
        pdb: Optional[ForkedPdb],
        tags: Optional[Dict[str, str]],
        hook_defs: Optional[AbstractSet[HookDefinition]],
        alias: Optional[str],
    ):
        self._solid_def = solid_def
        self._solid_config = solid_config
        self._resources = resources
        self._instance = instance
        self._log = log_manager
        self._pdb = pdb
        self._tags = merge_dicts(self._solid_def.tags, tags) if tags else self._solid_def.tags
        self._hook_defs = hook_defs
        self._alias = alias if alias else self._solid_def.name
        self._resources_config = resources_config

    @property
    def solid_config(self) -> Any:
        return self._solid_config

    @property
    def resources(self) -> Resources:
        return self._resources

    @property
    def pipeline_run(self) -> PipelineRun:
        raise DagsterInvalidPropertyError(_property_msg("pipeline_run", "property"))

    @property
    def instance(self) -> DagsterInstance:
        return self._instance

    @property
    def pdb(self) -> ForkedPdb:
        """dagster.utils.forked_pdb.ForkedPdb: Gives access to pdb debugging from within the solid.

        Example:

        .. code-block:: python

            @solid
            def debug_solid(context):
                context.pdb.set_trace()

        """
        if self._pdb is None:
            self._pdb = ForkedPdb()

        return self._pdb

    @property
    def step_launcher(self) -> Optional[StepLauncher]:
        raise DagsterInvalidPropertyError(_property_msg("step_launcher", "property"))

    @property
    def run_id(self) -> str:
        """str: Hard-coded value to indicate that we are directly invoking solid."""
        return "EPHEMERAL"

    @property
    def run_config(self) -> dict:
        run_config = {}
        if self._solid_config:
            run_config["solids"] = {self._solid_def.name: {"config": self._solid_config}}
        run_config["resources"] = self._resources_config
        return run_config

    @property
    def pipeline_def(self) -> PipelineDefinition:
        raise DagsterInvalidPropertyError(_property_msg("pipeline_def", "property"))

    @property
    def pipeline_name(self) -> str:
        raise DagsterInvalidPropertyError(_property_msg("pipeline_name", "property"))

    @property
    def mode_def(self) -> ModeDefinition:
        raise DagsterInvalidPropertyError(_property_msg("mode_def", "property"))

    @property
    def log(self) -> DagsterLogManager:
        """DagsterLogManager: A console manager constructed for this context."""
        return self._log

    @property
    def solid_handle(self) -> NodeHandle:
        raise DagsterInvalidPropertyError(_property_msg("solid_handle", "property"))

    @property
    def solid(self) -> Node:
        raise DagsterInvalidPropertyError(_property_msg("solid", "property"))

    @property
    def solid_def(self) -> SolidDefinition:
        return self._solid_def

    def has_tag(self, key: str) -> bool:
        return key in self._tags

    def get_tag(self, key: str) -> str:
        return self._tags.get(key)

    @property
    def alias(self) -> str:
        return self._alias

    def get_step_execution_context(self) -> StepExecutionContext:
        raise DagsterInvalidPropertyError(_property_msg("get_step_execution_context", "methods"))

    def for_type(self, dagster_type: DagsterType) -> TypeCheckContext:
        resources = cast(NamedTuple, self.resources)
        return TypeCheckContext(
            self.run_id, self.log, ScopedResourcesBuilder(resources._asdict()), dagster_type
        )

    def get_mapping_key(self) -> Optional[str]:
        return None

    def describe_op(self):
        if isinstance(self.solid_def, OpDefinition):
            return f'op "{self.solid_def.name}"'

        return f'solid "{self.solid_def.name}"'


def build_op_context(
    resources: Optional[Dict[str, Any]] = None,
    op_config: Any = None,
    resources_config: Optional[Dict[str, Any]] = None,
    instance: Optional[DagsterInstance] = None,
    config: Any = None,
    partition_key: Optional[str] = None,
) -> OpExecutionContext:
    """Builds op execution context from provided parameters.

    ``op`` is currently built on top of `solid`, and thus this function creates a `SolidExecutionContext`.
    ``build_op_context`` can be used as either a function or context manager. If there is a
    provided resource that is a context manager, then ``build_op_context`` must be used as a
    context manager. This function can be used to provide the context argument when directly
    invoking a op.

    Args:
        resources (Optional[Dict[str, Any]]): The resources to provide to the context. These can be
            either values or resource definitions.
        config (Optional[Any]): The op config to provide to the context.
        instance (Optional[DagsterInstance]): The dagster instance configured for the context.
            Defaults to DagsterInstance.ephemeral().

    Examples:
        .. code-block:: python

            context = build_op_context()
            op_to_invoke(context)

            with build_op_context(resources={"foo": context_manager_resource}) as context:
                op_to_invoke(context)
    """

    if op_config and config:
        raise DagsterInvalidInvocationError(
            "Attempted to invoke ``build_op_context`` with both ``op_config``, and its "
            "legacy version, ``config``. Please provide one or the other."
        )

    op_config = op_config if op_config else config
    return build_solid_context(
        resources=resources,
        resources_config=resources_config,
        solid_config=op_config,
        instance=instance,
        partition_key=partition_key,
    )


def build_solid_context(
    resources: Optional[Dict[str, Any]] = None,
    solid_config: Any = None,
    resources_config: Optional[Dict[str, Any]] = None,
    instance: Optional[DagsterInstance] = None,
    config: Any = None,
    partition_key: Optional[str] = None,
) -> UnboundSolidExecutionContext:
    """Builds solid execution context from provided parameters.

    ``build_solid_context`` can be used as either a function or context manager. If there is a
    provided resource that is a context manager, then ``build_solid_context`` must be used as a
    context manager. This function can be used to provide the context argument when directly
    invoking a solid.

    Args:
        resources (Optional[Dict[str, Any]]): The resources to provide to the context. These can be
            either values or resource definitions.
        solid_config (Optional[Any]): The solid config to provide to the context. The value provided
            here will be available as ``context.solid_config``.
        resources_config (Optional[Dict[str, Any]]): Configuration for any resource definitions
            provided to the resources arg. The configuration under a specific key should match the
            resource under a specific key in the resources dictionary.
        instance (Optional[DagsterInstance]): The dagster instance configured for the context.
            Defaults to DagsterInstance.ephemeral().

    Examples:
        .. code-block:: python

            context = build_solid_context()
            solid_to_invoke(context)

            with build_solid_context(resources={"foo": context_manager_resource}) as context:
                solid_to_invoke(context)
    """

    if solid_config and config:
        raise DagsterInvalidInvocationError(
            "Attempted to invoke ``build_solid_context`` with both ``solid_config``, and its "
            "legacy version, ``config``. Please provide one or the other."
        )

    solid_config = solid_config if solid_config else config

    return UnboundSolidExecutionContext(
        resources_dict=check.opt_dict_param(resources, "resources", key_type=str),
        resources_config=check.opt_dict_param(resources_config, "resources_config", key_type=str),
        solid_config=solid_config,
        instance=check.opt_inst_param(instance, "instance", DagsterInstance),
        partition_key=check.opt_str_param(partition_key, "partition_key"),
    )
