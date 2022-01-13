/* tslint:disable */
/* eslint-disable */
// @generated
// This file was automatically generated and should not be edited.

import { RunStatus } from "./../../types/globalTypes";

// ====================================================
// GraphQL query operation: LastTenRunsPerJobQuery
// ====================================================

export interface LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_RepositoryLocation_repositories_pipelines_runs_stats_RunStatsSnapshot {
  __typename: "RunStatsSnapshot";
  id: string;
  enqueuedTime: number | null;
  launchTime: number | null;
  startTime: number | null;
  endTime: number | null;
}

export interface LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_RepositoryLocation_repositories_pipelines_runs_stats_PythonError_cause {
  __typename: "PythonError";
  message: string;
  stack: string[];
}

export interface LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_RepositoryLocation_repositories_pipelines_runs_stats_PythonError {
  __typename: "PythonError";
  message: string;
  stack: string[];
  cause: LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_RepositoryLocation_repositories_pipelines_runs_stats_PythonError_cause | null;
}

export type LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_RepositoryLocation_repositories_pipelines_runs_stats = LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_RepositoryLocation_repositories_pipelines_runs_stats_RunStatsSnapshot | LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_RepositoryLocation_repositories_pipelines_runs_stats_PythonError;

export interface LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_RepositoryLocation_repositories_pipelines_runs {
  __typename: "Run";
  id: string;
  runId: string;
  status: RunStatus;
  stats: LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_RepositoryLocation_repositories_pipelines_runs_stats;
}

export interface LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_RepositoryLocation_repositories_pipelines {
  __typename: "Pipeline";
  id: string;
  name: string;
  isJob: boolean;
  runs: LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_RepositoryLocation_repositories_pipelines_runs[];
}

export interface LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_RepositoryLocation_repositories {
  __typename: "Repository";
  id: string;
  name: string;
  pipelines: LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_RepositoryLocation_repositories_pipelines[];
}

export interface LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_RepositoryLocation {
  __typename: "RepositoryLocation";
  id: string;
  name: string;
  repositories: LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_RepositoryLocation_repositories[];
}

export interface LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_PythonError_cause {
  __typename: "PythonError";
  message: string;
  stack: string[];
}

export interface LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_PythonError {
  __typename: "PythonError";
  message: string;
  stack: string[];
  cause: LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_PythonError_cause | null;
}

export type LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError = LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_RepositoryLocation | LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError_PythonError;

export interface LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries {
  __typename: "WorkspaceLocationEntry";
  id: string;
  locationOrLoadError: LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries_locationOrLoadError | null;
}

export interface LastTenRunsPerJobQuery_workspaceOrError_Workspace {
  __typename: "Workspace";
  locationEntries: LastTenRunsPerJobQuery_workspaceOrError_Workspace_locationEntries[];
}

export interface LastTenRunsPerJobQuery_workspaceOrError_PythonError_cause {
  __typename: "PythonError";
  message: string;
  stack: string[];
}

export interface LastTenRunsPerJobQuery_workspaceOrError_PythonError {
  __typename: "PythonError";
  message: string;
  stack: string[];
  cause: LastTenRunsPerJobQuery_workspaceOrError_PythonError_cause | null;
}

export type LastTenRunsPerJobQuery_workspaceOrError = LastTenRunsPerJobQuery_workspaceOrError_Workspace | LastTenRunsPerJobQuery_workspaceOrError_PythonError;

export interface LastTenRunsPerJobQuery {
  workspaceOrError: LastTenRunsPerJobQuery_workspaceOrError;
}
