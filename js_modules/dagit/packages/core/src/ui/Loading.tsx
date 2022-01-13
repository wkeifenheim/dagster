import {QueryResult} from '@apollo/client';
import {Box, NonIdealState, Spinner} from '@dagster-io/ui';
import * as React from 'react';

interface ILoadingProps<TData> {
  queryResult: QueryResult<TData, any>;
  children: (data: TData) => React.ReactNode;
  allowStaleData?: boolean;
  purpose: 'section' | 'page';
}

const BLANK_LOADING_DELAY_MSEC = 500;

export const Loading = <TData extends Record<string, any>>(props: ILoadingProps<TData>) => {
  const {children, purpose, allowStaleData = false} = props;
  const {error, data, loading} = props.queryResult;

  const [blankLoading, setBlankLoading] = React.useState(true);
  const isLoading = !data || (loading && !allowStaleData) || Object.keys(data as any).length === 0;

  React.useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;

    // Wait a brief moment so that we don't awkwardly flash the loading bar.
    // This is often enough time for data to become available.
    if (isLoading) {
      timer = setTimeout(() => setBlankLoading(false), BLANK_LOADING_DELAY_MSEC);
    } else {
      setBlankLoading(true);
    }

    return () => {
      timer && clearTimeout(timer);
    };
  }, [isLoading]);

  // either error.networkError or error.graphQLErrors is set,
  // so check that the error is not just a transient network error
  if (error && !error.networkError) {
    console.error(error);
    return (
      <Box padding={64} flex={{justifyContent: 'center'}}>
        <NonIdealState icon="error" title="GraphQL Error - see console for details" />
      </Box>
    );
  }

  if (isLoading) {
    return blankLoading ? null : <LoadingSpinner purpose={purpose} />;
  }

  return <>{children(data as TData)}</>;
};

export const LoadingSpinner: React.FC<{purpose: 'page' | 'section'}> = ({purpose}) => {
  const isPage = purpose === 'page';
  return (
    <Box
      padding={64}
      flex={{
        grow: isPage ? 1 : undefined,
        justifyContent: 'center',
        alignItems: 'center',
      }}
      style={isPage ? {height: '100%'} : undefined}
    >
      <Spinner purpose={purpose} />
    </Box>
  );
};

Loading.defaultProps = {
  purpose: 'page',
};
