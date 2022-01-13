import {gql} from '@apollo/client';
import {
  Box,
  CursorHistoryControls,
  NonIdealState,
  Page,
  TagWIP,
  TokenizingFieldValue,
} from '@dagster-io/ui';
import * as React from 'react';
import {useParams} from 'react-router-dom';

import {QueryCountdown} from '../app/QueryCountdown';
import {RunTable, RUN_TABLE_RUN_FRAGMENT} from '../runs/RunTable';
import {RunsQueryRefetchContext} from '../runs/RunUtils';
import {
  RunFilterTokenType,
  RunsFilterInput,
  runsFilterForSearchTokens,
  useQueryPersistedRunFilters,
} from '../runs/RunsFilterInput';
import {POLL_INTERVAL, useCursorPaginatedQuery} from '../runs/useCursorPaginatedQuery';
import {Loading} from '../ui/Loading';
import {isThisThingAJob, useRepository} from '../workspace/WorkspaceContext';
import {RepoAddress} from '../workspace/types';

import {explorerPathFromString} from './PipelinePathUtils';
import {PipelineRunsRootQuery, PipelineRunsRootQueryVariables} from './types/PipelineRunsRootQuery';
import {useJobTitle} from './useJobTitle';

const PAGE_SIZE = 25;
const ENABLED_FILTERS: RunFilterTokenType[] = ['status', 'tag'];

interface Props {
  repoAddress?: RepoAddress;
}

export const PipelineRunsRoot: React.FC<Props> = (props) => {
  const {pipelinePath} = useParams<{pipelinePath: string}>();
  const {repoAddress = null} = props;
  const explorerPath = explorerPathFromString(pipelinePath);
  const {pipelineName, snapshotId} = explorerPath;

  const repo = useRepository(repoAddress);
  const isJob = isThisThingAJob(repo, pipelineName);

  useJobTitle(explorerPath, isJob);

  const [filterTokens, setFilterTokens] = useQueryPersistedRunFilters(ENABLED_FILTERS);
  const permanentTokens = React.useMemo(() => {
    return [
      isJob ? {token: 'job', value: pipelineName} : {token: 'pipeline', value: pipelineName},
      snapshotId ? {token: 'snapshotId', value: snapshotId} : null,
    ].filter(Boolean) as TokenizingFieldValue[];
  }, [isJob, pipelineName, snapshotId]);

  const allTokens = [...filterTokens, ...permanentTokens];

  const {queryResult, paginationProps} = useCursorPaginatedQuery<
    PipelineRunsRootQuery,
    PipelineRunsRootQueryVariables
  >({
    query: PIPELINE_RUNS_ROOT_QUERY,
    pageSize: PAGE_SIZE,
    variables: {
      filter: {...runsFilterForSearchTokens(allTokens), pipelineName, snapshotId},
    },
    nextCursorForResult: (runs) => {
      if (runs.pipelineRunsOrError.__typename !== 'Runs') {
        return undefined;
      }
      return runs.pipelineRunsOrError.results[PAGE_SIZE - 1]?.runId;
    },
    getResultArray: (data) => {
      if (!data || data.pipelineRunsOrError.__typename !== 'Runs') {
        return [];
      }
      return data.pipelineRunsOrError.results;
    },
  });

  return (
    <RunsQueryRefetchContext.Provider value={{refetch: queryResult.refetch}}>
      <Page>
        <Loading queryResult={queryResult} allowStaleData={true}>
          {({pipelineRunsOrError}) => {
            if (pipelineRunsOrError.__typename !== 'Runs') {
              return (
                <Box padding={{vertical: 64}}>
                  <NonIdealState
                    icon="error"
                    title="Query Error"
                    description={pipelineRunsOrError.message}
                  />
                </Box>
              );
            }
            const runs = pipelineRunsOrError.results;
            const displayed = runs.slice(0, PAGE_SIZE);
            const {hasNextCursor, hasPrevCursor} = paginationProps;
            return (
              <>
                <Box
                  flex={{alignItems: 'flex-start', justifyContent: 'space-between'}}
                  padding={{top: 8, horizontal: 24}}
                >
                  <Box flex={{direction: 'row', gap: 8}}>
                    {permanentTokens.map(({token, value}) => (
                      <TagWIP key={token}>{`${token}:${value}`}</TagWIP>
                    ))}
                  </Box>
                  <QueryCountdown pollInterval={POLL_INTERVAL} queryResult={queryResult} />
                </Box>
                <RunTable
                  runs={displayed}
                  onSetFilter={setFilterTokens}
                  actionBarComponents={
                    <RunsFilterInput
                      enabledFilters={ENABLED_FILTERS}
                      tokens={filterTokens}
                      onChange={setFilterTokens}
                      loading={queryResult.loading}
                    />
                  }
                />
                {hasNextCursor || hasPrevCursor ? (
                  <div style={{marginTop: '20px'}}>
                    <CursorHistoryControls {...paginationProps} />
                  </div>
                ) : null}
              </>
            );
          }}
        </Loading>
      </Page>
    </RunsQueryRefetchContext.Provider>
  );
};

const PIPELINE_RUNS_ROOT_QUERY = gql`
  query PipelineRunsRootQuery($limit: Int, $cursor: String, $filter: RunsFilter!) {
    pipelineRunsOrError(limit: $limit, cursor: $cursor, filter: $filter) {
      ... on Runs {
        results {
          id
          ...RunTableRunFragment
        }
      }
      ... on InvalidPipelineRunsFilterError {
        message
      }
      ... on PythonError {
        message
      }
    }
  }

  ${RUN_TABLE_RUN_FRAGMENT}
`;
