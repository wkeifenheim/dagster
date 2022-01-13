/* tslint:disable */
/* eslint-disable */
// @generated
// This file was automatically generated and should not be edited.

import { RunStatus } from "./../../types/globalTypes";

// ====================================================
// GraphQL fragment: RunTimeFragment
// ====================================================

export interface RunTimeFragment_stats_RunStatsSnapshot {
  __typename: "RunStatsSnapshot";
  id: string;
  enqueuedTime: number | null;
  launchTime: number | null;
  startTime: number | null;
  endTime: number | null;
}

export interface RunTimeFragment_stats_PythonError_cause {
  __typename: "PythonError";
  message: string;
  stack: string[];
}

export interface RunTimeFragment_stats_PythonError {
  __typename: "PythonError";
  message: string;
  stack: string[];
  cause: RunTimeFragment_stats_PythonError_cause | null;
}

export type RunTimeFragment_stats = RunTimeFragment_stats_RunStatsSnapshot | RunTimeFragment_stats_PythonError;

export interface RunTimeFragment {
  __typename: "Run";
  id: string;
  runId: string;
  status: RunStatus;
  stats: RunTimeFragment_stats;
}
