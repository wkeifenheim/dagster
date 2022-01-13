import gc
from typing import NamedTuple

import objgraph
import pytest
from dagster import (
    DynamicOut,
    DynamicOutput,
    DynamicOutputDefinition,
    Out,
    build_solid_context,
    execute_pipeline,
    execute_solid,
    graph,
    job,
    op,
    pipeline,
    reconstructable,
    solid,
)
from dagster.core.definitions.events import Output
from dagster.core.definitions.output import OutputDefinition
from dagster.core.errors import DagsterInvalidDefinitionError, DagsterInvariantViolationError
from dagster.core.test_utils import instance_for_test


def test_basic():
    @solid(output_defs=[DynamicOutputDefinition()])
    def should_work(_):
        yield DynamicOutput(1, mapping_key="1")
        yield DynamicOutput(2, mapping_key="2")

    result = execute_solid(should_work)

    assert result.success
    assert len(result.get_output_events_for_compute()) == 2
    assert len(result.compute_output_events_dict["result"]) == 2
    assert result.output_values == {"result": {"1": 1, "2": 2}}
    assert result.output_value() == {"1": 1, "2": 2}


def test_basic_op():
    @op(out=DynamicOut())
    def should_work(_):
        yield DynamicOutput(1, mapping_key="1")
        yield DynamicOutput(2, mapping_key="2")

    result = execute_solid(should_work)

    assert result.success
    assert len(result.get_output_events_for_compute()) == 2
    assert len(result.compute_output_events_dict["result"]) == 2
    assert result.output_values == {"result": {"1": 1, "2": 2}}
    assert result.output_value() == {"1": 1, "2": 2}


def test_fails_without_def():
    @solid
    def should_fail(_):
        yield DynamicOutput(True, mapping_key="foo")

    with pytest.raises(DagsterInvariantViolationError, match="did not use DynamicOutputDefinition"):
        execute_solid(should_fail)


def test_fails_with_wrong_output():
    @solid(output_defs=[DynamicOutputDefinition()])
    def should_fail(_):
        yield Output(1)

    with pytest.raises(DagsterInvariantViolationError, match="must yield DynamicOutput"):
        execute_solid(should_fail)

    @solid(output_defs=[DynamicOutputDefinition()])
    def should_also_fail(_):
        return 1

    with pytest.raises(DagsterInvariantViolationError, match="must yield DynamicOutput"):
        execute_solid(should_also_fail)


def test_fails_dupe_keys():
    @solid(output_defs=[DynamicOutputDefinition()])
    def should_fail(_):
        yield DynamicOutput(True, mapping_key="dunk")
        yield DynamicOutput(True, mapping_key="dunk")

    with pytest.raises(DagsterInvariantViolationError, match='mapping_key "dunk" multiple times'):
        execute_solid(should_fail)


def test_invalid_mapping_keys():
    with pytest.raises(DagsterInvalidDefinitionError):
        DynamicOutput(True, mapping_key="")

    with pytest.raises(DagsterInvalidDefinitionError):
        DynamicOutput(True, mapping_key="?")

    with pytest.raises(DagsterInvalidDefinitionError):
        DynamicOutput(True, mapping_key="foo.baz")


