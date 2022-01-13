/* tslint:disable */
/* eslint-disable */
// @generated
// This file was automatically generated and should not be edited.

import { PipelineSelector, RunsFilter, InstigationStatus, RunStatus } from "./../../types/globalTypes";

// ====================================================
// GraphQL query operation: JobMetadataQuery
// ====================================================

export interface JobMetadataQuery_pipelineOrError_PipelineNotFoundError {
  __typename: "PipelineNotFoundError" | "InvalidSubsetError" | "PythonError";
}

export interface JobMetadataQuery_pipelineOrError_Pipeline_schedules_scheduleState {
  __typename: "InstigationState";
  id: string;
  status: InstigationStatus;
}

export interface JobMetadataQuery_pipelineOrError_Pipeline_schedules {
  __typename: "Schedule";
  id: string;
  mode: string;
  name: string;
  cronSchedule: string;
  scheduleState: JobMetadataQuery_pipelineOrError_Pipeline_schedules_scheduleState;
}

export interface JobMetadataQuery_pipelineOrError_Pipeline_sensors_targets {
  __typename: "Target";
  pipelineName: string;
  mode: string;
}

export interface JobMetadataQuery_pipelineOrError_Pipeline_sensors_sensorState {
  __typename: "InstigationState";
  id: string;
  status: InstigationStatus;
}

export interface JobMetadataQuery_pipelineOrError_Pipeline_sensors {
  __typename: "Sensor";
  id: string;
  targets: JobMetadataQuery_pipelineOrError_Pipeline_sensors_targets[] | null;
  jobOriginId: string;
  name: string;
  sensorState: JobMetadataQuery_pipelineOrError_Pipeline_sensors_sensorState;
}

export interface JobMetadataQuery_pipelineOrError_Pipeline {
  __typename: "Pipeline";
  id: string;
  isJob: boolean;
  name: string;
  schedules: JobMetadataQuery_pipelineOrError_Pipeline_schedules[];
  sensors: JobMetadataQuery_pipelineOrError_Pipeline_sensors[];
}

export type JobMetadataQuery_pipelineOrError = JobMetadataQuery_pipelineOrError_PipelineNotFoundError | JobMetadataQuery_pipelineOrError_Pipeline;

export interface JobMetadataQuery_pipelineRunsOrError_InvalidPipelineRunsFilterError {
  __typename: "InvalidPipelineRunsFilterError" | "PythonError";
}

export interface JobMetadataQuery_pipelineRunsOrError_Runs_results_assets_key {
  __typename: "AssetKey";
  path: string[];
}

export interface JobMetadataQuery_pipelineRunsOrError_Runs_results_assets {
  __typename: "Asset";
  id: string;
  key: JobMetadataQuery_pipelineRunsOrError_Runs_results_assets_key;
}

export interface JobMetadataQuery_pipelineRunsOrError_Runs_results_stats_RunStatsSnapshot {
  __typename: "RunStatsSnapshot";
  id: string;
  enqueuedTime: number | null;
  launchTime: number | null;
  startTime: number | null;
  endTime: number | null;
}

export interface JobMetadataQuery_pipelineRunsOrError_Runs_results_stats_PythonError_cause {
  __typename: "PythonError";
  message: string;
  stack: string[];
}

export interface JobMetadataQuery_pipelineRunsOrError_Runs_results_stats_PythonError {
  __typename: "PythonError";
  message: string;
  stack: string[];
  cause: JobMetadataQuery_pipelineRunsOrError_Runs_results_stats_PythonError_cause | null;
}

export type JobMetadataQuery_pipelineRunsOrError_Runs_results_stats = JobMetadataQuery_pipelineRunsOrError_Runs_results_stats_RunStatsSnapshot | JobMetadataQuery_pipelineRunsOrError_Runs_results_stats_PythonError;

export interface JobMetadataQuery_pipelineRunsOrError_Runs_results {
  __typename: "Run";
  id: string;
  status: RunStatus;
  assets: JobMetadataQuery_pipelineRunsOrError_Runs_results_assets[];
  runId: string;
  stats: JobMetadataQuery_pipelineRunsOrError_Runs_results_stats;
}

export interface JobMetadataQuery_pipelineRunsOrError_Runs {
  __typename: "Runs";
  results: JobMetadataQuery_pipelineRunsOrError_Runs_results[];
}

export type JobMetadataQuery_pipelineRunsOrError = JobMetadataQuery_pipelineRunsOrError_InvalidPipelineRunsFilterError | JobMetadataQuery_pipelineRunsOrError_Runs;

export interface JobMetadataQuery {
  pipelineOrError: JobMetadataQuery_pipelineOrError;
  pipelineRunsOrError: JobMetadataQuery_pipelineRunsOrError;
}

export interface JobMetadataQueryVariables {
  params: PipelineSelector;
  runsFilter?: RunsFilter | null;
}
