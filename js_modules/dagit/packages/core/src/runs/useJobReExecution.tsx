import {useMutation} from '@apollo/client';
import * as React from 'react';
import {useLocation} from 'react-router';

import {AppContext} from '../app/AppContext';
import {showLaunchError} from '../launchpad/showLaunchError';
import {useRepositoryForRun} from '../workspace/useRepositoryForRun';

import {
  getReexecutionVariables,
  handleLaunchResult,
  LAUNCH_PIPELINE_REEXECUTION_MUTATION,
  ReExecutionStyle,
} from './RunUtils';
import {
  LaunchPipelineReexecution,
  LaunchPipelineReexecutionVariables,
} from './types/LaunchPipelineReexecution';
import {RunFragment} from './types/RunFragment';

export const useJobReExecution = (run: RunFragment | undefined | null) => {
  const {basePath} = React.useContext(AppContext);
  const [launchPipelineReexecution] = useMutation<
    LaunchPipelineReexecution,
    LaunchPipelineReexecutionVariables
  >(LAUNCH_PIPELINE_REEXECUTION_MUTATION);
  const repoMatch = useRepositoryForRun(run);
  const location = useLocation();

  return React.useCallback(
    async (style: ReExecutionStyle) => {
      if (!run || !run.pipelineSnapshotId || !repoMatch) {
        return;
      }

      const variables = getReexecutionVariables({
        run,
        style,
        repositoryLocationName: repoMatch.match.repositoryLocation.name,
        repositoryName: repoMatch.match.repository.name,
      });

      try {
        const result = await launchPipelineReexecution({variables});
        handleLaunchResult(basePath, run.pipelineName, result, {
          querystring: location.search,
        });
      } catch (error) {
        showLaunchError(error as Error);
      }
    },
    [basePath, launchPipelineReexecution, repoMatch, run, location.search],
  );
};
