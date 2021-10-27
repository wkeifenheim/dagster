from dagster_airflow.dagster_pipeline_factory import make_dagster_pipeline_from_airflow_dag


def make_dagster_job_from_airflow_dag(
    dag, tags=None, use_airflow_template_context=False, unique_id=None
):
    """Construct a Dagster pipeline corresponding to a given Airflow DAG.

    Tasks in the resulting pipeline will execute the ``execute()`` method on the corresponding
    Airflow Operator. Dagster, any dependencies required by Airflow Operators, and the module
    containing your DAG definition must be available in the Python environment within which your
    Dagster solids execute.

    To set Airflow's ``execution_date`` for use with Airflow Operator's ``execute()`` methods,
    either:

    1. (Best for ad hoc runs) Execute job directly. This will set execution_date to the
        time (in UTC) of the run.

    2. Add ``{'airflow_execution_date': utc_date_string}`` to the job tags. This will override
        behavior from (1).

        .. code-block:: python

            execute_pipeline(
                make_dagster_job_from_airflow_dag(
                    dag=dag,
                    tags={'airflow_execution_date': utc_execution_date_str}
                )
            )

    3. (Recommended) Add ``{'airflow_execution_date': utc_date_string}`` to the run tags,
        such as in the Dagit UI. This will override behavior from (1) and (2)


    We apply normalized_name() to the dag id and task ids when generating job name and op
    names to ensure that names conform to Dagster's naming conventions.

    Args:
        dag (DAG): The Airflow DAG to compile into a Dagster job
        tags (Dict[str, Field]): Pipeline tags. Optionally include
            `tags={'airflow_execution_date': utc_date_string}` to specify execution_date used within
            execution of Airflow Operators.
        use_airflow_template_context (bool): If True, will call get_template_context() on the
            Airflow TaskInstance model which requires and modifies the DagRun table.
            (default: False)
        unique_id (int): If not None, this id will be postpended to generated op names. Used by
            framework authors to enforce unique op names within a repo.

    Returns:
        job_def (PipelineDefinition): The generated Dagster job

    """
    pipeline_def = make_dagster_pipeline_from_airflow_dag(
        dag, tags, use_airflow_template_context, unique_id
    )
    # pass in tags manually because pipeline_def.graph doesn't have it threaded
    return pipeline_def.graph.to_job(tags={**pipeline_def.tags})
