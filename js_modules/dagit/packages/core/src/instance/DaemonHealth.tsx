import {
  ButtonWIP,
  ButtonLink,
  ColorsWIP,
  DialogBody,
  DialogFooter,
  DialogWIP,
  Group,
  TagWIP,
  Trace,
} from '@dagster-io/ui';
import * as React from 'react';

import {DaemonHealthFragment_allDaemonStatuses as DaemonStatus} from './types/DaemonHealthFragment';

interface Props {
  daemon: DaemonStatus;
}

const DaemonHealthTag = (props: Props) => {
  const {daemon} = props;

  if (daemon.healthy) {
    return <TagWIP intent="success">Running</TagWIP>;
  }

  if (daemon.required) {
    return <TagWIP intent="danger">Not running</TagWIP>;
  }

  return <TagWIP intent="none">Not enabled</TagWIP>;
};

type State = {
  shown: boolean;
  page: number;
};

type Action = {type: 'show'} | {type: 'hide'} | {type: 'page'; page: number};

const reducer = (state: State, action: Action) => {
  switch (action.type) {
    case 'show':
      return {shown: true, page: 0};
    case 'hide':
      return {shown: false, page: 0};
    case 'page':
      return {...state, page: action.page};
    default:
      return state;
  }
};

const initialState = {shown: false, page: 0};

export const DaemonHealth = (props: Props) => {
  const {daemon} = props;
  const [state, dispatch] = React.useReducer(reducer, initialState);
  const {shown, page} = state;

  const errors = daemon.lastHeartbeatErrors;
  const errorCount = errors.length;

  const show = () => dispatch({type: 'show'});
  const hide = () => dispatch({type: 'hide'});
  const prev = () => dispatch({type: 'page', page: page === 0 ? errorCount - 1 : page - 1});
  const next = () => dispatch({type: 'page', page: page === errorCount - 1 ? 0 : page + 1});

  const metadata = () => {
    if (errorCount > 0) {
      return (
        <>
          <ButtonLink color={ColorsWIP.Link} underline="hover" onClick={show}>
            {errorCount > 1 ? `View errors (${errorCount})` : 'View error'}
          </ButtonLink>
          <DialogWIP
            isOpen={shown}
            title="Daemon error"
            onClose={hide}
            style={{maxWidth: '80%', minWidth: '70%'}}
          >
            <DialogBody>
              <Group direction="column" spacing={12}>
                {errorCount === 1 ? (
                  <div>
                    <strong>{daemon.daemonType}</strong> daemon logged an error.
                  </div>
                ) : (
                  <div>
                    <strong>{daemon.daemonType}</strong> daemon logged {errorCount} errors.
                  </div>
                )}
                <Trace>
                  <Group direction="column" spacing={12}>
                    <div>{errors[page].message}</div>
                    <div>{errors[page].stack}</div>
                  </Group>
                </Trace>
              </Group>
            </DialogBody>
            <DialogFooter
              left={
                errorCount > 1 ? (
                  <Group direction="row" spacing={12} alignItems="center">
                    <ButtonLink onClick={prev}>&larr; Previous</ButtonLink>
                    <span>{`${page + 1} of ${errorCount}`}</span>
                    <ButtonLink onClick={next}>Next &rarr;</ButtonLink>
                  </Group>
                ) : (
                  <div />
                )
              }
            >
              <ButtonWIP intent="primary" onClick={hide}>
                OK
              </ButtonWIP>
            </DialogFooter>
          </DialogWIP>
        </>
      );
    }

    if (!daemon.healthy) {
      return <div style={{color: ColorsWIP.Gray500}}>No recent heartbeat</div>;
    }

    return null;
  };

  return (
    <Group direction="row" spacing={8} alignItems="center">
      <DaemonHealthTag daemon={daemon} />
      {metadata()}
    </Group>
  );
};
