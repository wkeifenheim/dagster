import json
import time
import uuid

from dagster.core.storage.pipeline_run import PipelineRunsFilter
from dagster.utils import file_relative_path
from dagster.utils.test import get_temp_file_name
from dagster_graphql.client.query import (
    LAUNCH_PIPELINE_EXECUTION_MUTATION,
    RUN_EVENTS_QUERY,
    SUBSCRIPTION_QUERY,
)
from dagster_graphql.test.utils import execute_dagster_graphql, infer_pipeline_selector
from graphql import parse

from .graphql_context_test_suite import (
    ExecutingGraphQLContextTestMatrix,
    ReadonlyGraphQLContextTestMatrix,
)
from .setup import csv_hello_world_solids_config
from .utils import sync_execute_get_run_log_data


class TestExecutePipeline(ExecutingGraphQLContextTestMatrix):
    def test_start_pipeline_execution(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "csv_hello_world")
        result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                    "runConfigData": csv_hello_world_solids_config(),
                    "mode": "default",
                }
            },
        )

        assert not result.errors
        assert result.data

        # just test existence
        assert result.data["launchPipelineExecution"]["__typename"] == "LaunchRunSuccess"
        assert uuid.UUID(result.data["launchPipelineExecution"]["run"]["runId"])
        assert (
            result.data["launchPipelineExecution"]["run"]["pipeline"]["name"] == "csv_hello_world"
        )

    def test_start_pipeline_execution_serialized_config(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "csv_hello_world")
        result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                    "runConfigData": json.dumps(csv_hello_world_solids_config()),
                    "mode": "default",
                }
            },
        )

        assert not result.errors
        assert result.data

        # just test existence
        assert result.data["launchPipelineExecution"]["__typename"] == "LaunchRunSuccess"
        assert uuid.UUID(result.data["launchPipelineExecution"]["run"]["runId"])
        assert (
            result.data["launchPipelineExecution"]["run"]["pipeline"]["name"] == "csv_hello_world"
        )

    def test_start_pipeline_execution_malformed_config(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "csv_hello_world")
        result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                    "runConfigData": '{"foo": {{{{',
                    "mode": "default",
                }
            },
        )

        assert not result.errors
        assert result.data

        assert result.data["launchPipelineExecution"]["__typename"] == "PythonError"
        assert "JSONDecodeError" in result.data["launchPipelineExecution"]["message"]

    def test_basic_start_pipeline_execution_with_preset(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "csv_hello_world")
        result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                    "preset": "test_inline",
                }
            },
        )

        assert not result.errors
        assert result.data

        # just test existence
        assert result.data["launchPipelineExecution"]["__typename"] == "LaunchRunSuccess"
        assert uuid.UUID(result.data["launchPipelineExecution"]["run"]["runId"])
        assert (
            result.data["launchPipelineExecution"]["run"]["pipeline"]["name"] == "csv_hello_world"
        )

    def test_basic_start_pipeline_execution_with_pipeline_def_tags(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "hello_world_with_tags")
        result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                    "mode": "default",
                },
            },
        )

        assert not result.errors
        assert result.data["launchPipelineExecution"]["run"]["tags"] == [
            {"key": "tag_key", "value": "tag_value"}
        ]

        # just test existence
        assert result.data["launchPipelineExecution"]["__typename"] == "LaunchRunSuccess"
        assert uuid.UUID(result.data["launchPipelineExecution"]["run"]["runId"])
        assert (
            result.data["launchPipelineExecution"]["run"]["pipeline"]["name"]
            == "hello_world_with_tags"
        )

        # ensure provided tags override def tags
        result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                    "mode": "default",
                    "executionMetadata": {
                        "tags": [{"key": "tag_key", "value": "new_tag_value"}],
                    },
                },
            },
        )

        assert not result.errors
        assert result.data["launchPipelineExecution"]["run"]["tags"] == [
            {"key": "tag_key", "value": "new_tag_value"}
        ]

    def test_basic_start_pipeline_execution_with_non_existent_preset(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "csv_hello_world")

        result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                    "preset": "undefined_preset",
                }
            },
        )

        assert not result.errors
        assert result.data
        assert result.data["launchPipelineExecution"]["__typename"] == "PresetNotFoundError"
        assert (
            result.data["launchPipelineExecution"]["message"]
            == "Preset undefined_preset not found in pipeline csv_hello_world."
        )

    def test_basic_start_pipeline_execution_with_preset_failure(self, graphql_context):
        subset_selector = infer_pipeline_selector(
            graphql_context, "csv_hello_world", ["sum_sq_solid"]
        )

        result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": subset_selector,
                    "preset": "test_inline",
                }
            },
        )

        # while illegally defining selector.solid_selection
        assert not result.errors
        assert result.data
        assert (
            result.data["launchPipelineExecution"]["__typename"]
            == "ConflictingExecutionParamsError"
        )
        assert (
            result.data["launchPipelineExecution"]["message"]
            == "Invalid ExecutionParams. Cannot define selector.solid_selection when using a preset."
        )

        # while illegally defining runConfigData
        selector = infer_pipeline_selector(graphql_context, "csv_hello_world")
        result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                    "preset": "test_inline",
                    "runConfigData": csv_hello_world_solids_config(),
                }
            },
        )

        assert not result.errors
        assert result.data
        assert (
            result.data["launchPipelineExecution"]["__typename"]
            == "ConflictingExecutionParamsError"
        )
        assert (
            result.data["launchPipelineExecution"]["message"]
            == "Invalid ExecutionParams. Cannot define runConfigData when using a preset."
        )

        # while illegally defining mode
        result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                    "preset": "test_inline",
                    "mode": "default",
                }
            },
        )

        assert not result.errors
        assert result.data
        assert (
            result.data["launchPipelineExecution"]["__typename"]
            == "ConflictingExecutionParamsError"
        )
        assert (
            result.data["launchPipelineExecution"]["message"]
            == "Invalid ExecutionParams. Cannot define mode when using a preset."
        )

    def test_basic_start_pipeline_execution_config_failure(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "csv_hello_world")
        result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                    "runConfigData": {"solids": {"sum_solid": {"inputs": {"num": 384938439}}}},
                    "mode": "default",
                }
            },
        )

        assert not result.errors
        assert result.data
        assert result.data["launchPipelineExecution"]["__typename"] == "RunConfigValidationInvalid"

    def test_basis_start_pipeline_not_found_error(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "sjkdfkdjkf")
        result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                    "runConfigData": {"solids": {"sum_solid": {"inputs": {"num": "test.csv"}}}},
                    "mode": "default",
                }
            },
        )

        assert not result.errors
        assert result.data

        # just test existence
        assert result.data["launchPipelineExecution"]["__typename"] == "PipelineNotFoundError"
        assert result.data["launchPipelineExecution"]["pipelineName"] == "sjkdfkdjkf"

    def _csv_hello_world_event_sequence(self):
        # expected non engine event sequence from executing csv_hello_world pipeline
        return [
            "RunStartingEvent",
            "RunStartEvent",
            "LogsCapturedEvent",
            "ExecutionStepStartEvent",
            "ExecutionStepInputEvent",
            "ExecutionStepOutputEvent",
            "LogMessageEvent",
            "HandledOutputEvent",
            "ExecutionStepSuccessEvent",
            "LogsCapturedEvent",
            "ExecutionStepStartEvent",
            "LogMessageEvent",
            "LoadedInputEvent",
            "ExecutionStepInputEvent",
            "ExecutionStepOutputEvent",
            "LogMessageEvent",
            "HandledOutputEvent",
            "ExecutionStepSuccessEvent",
            "RunSuccessEvent",
        ]

    def test_basic_start_pipeline_execution_and_subscribe(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "csv_hello_world")
        run_logs = sync_execute_get_run_log_data(
            context=graphql_context,
            variables={
                "executionParams": {
                    "selector": selector,
                    "runConfigData": {
                        "solids": {
                            "sum_solid": {
                                "inputs": {"num": file_relative_path(__file__, "../data/num.csv")}
                            }
                        }
                    },
                    "mode": "default",
                }
            },
        )

        assert run_logs["__typename"] == "PipelineRunLogsSubscriptionSuccess"
        non_engine_event_types = [
            message["__typename"]
            for message in run_logs["messages"]
            if message["__typename"] != "EngineEvent"
        ]

        assert non_engine_event_types == self._csv_hello_world_event_sequence()

    def test_basic_start_pipeline_and_fetch(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "csv_hello_world")
        exc_result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                    "runConfigData": {
                        "solids": {
                            "sum_solid": {
                                "inputs": {"num": file_relative_path(__file__, "../data/num.csv")}
                            }
                        }
                    },
                    "mode": "default",
                }
            },
        )

        assert not exc_result.errors
        assert exc_result.data
        assert exc_result.data["launchPipelineExecution"]["__typename"] == "LaunchRunSuccess"

        # block until run finishes
        graphql_context.instance.run_launcher.join()

        events_result = execute_dagster_graphql(
            graphql_context,
            RUN_EVENTS_QUERY,
            variables={"runId": exc_result.data["launchPipelineExecution"]["run"]["runId"]},
        )

        assert not events_result.errors
        assert events_result.data
        assert events_result.data["pipelineRunOrError"]["__typename"] == "Run"

        non_engine_event_types = [
            message["__typename"]
            for message in events_result.data["pipelineRunOrError"]["events"]
            if message["__typename"] != "EngineEvent"
        ]
        assert non_engine_event_types == self._csv_hello_world_event_sequence()

    def test_basic_start_pipeline_and_poll(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "csv_hello_world")
        exc_result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                    "runConfigData": {
                        "solids": {
                            "sum_solid": {
                                "inputs": {"num": file_relative_path(__file__, "../data/num.csv")}
                            }
                        }
                    },
                    "mode": "default",
                }
            },
        )

        assert not exc_result.errors
        assert exc_result.data
        assert exc_result.data["launchPipelineExecution"]["__typename"] == "LaunchRunSuccess"

        def _fetch_events(after):
            events_result = execute_dagster_graphql(
                graphql_context,
                RUN_EVENTS_QUERY,
                variables={
                    "runId": exc_result.data["launchPipelineExecution"]["run"]["runId"],
                    "after": after,
                },
            )
            assert not events_result.errors
            assert events_result.data
            assert events_result.data["pipelineRunOrError"]["__typename"] == "Run"
            return events_result.data["pipelineRunOrError"]["events"]

        full_logs = []
        cursor = -1
        iters = 0

        # do 3 polls, then fetch after waiting for execution to finish
        while iters < 3:
            full_logs.extend(_fetch_events(cursor))
            cursor = len(full_logs) - 1
            iters += 1
            time.sleep(0.05)  # 50ms

        # block until run finishes
        graphql_context.instance.run_launcher.join()
        full_logs.extend(_fetch_events(cursor))

        non_engine_event_types = [
            message["__typename"] for message in full_logs if message["__typename"] != "EngineEvent"
        ]
        assert non_engine_event_types == self._csv_hello_world_event_sequence()

    def test_subscription_query_error(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "naughty_programmer_pipeline")
        run_logs = sync_execute_get_run_log_data(
            context=graphql_context,
            variables={
                "executionParams": {
                    "selector": selector,
                    "mode": "default",
                }
            },
        )

        assert run_logs["__typename"] == "PipelineRunLogsSubscriptionSuccess"

        step_run_log_entry = _get_step_run_log_entry(
            run_logs, "throw_a_thing", "ExecutionStepFailureEvent"
        )

        assert step_run_log_entry
        # Confirm that it is the user stack

        assert step_run_log_entry["message"] == 'Execution of step "throw_a_thing" failed.'
        assert step_run_log_entry["error"]
        assert step_run_log_entry["level"] == "ERROR"
        assert isinstance(step_run_log_entry["error"]["cause"]["stack"], list)

        assert "bad programmer" in step_run_log_entry["error"]["cause"]["stack"][-1]

    def test_subscribe_bad_run_id(self, graphql_context):
        run_id = "nope"
        subscription = execute_dagster_graphql(
            graphql_context, parse(SUBSCRIPTION_QUERY), variables={"runId": run_id}
        )

        subscribe_results = []
        subscription.subscribe(subscribe_results.append)

        assert len(subscribe_results) == 1
        subscribe_result = subscribe_results[0]

        assert (
            subscribe_result.data["pipelineRunLogs"]["__typename"]
            == "PipelineRunLogsSubscriptionFailure"
        )
        assert subscribe_result.data["pipelineRunLogs"]["missingRunId"] == "nope"

    def test_basic_sync_execution_no_config(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "no_config_pipeline")
        result = sync_execute_get_run_log_data(
            context=graphql_context,
            variables={
                "executionParams": {
                    "selector": selector,
                    "runConfigData": None,
                    "mode": "default",
                }
            },
        )
        logs = result["messages"]
        assert isinstance(logs, list)
        assert has_event_of_type(logs, "RunStartEvent")
        assert has_event_of_type(logs, "RunSuccessEvent")
        assert not has_event_of_type(logs, "RunFailureEvent")

    def test_basic_filesystem_sync_execution(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "csv_hello_world")
        result = sync_execute_get_run_log_data(
            context=graphql_context,
            variables={
                "executionParams": {
                    "selector": selector,
                    "runConfigData": csv_hello_world_solids_config(),
                    "mode": "default",
                }
            },
        )

        logs = result["messages"]
        assert isinstance(logs, list)
        assert has_event_of_type(logs, "RunStartEvent")
        assert has_event_of_type(logs, "RunSuccessEvent")
        assert not has_event_of_type(logs, "RunFailureEvent")

        assert first_event_of_type(logs, "RunStartEvent")["level"] == "DEBUG"

        sum_solid_output = get_step_output_event(logs, "sum_solid")
        assert sum_solid_output["stepKey"] == "sum_solid"
        assert sum_solid_output["outputName"] == "result"

    def test_basic_start_pipeline_execution_with_tags(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "csv_hello_world")
        result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                    "runConfigData": csv_hello_world_solids_config(),
                    "executionMetadata": {
                        "tags": [{"key": "dagster/test_key", "value": "test_value"}]
                    },
                    "mode": "default",
                }
            },
        )

        assert not result.errors
        assert result.data
        assert result.data["launchPipelineExecution"]["__typename"] == "LaunchRunSuccess"

        run = result.data["launchPipelineExecution"]["run"]
        run_id = run["runId"]
        assert len(run["tags"]) > 0
        assert any(
            [x["key"] == "dagster/test_key" and x["value"] == "test_value" for x in run["tags"]]
        )

        # Check run storage
        runs_with_tag = graphql_context.instance.get_runs(
            filters=PipelineRunsFilter(tags={"dagster/test_key": "test_value"})
        )
        assert len(runs_with_tag) == 1
        assert runs_with_tag[0].run_id == run_id

    def test_basic_start_pipeline_execution_with_materialization(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "csv_hello_world")

        with get_temp_file_name() as out_csv_path:

            run_config = {
                "solids": {
                    "sum_solid": {
                        "inputs": {"num": file_relative_path(__file__, "../data/num.csv")},
                        "outputs": [{"result": out_csv_path}],
                    }
                }
            }

            run_logs = sync_execute_get_run_log_data(
                context=graphql_context,
                variables={
                    "executionParams": {
                        "selector": selector,
                        "runConfigData": run_config,
                        "mode": "default",
                    }
                },
            )

            step_mat_event = None

            for message in run_logs["messages"]:
                if message["__typename"] == "StepMaterializationEvent":
                    # ensure only one event
                    assert step_mat_event is None
                    step_mat_event = message

            # ensure only one event
            assert step_mat_event
            assert len(step_mat_event["materialization"]["metadataEntries"]) == 1
            assert step_mat_event["materialization"]["metadataEntries"][0]["path"] == out_csv_path

    def test_start_job_execution_with_default_config(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "job_with_default_config")
        result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                }
            },
        )
        # should succeed for this job, even when not providing config because it should
        # pick up the job default run_config
        assert not result.errors
        assert result.data
        assert result.data["launchPipelineExecution"]["__typename"] == "LaunchRunSuccess"

    def test_pipeline_execution_fails_no_mode(self, graphql_context):
        selector = infer_pipeline_selector(graphql_context, "multi_mode_with_resources")
        result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                }
            },
        )

        assert not result.errors
        assert result.data
        assert result.data["launchPipelineExecution"]["__typename"] == "NoModeProvidedError"

    def test_two_ins_job_subset_and_config(self, graphql_context):
        selector = infer_pipeline_selector(
            graphql_context, "two_ins_job", ["op_1", "op_with_2_ins"]
        )
        run_config = {
            "ops": {"op_with_2_ins": {"inputs": {"in_2": {"value": 2}}}},
        }
        result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                    "runConfigData": run_config,
                    "mode": "default",
                }
            },
        )
        assert not result.errors
        assert result.data
        assert result.data["launchPipelineExecution"]["__typename"] == "LaunchRunSuccess"
        assert set(result.data["launchPipelineExecution"]["run"]["resolvedOpSelection"]) == set(
            [
                "op_1",
                "op_with_2_ins",
            ]
        )


