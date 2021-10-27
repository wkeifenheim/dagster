# pylint doesn't understand pytest fixtures
# pylint: disable=unused-argument

import pytest
from click.testing import CliRunner
from dagster_airflow.cli import scaffold
from dagster_airflow_tests.marks import requires_airflow_db


@requires_airflow_db
@pytest.mark.parametrize(
    "cli_args",
    [
        ["--module-name", "dagster_test.toys.log_spew", "--pipeline-name", "log_spew"],
        ["--module-name", "dagster_test.toys.many_events", "--pipeline-name", "many_events"],
        [
            "--module-name",
            "dagster_test.toys.error_monster",
            "--preset",
            "passing",
            "--pipeline-name",
            "error_monster",
        ],
        [
            "--module-name",
            "dagster_test.toys.resources",
            "--pipeline-name",
            "resource_pipeline",
        ],
        ["--module-name", "dagster_test.graph_job_op_toys.log_spew", "--job-name", "log_spew"],
        [
            "--module-name",
            "dagster_test.graph_job_op_toys.many_events",
            "--job-name",
            "many_events",
        ],
    ],
)
def test_build_dags(clean_airflow_home, cli_args):
    """This test generates Airflow DAGs for several pipelines in examples/toys and writes those DAGs
    to $AIRFLOW_HOME/dags.

    By invoking DagBag() below, an Airflow DAG refresh is triggered. If there are any failures in
    DAG parsing, DagBag() will add an entry to its import_errors property.

    By exercising this path, we ensure that our codegen continues to generate valid Airflow DAGs,
    and that Airflow is able to successfully parse our DAGs.
    """
    runner = CliRunner()

    runner.invoke(scaffold, cli_args)

    # This forces Airflow to refresh DAGs; see https://stackoverflow.com/a/50356956/11295366
    from airflow.models import DagBag

    dag_bag = DagBag()

    # If Airflow hits an import error, it will add an entry to this dict.
    assert not dag_bag.import_errors

    assert cli_args[-1] in dag_bag.dags