def test_multi_output():
    @solid(
        output_defs=[
            DynamicOutputDefinition(int, "numbers"),
            DynamicOutputDefinition(str, "letters"),
            OutputDefinition(str, "wildcard"),
        ]
    )
    def multiout(_):
        yield DynamicOutput(1, output_name="numbers", mapping_key="1")
        yield DynamicOutput(2, output_name="numbers", mapping_key="2")
        yield DynamicOutput("a", output_name="letters", mapping_key="a")
        yield DynamicOutput("b", output_name="letters", mapping_key="b")
        yield DynamicOutput("c", output_name="letters", mapping_key="c")
        yield Output("*", "wildcard")

    @solid
    def double(n):
        return n * 2

    @pipeline
    def multi_dyn():
        numbers, _, _ = multiout()
        numbers.map(double)

    pipe_result = execute_pipeline(multi_dyn)

    assert pipe_result.success

    result = pipe_result.result_for_solid("multiout")
    assert len(result.get_output_events_for_compute("numbers")) == 2
    assert len(result.get_output_events_for_compute("letters")) == 3
    assert result.get_output_event_for_compute("wildcard")
    assert len(result.compute_output_events_dict["numbers"]) == 2
    assert len(result.compute_output_events_dict["letters"]) == 3
    assert len(result.compute_output_events_dict["wildcard"]) == 1
    assert result.output_values == {
        "numbers": {"1": 1, "2": 2},
        "letters": {"a": "a", "b": "b", "c": "c"},
        "wildcard": "*",
    }
    assert result.output_value("numbers") == {"1": 1, "2": 2}
    assert result.output_value("letters") == {"a": "a", "b": "b", "c": "c"}
    assert result.output_value("wildcard") == "*"

    assert pipe_result.output_for_solid("double") == {"1": 2, "2": 4}


def test_multi_out_map():
    @solid(output_defs=[DynamicOutputDefinition()])
    def emit():
        yield DynamicOutput(1, mapping_key="1")
        yield DynamicOutput(2, mapping_key="2")
        yield DynamicOutput(3, mapping_key="3")

    @solid(
        output_defs=[
            OutputDefinition(name="a", is_required=False),
            OutputDefinition(name="b", is_required=False),
            OutputDefinition(name="c", is_required=False),
        ]
    )
    def multiout(inp: int):
        if inp == 1:
            yield Output(inp, output_name="a")
        else:
            yield Output(inp, output_name="b")

    @solid
    def echo(a):
        return a

    @pipeline
    def destructure():
        a, b, c = emit().map(multiout)
        echo.alias("echo_a")(a.collect())
        echo.alias("echo_b")(b.collect())
        echo.alias("echo_c")(c.collect())

    result = execute_pipeline(destructure)
    assert result.result_for_solid("echo_a").output_value() == [1]
    assert result.result_for_solid("echo_b").output_value() == [2, 3]
    assert result.result_for_solid("echo_c").skipped  # all fanned in inputs skipped -> solid skips


def test_context_mapping_key():
    _observed = []

    @solid
    def observe_key(context, _dep=None):
        _observed.append(context.get_mapping_key())

    @solid(output_defs=[DynamicOutputDefinition()])
    def emit():
        yield DynamicOutput(1, mapping_key="key_1")
        yield DynamicOutput(2, mapping_key="key_2")

    @pipeline
    def test():
        observe_key()
        emit().map(observe_key)

    result = execute_pipeline(test)
    assert result.success
    assert _observed == [None, "key_1", "key_2"]

    # test standalone doesn't throw as well
    _observed = []
    observe_key(build_solid_context())
    assert _observed == [None]


def test_dynamic_with_op():
    @op
    def passthrough(_ctx, _dep=None):
        pass

    @op(output_defs=[DynamicOutputDefinition()])
    def emit():
        yield DynamicOutput(1, mapping_key="key_1")
        yield DynamicOutput(2, mapping_key="key_2")

    @graph
    def test_graph():
        emit().map(passthrough)

    assert test_graph.execute_in_process().success


class DangerNoodle(NamedTuple):
    x: int


@op(out={"items": DynamicOut(), "refs": Out()})
def spawn():
    for i in range(10):
        yield DynamicOutput(DangerNoodle(i), output_name="items", mapping_key=f"num_{i}")

    gc.collect()
    yield Output(len(objgraph.by_type("DangerNoodle")), output_name="refs")


@job()
def no_leaks_plz():
    spawn()


def test_dealloc_prev_outputs():
    # Ensure dynamic outputs can be used to chunk large data objects
    # by not holding any refs to previous outputs.
    # Things that will hold on to outputs:
    # * in process execution / mem io manager
    # * having hooks
    with instance_for_test() as inst:
        result = execute_pipeline(reconstructable(no_leaks_plz), instance=inst)
        assert result.success

        # there may be 1 still referenced by outer iteration frames
        assert result.output_for_solid("spawn", "refs") <= 1
