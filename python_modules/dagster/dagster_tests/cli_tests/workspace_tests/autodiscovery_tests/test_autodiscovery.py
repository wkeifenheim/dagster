import os
import sys

import pytest
from dagster import DagsterInvariantViolationError, RepositoryDefinition
from dagster.core.code_pointer import CodePointer
from dagster.core.definitions.reconstructable import repository_def_from_pointer
from dagster.core.errors import DagsterImportError
from dagster.core.workspace.autodiscovery import (
    loadable_targets_from_python_file,
    loadable_targets_from_python_module,
    loadable_targets_from_python_package,
)
from dagster.utils import alter_sys_path, file_relative_path, restore_sys_modules


def test_single_repository():
    single_repo_path = file_relative_path(__file__, "single_repository.py")
    loadable_targets = loadable_targets_from_python_file(single_repo_path)

    assert len(loadable_targets) == 1
    symbol = loadable_targets[0].attribute
    assert symbol == "single_repository"

    repo_def = CodePointer.from_python_file(single_repo_path, symbol, None).load_target()
    isinstance(repo_def, RepositoryDefinition)
    assert repo_def.name == "single_repository"


def test_double_repository():
    loadable_repos = loadable_targets_from_python_file(
        file_relative_path(__file__, "double_repository.py"),
    )

    assert set([lr.target_definition.name for lr in loadable_repos]) == {"repo_one", "repo_two"}


def test_single_pipeline():
    single_pipeline_path = file_relative_path(__file__, "single_pipeline.py")
    loadable_targets = loadable_targets_from_python_file(single_pipeline_path)

    assert len(loadable_targets) == 1
    symbol = loadable_targets[0].attribute
    assert symbol == "a_pipeline"

    repo_def = repository_def_from_pointer(
        CodePointer.from_python_file(single_pipeline_path, symbol, None)
    )

    isinstance(repo_def, RepositoryDefinition)
    assert repo_def.get_pipeline("a_pipeline")


def test_double_pipeline():
    double_pipeline_path = file_relative_path(__file__, "double_pipeline.py")
    with pytest.raises(DagsterInvariantViolationError) as exc_info:
        loadable_targets_from_python_file(double_pipeline_path)

    assert str(exc_info.value) == (
        'No repository and more than one pipeline found in "double_pipeline". '
        "If you load a file or module directly it must have only one pipeline "
        "in scope. Found pipelines defined in variables or decorated "
        "functions: ['pipe_one', 'pipe_two']."
    )


def test_single_graph():
    single_graph_path = file_relative_path(__file__, "single_graph.py")
    loadable_targets = loadable_targets_from_python_file(single_graph_path)

    assert len(loadable_targets) == 1
    symbol = loadable_targets[0].attribute
    assert symbol == "graph_one"

    repo_def = repository_def_from_pointer(
        CodePointer.from_python_file(single_graph_path, symbol, None)
    )

    isinstance(repo_def, RepositoryDefinition)
    assert repo_def.get_pipeline("graph_one")


def test_double_graph():
    double_pipeline_path = file_relative_path(__file__, "double_graph.py")
    with pytest.raises(DagsterInvariantViolationError) as exc_info:
        loadable_targets_from_python_file(double_pipeline_path)

    assert str(exc_info.value) == (
        'No repository, job, or pipeline, and more than one graph found in "double_graph". '
        "If you load a file or module directly it must either have one repository, "
        "one job, one pipeline, or one graph in scope. Found graphs defined in variables or decorated "
        "functions: ['graph_one', 'graph_two']."
    )


def test_no_loadable_targets():
    with pytest.raises(DagsterInvariantViolationError) as exc_info:
        loadable_targets_from_python_file(file_relative_path(__file__, "nada.py"))

    assert str(exc_info.value) == 'No jobs, pipelines, graphs, or repositories found in "nada".'


def test_single_repository_in_module():
    loadable_targets = loadable_targets_from_python_module(
        "dagster.utils.test.toys.single_repository",
        working_directory=None,
    )
    assert len(loadable_targets) == 1
    symbol = loadable_targets[0].attribute
    assert symbol == "single_repository"

    repo_def = CodePointer.from_module(
        "dagster.utils.test.toys.single_repository", symbol, working_directory=None
    ).load_target()
    isinstance(repo_def, RepositoryDefinition)
    assert repo_def.name == "single_repository"


def test_single_repository_in_package():
    loadable_targets = loadable_targets_from_python_package(
        "dagster.utils.test.toys.single_repository",
        working_directory=None,
    )
    assert len(loadable_targets) == 1
    symbol = loadable_targets[0].attribute
    assert symbol == "single_repository"

    repo_def = CodePointer.from_python_package(
        "dagster.utils.test.toys.single_repository", symbol, working_directory=None
    ).load_target()
    isinstance(repo_def, RepositoryDefinition)
    assert repo_def.name == "single_repository"


def _current_test_directory_paths():
    # need to remove the current test directory when checking for module/package resolution.  we
    # have to manually remove the appropriate path from sys.path because pytest does a lot of
    # sys.path manipulation during auto-discovery of pytest files.
    #
    # Ordinarily, the working directory is just the first element in sys.path
    return [os.path.dirname(__file__)]


def test_local_directory_module():
    # this is testing that modules that *can* be resolved using the current working directory
    # for local python modules instead of installed packages will succeed.

    # pytest will insert the current directory onto the path when the current directory does is not
    # a module
    assert not os.path.exists(file_relative_path(__file__, "__init__.py"))
    assert os.path.dirname(__file__) in sys.path

    if "autodiscover_in_module" in sys.modules:
        del sys.modules["autodiscover_in_module"]

    with pytest.raises(DagsterImportError):
        loadable_targets_from_python_module(
            "complete_bogus_module",
            working_directory=os.path.dirname(__file__),
            remove_from_path_fn=_current_test_directory_paths,
        )

    with pytest.raises(DagsterImportError):
        loadable_targets_from_python_module(
            "autodiscover_in_module",
            working_directory=None,
            remove_from_path_fn=_current_test_directory_paths,
        )

    loadable_targets = loadable_targets_from_python_module(
        "autodiscover_in_module",
        working_directory=os.path.dirname(__file__),
        remove_from_path_fn=_current_test_directory_paths,
    )
    assert len(loadable_targets) == 1


def test_local_directory_file():
    path = file_relative_path(__file__, "autodiscover_file_in_directory/repository.py")

    with restore_sys_modules():
        with pytest.raises(DagsterImportError) as exc_info:
            loadable_targets_from_python_file(path)

        assert "No module named 'autodiscover_src'" in str(exc_info.value)

    with alter_sys_path(to_add=[os.path.dirname(path)], to_remove=[]):
        loadable_targets_from_python_file(path, working_directory=os.path.dirname(path))
