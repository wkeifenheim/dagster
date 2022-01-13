import {NetworkStatus, QueryResult} from '@apollo/client';
import {useCountdown, RefreshableCountdown} from '@dagster-io/ui';
import * as React from 'react';

interface Props<TData> {
  pollInterval: number;
  queryResult: QueryResult<TData, any>;
}

export const QueryCountdown = <TData extends Record<string, any>>(props: Props<TData>) => {
  const {pollInterval, queryResult} = props;
  const {networkStatus, refetch} = queryResult;

  const countdownStatus = networkStatus === NetworkStatus.ready ? 'counting' : 'idle';
  const timeRemaining = useCountdown({
    duration: pollInterval,
    status: countdownStatus,
  });
  const countdownRefreshing = countdownStatus === 'idle' || timeRemaining === 0;

  return (
    <RefreshableCountdown
      refreshing={countdownRefreshing}
      seconds={Math.floor(timeRemaining / 1000)}
      onRefresh={() => refetch()}
    />
  );
};
