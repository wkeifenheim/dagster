"""
Serialization & deserialization for Dagster objects.

Why have custom serialization?

* Default json serialization doesn't work well on namedtuples, which we use extensively to create
  immutable value types. Namedtuples serialize like tuples as flat lists.
* Explicit whitelisting should help ensure we are only persisting or communicating across a
  serialization boundary the types we expect to.

Why not pickle?

* This isn't meant to replace pickle in the conditions that pickle is reasonable to use
  (in memory, not human readable, etc) just handle the json case effectively.
"""

from abc import ABC, abstractmethod
from enum import Enum
from inspect import Parameter, signature
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    cast,
    overload,
)

from dagster import check, seven

from .errors import DeserializationError, SerdesUsageError, SerializationError

###################################################################################################
# Whitelisting
###################################################################################################

TupleEntry = Tuple[
    Optional[Type[NamedTuple]], Type["NamedTupleSerializer"], Mapping[str, Parameter]
]
EnumEntry = Tuple[Type[Enum], Type["EnumSerializer"]]


class WhitelistMap(NamedTuple):
    tuples: Dict[str, TupleEntry]
    enums: Dict[str, EnumEntry]

    def register_tuple(
        self,
        name: str,
        nt: Optional[Type[NamedTuple]],
        serializer: Optional[Type["NamedTupleSerializer"]],
        args_for_class: Mapping[str, Parameter],
    ):
        """
        Args:
            name: The class name of the namedtuple to register
            nt: The namedtuple class to register.
                Can be None to gracefull load previously serialized objects as None.
            serializer: The class to use when serializing and deserializing
            args_for_class: the inspect.signature paramaters for __new__
        """
        self.tuples[name] = (nt, serializer or DefaultNamedTupleSerializer, args_for_class)

    def has_tuple_entry(self, name: str) -> bool:
        return name in self.tuples

    def get_tuple_entry(self, name: str) -> TupleEntry:
        return self.tuples[name]

    def register_enum(
        self,
        name: str,
        enum: Type[Enum],
        serializer: Optional[Type["EnumSerializer"]],
    ):
        self.enums[name] = (enum, serializer or DefaultEnumSerializer)

    def has_enum_entry(self, name: str) -> bool:
        return name in self.enums

    def get_enum_entry(self, name: str) -> EnumEntry:
        return self.enums[name]

    @staticmethod
    def create():
        return WhitelistMap(tuples={}, enums={})


_WHITELIST_MAP = WhitelistMap.create()


@overload
def whitelist_for_serdes(__cls: Type) -> Type:
    ...


@overload
def whitelist_for_serdes(
    __cls: None = None, *, serializer: Type["Serializer"]
) -> Callable[[Type], Type]:
    ...


def whitelist_for_serdes(
    __cls: Optional[Type] = None, *, serializer: Optional[Type["Serializer"]] = None
):
    """
    Decorator to whitelist a named tuple or enum to be serializable.

    @whitelist_for_serdes
    class

    """

    if __cls is not None:  # decorator invoked directly on class
        check.class_param(__cls, "__cls")
        return _whitelist_for_serdes(whitelist_map=_WHITELIST_MAP, serializer=None)(__cls)
    else:  # decorator passed params
        check.subclass_param(serializer, "serializer", Serializer)
        serializer = cast(Type[Serializer], serializer)
        return _whitelist_for_serdes(whitelist_map=_WHITELIST_MAP, serializer=serializer)


def _whitelist_for_serdes(
    whitelist_map: WhitelistMap, serializer: Optional[Type["Serializer"]] = None
) -> Callable[[type], type]:
    def __whitelist_for_serdes(klass: type) -> type:
        if issubclass(klass, Enum) and (
            serializer is None or issubclass(serializer, EnumSerializer)
        ):
            whitelist_map.register_enum(klass.__name__, klass, serializer)
        elif issubclass(klass, tuple) and (
            serializer is None or issubclass(serializer, NamedTupleSerializer)
        ):
            sig_params = signature(klass.__new__).parameters
            _check_serdes_tuple_class_invariants(klass, sig_params)
            whitelist_map.register_tuple(
                klass.__name__, cast(Type[NamedTuple], klass), serializer, sig_params
            )
        else:
            raise SerdesUsageError(f"Can not whitelist class {klass} for serializer {serializer}")

        return klass

    return __whitelist_for_serdes


class Serializer(ABC):
    pass


class EnumSerializer(Serializer):
    @classmethod
    @abstractmethod
    def value_from_storage_str(cls, storage_str: str, klass: Type) -> Enum:
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def value_to_storage_str(
        cls, value: Enum, whitelist_map: WhitelistMap, descent_path: str
    ) -> str:
        raise NotImplementedError()