def _get_step_run_log_entry(pipeline_run_logs, step_key, typename):
    for message_data in pipeline_run_logs["messages"]:
        if message_data["__typename"] == typename:
            if message_data["stepKey"] == step_key:
                return message_data


def first_event_of_type(logs, message_type):
    for log in logs:
        if log["__typename"] == message_type:
            return log
    return None


def has_event_of_type(logs, message_type):
    return first_event_of_type(logs, message_type) is not None


def get_step_output_event(logs, step_key, output_name="result"):
    for log in logs:
        if (
            log["__typename"] == "ExecutionStepOutputEvent"
            and log["stepKey"] == step_key
            and log["outputName"] == output_name
        ):
            return log

    return None


class TestExecutePipelineReadonlyFailure(ReadonlyGraphQLContextTestMatrix):
    def test_start_pipeline_execution_readonly_failure(self, graphql_context):
        assert graphql_context.read_only == True

        selector = infer_pipeline_selector(graphql_context, "csv_hello_world")
        result = execute_dagster_graphql(
            graphql_context,
            LAUNCH_PIPELINE_EXECUTION_MUTATION,
            variables={
                "executionParams": {
                    "selector": selector,
                    "runConfigData": csv_hello_world_solids_config(),
                    "mode": "default",
                }
            },
        )

        assert not result.errors
        assert result.data

        assert result.data["launchPipelineExecution"]["__typename"] == "UnauthorizedError"