class DefaultEnumSerializer(EnumSerializer):
    @classmethod
    def value_from_storage_str(cls, storage_str: str, klass: Type) -> Enum:
        return getattr(klass, storage_str)

    @classmethod
    def value_to_storage_str(
        cls, value: Enum, whitelist_map: WhitelistMap, descent_path: str
    ) -> str:
        return str(value)


class NamedTupleSerializer(Serializer):
    @classmethod
    @abstractmethod
    def value_from_storage_dict(
        cls,
        storage_dict: Dict[str, Any],
        klass: Type,
        args_for_class: Mapping[str, Parameter],
        whitelist_map: WhitelistMap,
        descent_path: str,
    ) -> NamedTuple:
        """
        Load the target value from the object tree output of json parsing.

        Args:
            storage_dict: The parsed json object to hydrate
            klass: The namedtuple class object
            args_for_class: the inspect.signature paramaters for __new__
            whitelist_map: current map of whitelisted serdes objects
            descent_path: the path to the current node from the root
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def value_to_storage_dict(
        cls,
        value: NamedTuple,
        whitelist_map: WhitelistMap,
        descent_path: str,
    ) -> Dict[str, Any]:
        """
        Transform the object in to a form that can be json serialized.

        Args:
            value: the instance of the object
            whitelist_map: current map of whitelisted serdes objects
            descent_path: the path to the current node from the root
        """

        raise NotImplementedError()


EMPTY_VALUES_TO_SKIP: Tuple[None, List[Any], Dict[Any, Any], Set[Any]] = (None, [], {}, set())


class DefaultNamedTupleSerializer(NamedTupleSerializer):
    @classmethod
    def skip_when_empty(cls) -> Set[str]:
        # Override this method to leave out certain fields from the serialized namedtuple
        # when they are empty. This can be used to ensure that adding a new field doesn't
        # change the serialized namedtuple.
        return set()

    @classmethod
    def value_from_storage_dict(
        cls,
        storage_dict: Dict[str, Any],
        klass: Type,
        args_for_class: Mapping[str, Parameter],
        whitelist_map: WhitelistMap,
        descent_path: str,
    ) -> NamedTuple:
        # Naively implements backwards compatibility by filtering arguments that aren't present in
        # the constructor. If a property is present in the serialized object, but doesn't exist in
        # the version of the class loaded into memory, that property will be completely ignored.
        unpacked_dict = {
            key: unpack_inner_value(value, whitelist_map, f"{descent_path}.{key}")
            for key, value in storage_dict.items()
            if key in args_for_class
        }
        return cls.value_from_unpacked(unpacked_dict, klass)

    @classmethod
    def value_from_unpacked(
        cls,
        unpacked_dict: Dict[str, Any],
        klass: Type,
    ):
        return klass(**unpacked_dict)

    @classmethod
    def value_to_storage_dict(
        cls,
        value: NamedTuple,
        whitelist_map: WhitelistMap,
        descent_path: str,
    ) -> Dict[str, Any]:
        skip_when_empty_fields = cls.skip_when_empty()

        base_dict = {}
        for key, inner_value in value._asdict().items():
            if key in skip_when_empty_fields and inner_value in EMPTY_VALUES_TO_SKIP:
                continue
            base_dict[key] = pack_inner_value(inner_value, whitelist_map, f"{descent_path}.{key}")

        base_dict["__class__"] = value.__class__.__name__
        return base_dict


###################################################################################################
# Serialize
###################################################################################################


def serialize_dagster_namedtuple(nt: tuple, **json_kwargs) -> str:
    """Serialize a whitelisted named tuple to a json encoded string"""
    check.tuple_param(nt, "nt")
    return _serialize_dagster_namedtuple(nt, whitelist_map=_WHITELIST_MAP, **json_kwargs)


def _serialize_dagster_namedtuple(nt: tuple, whitelist_map: WhitelistMap, **json_kwargs) -> str:
    return seven.json.dumps(pack_inner_value(nt, whitelist_map, _root(nt)), **json_kwargs)


def serialize_value(val: Any, whitelist_map: WhitelistMap = _WHITELIST_MAP) -> str:
    """Serialize a value to a json encoded string."""
    return seven.json.dumps(
        pack_inner_value(val, whitelist_map=whitelist_map, descent_path=_root(val))
    )


def pack_value(val: Any) -> Any:
    """
    Transform a value in to a json serializable form. The following types are transformed in to dicts:
        * whitelisted named tuples
        * whitelisted enums
        * set
        * frozenset
    """
    return pack_inner_value(val, whitelist_map=_WHITELIST_MAP, descent_path=_root(val))


def pack_inner_value(val: Any, whitelist_map: WhitelistMap, descent_path: str) -> Any:
    if isinstance(val, list):
        return [
            pack_inner_value(item, whitelist_map, f"{descent_path}[{idx}]")
            for idx, item in enumerate(val)
        ]
    if isinstance(val, tuple):
        klass_name = val.__class__.__name__
        if not whitelist_map.has_tuple_entry(klass_name):
            raise SerializationError(
                f"Can only serialize whitelisted namedtuples, received {val}.{_path_msg(descent_path)}",
            )
        val = cast(NamedTuple, val)
        _, serializer, _ = whitelist_map.get_tuple_entry(klass_name)
        return serializer.value_to_storage_dict(val, whitelist_map, descent_path)
    if isinstance(val, Enum):
        klass_name = val.__class__.__name__
        if not whitelist_map.has_enum_entry(klass_name):
            raise SerializationError(
                f"Can only serialize whitelisted Enums, received {klass_name}.{_path_msg(descent_path)}",
            )
        _, enum_serializer = whitelist_map.get_enum_entry(klass_name)
        return {"__enum__": enum_serializer.value_to_storage_str(val, whitelist_map, descent_path)}
    if isinstance(val, set):
        set_path = descent_path + "{}"
        return {
            "__set__": [
                pack_inner_value(item, whitelist_map, set_path)
                for item in sorted(list(val), key=str)
            ]
        }
    if isinstance(val, frozenset):
        frz_set_path = descent_path + "{}"
        return {
            "__frozenset__": [
                pack_inner_value(item, whitelist_map, frz_set_path)
                for item in sorted(list(val), key=str)
            ]
        }
    if isinstance(val, dict):
        return {
            key: pack_inner_value(value, whitelist_map, f"{descent_path}.{key}")
            for key, value in val.items()
        }

    return val


###################################################################################################
# Deserialize
###################################################################################################


def deserialize_json_to_dagster_namedtuple(
    json_str: str,
) -> tuple:
    """Deserialize a json encoded string in to a whitelisted named tuple"""
    dagster_namedtuple = _deserialize_json(
        check.str_param(json_str, "json_str"), whitelist_map=_WHITELIST_MAP
    )
    if not isinstance(dagster_namedtuple, tuple):
        raise DeserializationError(
            f"Output of deserialized json_str was not expected type of tuple. Received type {type(dagster_namedtuple)}."
        )

    return dagster_namedtuple


T = TypeVar("T")


def deserialize_as(json_str: str, cls: Type[T]) -> T:
    """Deserialize a json encoded string to a specific namedtuple class."""
    val = deserialize_json_to_dagster_namedtuple(json_str)
    if isinstance(val, cls):
        return val
    check.failed(f"Deserialized object was not expected target type {cls}, got {type(val)}")


def opt_deserialize_as(json_str: Optional[str], cls: Type[T]) -> Optional[T]:
    """Optionally deserialize a json encoded string to a specific namedtuple class."""
    return deserialize_as(json_str, cls) if json_str else None


def _deserialize_json(json_str: str, whitelist_map: WhitelistMap):
    value = seven.json.loads(json_str)
    return unpack_inner_value(value, whitelist_map=whitelist_map, descent_path=_root(value))


def deserialize_value(val: str, whitelist_map: WhitelistMap = _WHITELIST_MAP) -> Any:
    """Deserialize a json encoded string in to its original value"""
    return unpack_inner_value(
        seven.json.loads(check.str_param(val, "val")),
        whitelist_map=whitelist_map,
        descent_path="",
    )


def unpack_value(val: Any) -> Any:
    """Convert a packed value in to its original form"""
    return unpack_inner_value(
        val,
        whitelist_map=_WHITELIST_MAP,
        descent_path="",
    )


def unpack_inner_value(val: Any, whitelist_map: WhitelistMap, descent_path: str) -> Any:
    if isinstance(val, list):
        return [
            unpack_inner_value(item, whitelist_map, f"{descent_path}[{idx}]")
            for idx, item in enumerate(val)
        ]
    if isinstance(val, dict) and val.get("__class__"):
        klass_name = val.pop("__class__")
        if not whitelist_map.has_tuple_entry(klass_name):
            raise DeserializationError(
                f'Attempted to deserialize class "{klass_name}" which is not in the whitelist. '
                "This error can occur due to version skew, verify processes are running "
                f"expected versions.{_path_msg(descent_path)}"
            )

        klass, serializer, args_for_class = whitelist_map.get_tuple_entry(klass_name)

        # Target class being set to none, likely by
        if klass is None:
            return None

        return serializer.value_from_storage_dict(
            val, klass, args_for_class, whitelist_map, descent_path
        )
    if isinstance(val, dict) and val.get("__enum__"):
        name, member = val["__enum__"].split(".")
        if not whitelist_map.has_enum_entry(name):
            raise DeserializationError(
                f"Attempted to deserialize enum {name} which was not in the whitelist.\n"
                "This error can occur due to version skew, verify processes are running "
                f"expected versions.{_path_msg(descent_path)}"
            )
        enum_class, enum_serializer = whitelist_map.get_enum_entry(name)
        return enum_serializer.value_from_storage_str(member, enum_class)
    if isinstance(val, dict) and val.get("__set__") is not None:
        set_path = descent_path + "{}"
        return set([unpack_inner_value(item, whitelist_map, set_path) for item in val["__set__"]])
    if isinstance(val, dict) and val.get("__frozenset__") is not None:
        frz_set_path = descent_path + "{}"
        return frozenset(
            [unpack_inner_value(item, whitelist_map, frz_set_path) for item in val["__frozenset__"]]
        )
    if isinstance(val, dict):
        return {
            key: unpack_inner_value(value, whitelist_map, f"{descent_path}.{key}")
            for key, value in val.items()
        }

    return val


###################################################################################################
# Back compat
###################################################################################################


def register_serdes_tuple_fallbacks(
    fallback_map: Dict[str, Optional[Type]],
    whitelist_map: WhitelistMap = _WHITELIST_MAP,
) -> None:
    """
    Manually provide remappings for named tuples.
    Used to manage loading previously types that no longer exist.
    """

    for class_name, klass in fallback_map.items():
        whitelist_map.register_tuple(
            class_name,
            klass,
            DefaultNamedTupleSerializer,
            signature(klass.__new__).parameters,
        )


def register_serdes_enum_fallbacks(
    fallback_map: Dict[str, Optional[Type[Enum]]],
    whitelist_map: WhitelistMap = _WHITELIST_MAP,
) -> None:
    """
    Manually provide remappings for named tuples.
    Used to manage loading previously types that no longer exist.
    """

    serializer: Type[EnumSerializer] = DefaultEnumSerializer
    for class_name, klass in fallback_map.items():
        if not klass or not issubclass(klass, Enum):
            raise SerdesUsageError(
                f"Cannot register {klass} as an enum, because it does not have enum type."
            )
        if klass and whitelist_map.has_enum_entry(klass.__name__):
            _, serializer = whitelist_map.get_enum_entry(klass.__name__)
        whitelist_map.register_enum(class_name, klass, serializer)


###################################################################################################
# Validation
###################################################################################################


def _get_dunder_new_params(sig_params):
    return list(sig_params.values())


def _check_serdes_tuple_class_invariants(klass, sig_params):
    dunder_new_params = _get_dunder_new_params(sig_params)

    cls_param = dunder_new_params[0]

    def _with_header(msg):
        return f"For namedtuple {klass.__name__}: {msg}"

    if cls_param.name not in {"cls", "_cls"}:
        raise SerdesUsageError(
            _with_header(f'First parameter must be _cls or cls. Got "{cls_param.name}".')
        )

    value_params = dunder_new_params[1:]

    for index, field in enumerate(klass._fields):

        if index >= len(value_params):
            error_msg = (
                "Missing parameters to __new__. You have declared fields "
                "in the named tuple that are not present as parameters to the "
                "to the __new__ method. In order for "
                "both serdes serialization and pickling to work, "
                "these must match. Missing: {missing_fields}"
            ).format(missing_fields=repr(list(klass._fields[index:])))

            raise SerdesUsageError(_with_header(error_msg))

        value_param = value_params[index]
        if value_param.name != field:
            error_msg = (
                "Params to __new__ must match the order of field declaration in the namedtuple. "
                'Declared field number {one_based_index} in the namedtuple is "{field_name}". '
                'Parameter {one_based_index} in __new__ method is "{param_name}".'
            ).format(one_based_index=index + 1, field_name=field, param_name=value_param.name)
            raise SerdesUsageError(_with_header(error_msg))

    if len(value_params) > len(klass._fields):
        # Ensure that remaining parameters have default values
        for extra_param_index in range(len(klass._fields), len(value_params) - 1):
            if value_params[extra_param_index].default == Parameter.empty:
                error_msg = (
                    'Parameter "{param_name}" is a parameter to the __new__ '
                    "method but is not a field in this namedtuple. The only "
                    "reason why this should exist is that "
                    "it is a field that used to exist (we refer to this as the graveyard) "
                    "but no longer does. However it might exist in historical storage. This "
                    "parameter existing ensures that serdes continues to work. However these "
                    "must come at the end and have a default value for pickling to work."
                ).format(param_name=value_params[extra_param_index].name)
                raise SerdesUsageError(_with_header(error_msg))


def _path_msg(descent_path: str) -> str:
    if not descent_path:
        return ""
    else:
        return f"\nDescent path: {descent_path}"


def _root(val: Any) -> str:
    return f"<root:{val.__class__.__name__}>"
