import {useMutation} from '@apollo/client';
import {ProgressBar} from '@blueprintjs/core';
import {
  Box,
  ButtonWIP,
  Checkbox,
  ColorsWIP,
  DialogBody,
  DialogFooter,
  DialogWIP,
  Group,
  IconWIP,
  Mono,
} from '@dagster-io/ui';
import * as React from 'react';

import {TerminateRunPolicy} from '../types/globalTypes';

import {NavigationBlock} from './NavitationBlock';
import {TERMINATE_MUTATION} from './RunUtils';
import {
  Terminate,
  Terminate_terminatePipelineExecution_RunNotFoundError,
  Terminate_terminatePipelineExecution_PythonError,
  Terminate_terminatePipelineExecution_UnauthorizedError,
  Terminate_terminatePipelineExecution_TerminateRunFailure,
} from './types/Terminate';

export interface Props {
  isOpen: boolean;
  onClose: () => void;
  onComplete: (terminationState: TerminationState) => void;
  // A map from the run ID to its `canTerminate` value
  selectedRuns: {[id: string]: boolean};
}

type Error =
  | Terminate_terminatePipelineExecution_TerminateRunFailure
  | Terminate_terminatePipelineExecution_RunNotFoundError
  | Terminate_terminatePipelineExecution_UnauthorizedError
  | Terminate_terminatePipelineExecution_PythonError
  | undefined;

export type TerminationState = {completed: number; errors: {[id: string]: Error}};

type TerminationDialogState = {
  mustForce: boolean;
  frozenRuns: SelectedRuns;
  step: 'initial' | 'terminating' | 'completed';
  termination: TerminationState;
};

type SelectedRuns = {[id: string]: boolean};

const initializeState = (selectedRuns: SelectedRuns): TerminationDialogState => {
  return {
    // If any selected runs have `canTerminate`, we don't necessarily have to force.
    mustForce: !Object.keys(selectedRuns).some((id) => selectedRuns[id]),
    frozenRuns: selectedRuns,
    step: 'initial',
    termination: {completed: 0, errors: {}},
  };
};

type TerminationDialogAction =
  | {type: 'reset'; frozenRuns: SelectedRuns}
  | {type: 'toggle-force-terminate'; checked: boolean}
  | {type: 'start'}
  | {type: 'termination-success'}
  | {type: 'termination-error'; id: string; error: Error}
  | {type: 'complete'};

const terminationDialogReducer = (
  prevState: TerminationDialogState,
  action: TerminationDialogAction,
): TerminationDialogState => {
  switch (action.type) {
    case 'reset':
      return initializeState(action.frozenRuns);
    case 'toggle-force-terminate':
      return {...prevState, mustForce: action.checked};
    case 'start':
      return {...prevState, step: 'terminating'};
    case 'termination-success': {
      const {termination} = prevState;
      return {
        ...prevState,
        step: 'terminating',
        termination: {...termination, completed: termination.completed + 1},
      };
    }
    case 'termination-error': {
      const {termination} = prevState;
      return {
        ...prevState,
        step: 'terminating',
        termination: {
          ...termination,
          completed: termination.completed + 1,
          errors: {...termination.errors, [action.id]: action.error},
        },
      };
    }
    case 'complete':
      return {...prevState, step: 'completed'};
  }
};

export const TerminationDialog = (props: Props) => {
  const {isOpen, onClose, onComplete, selectedRuns} = props;

  // Freeze the selected IDs, since the list may change as runs continue processing and
  // terminating. We want to preserve the list we're given.
  const frozenRuns = React.useRef<SelectedRuns>(selectedRuns);

  const [state, dispatch] = React.useReducer(
    terminationDialogReducer,
    frozenRuns.current,
    initializeState,
  );

  const count = Object.keys(state.frozenRuns).length;

  // If the dialog is newly open, update state to match the frozen list.
  React.useEffect(() => {
    if (isOpen) {
      dispatch({type: 'reset', frozenRuns: frozenRuns.current});
    }
  }, [isOpen]);

  // If the dialog is not open, update the ref so that the frozen list will be entered
  // into state the next time the dialog opens.
  React.useEffect(() => {
    if (!isOpen) {
      frozenRuns.current = selectedRuns;
    }
  }, [isOpen, selectedRuns]);

  const [terminate] = useMutation<Terminate>(TERMINATE_MUTATION);
  const policy = state.mustForce
    ? TerminateRunPolicy.MARK_AS_CANCELED_IMMEDIATELY
    : TerminateRunPolicy.SAFE_TERMINATE;

  const mutate = async () => {
    dispatch({type: 'start'});

    const runList = Object.keys(state.frozenRuns);
    for (let ii = 0; ii < runList.length; ii++) {
      const runId = runList[ii];
      const {data} = await terminate({variables: {runId, terminatePolicy: policy}});

      if (data?.terminatePipelineExecution.__typename === 'TerminateRunSuccess') {
        dispatch({type: 'termination-success'});
      } else {
        dispatch({type: 'termination-error', id: runId, error: data?.terminatePipelineExecution});
      }
    }

    dispatch({type: 'complete'});
    onComplete(state.termination);
  };

  const onToggleForce = (event: React.ChangeEvent<HTMLInputElement>) => {
    dispatch({type: 'toggle-force-terminate', checked: event.target.checked});
  };

  const showCheckbox = Object.keys(state.frozenRuns).some((id) => state.frozenRuns[id]);

  const progressContent = () => {
    switch (state.step) {
      case 'initial':
        if (!count) {
          return (
            <Group direction="column" spacing={16}>
              <div>No runs selected for termination.</div>
              <div>The runs you selected may already have finished executing.</div>
            </Group>
          );
        }

        return (
          <Group direction="column" spacing={16}>
            <div>
              {`${count} ${
                count === 1 ? 'run' : 'runs'
              } will be terminated. Do you wish to continue?`}
            </div>
            <div>
              {showCheckbox ? (
                <Checkbox
                  checked={state.mustForce}
                  size="small"
                  label={
                    <Box flex={{display: 'flex', direction: 'row', gap: 8}}>
                      <IconWIP name="warning" color={ColorsWIP.Yellow500} />
                      <div>
                        Force termination immediately. <strong>Warning:</strong> computational
                        resources created by runs may not be cleaned up.
                      </div>
                    </Box>
                  }
                  onChange={onToggleForce}
                />
              ) : (
                <Group direction="row" spacing={8}>
                  <IconWIP name="warning" color={ColorsWIP.Yellow500} />
                  <div>
                    <strong>Warning:</strong> computational resources created by runs may not be
                    cleaned up.
                  </div>
                </Group>
              )}
            </div>
          </Group>
        );
      case 'terminating':
      case 'completed':
        const value = count > 0 ? state.termination.completed / count : 1;
        return (
          <Group direction="column" spacing={8}>
            <div>{state.mustForce ? 'Forcing termination…' : 'Terminating…'}</div>
            <ProgressBar intent="primary" value={Math.max(0.1, value)} animate={value < 1} />
            {state.step === 'terminating' ? (
              <NavigationBlock message="Termination in progress, please do not navigate away yet." />
            ) : null}
          </Group>
        );
      default:
        return null;
    }
  };

  const buttons = () => {
    switch (state.step) {
      case 'initial':
        if (!count) {
          return (
            <ButtonWIP intent="none" onClick={onClose}>
              OK
            </ButtonWIP>
          );
        }

        return (
          <>
            <ButtonWIP intent="none" onClick={onClose}>
              Cancel
            </ButtonWIP>
            <ButtonWIP intent="danger" onClick={mutate}>
              {`${state.mustForce ? 'Force termination for' : 'Terminate'} ${`${count} ${
                count === 1 ? 'run' : 'runs'
              }`}`}
            </ButtonWIP>
          </>
        );
      case 'terminating':
        return (
          <ButtonWIP intent="danger" disabled>
            {state.mustForce
              ? `Forcing termination for ${`${count} ${count === 1 ? 'run' : 'runs'}...`}`
              : `Terminating ${`${count} ${count === 1 ? 'run' : 'runs'}...`}`}
          </ButtonWIP>
        );
      case 'completed':
        return (
          <ButtonWIP intent="primary" onClick={onClose}>
            Done
          </ButtonWIP>
        );
    }
  };

  const completionContent = () => {
    if (state.step === 'initial') {
      return null;
    }

    if (state.step === 'terminating') {
      return <div>Please do not close the window or navigate away during termination.</div>;
    }

    const errors = state.termination.errors;
    const errorCount = Object.keys(errors).length;
    const successCount = state.termination.completed - errorCount;

    return (
      <Group direction="column" spacing={8}>
        {successCount ? (
          <Group direction="row" spacing={8} alignItems="flex-start">
            <IconWIP name="check_circle" color={ColorsWIP.Green500} />
            <div>
              {state.mustForce
                ? `Successfully forced termination for ${successCount}
                ${successCount === 1 ? 'run' : `runs`}.`
                : `Successfully requested termination for ${successCount}
              ${successCount === 1 ? 'run' : `runs`}.`}
            </div>
          </Group>
        ) : null}
        {errorCount ? (
          <Group direction="column" spacing={8}>
            <Group direction="row" spacing={8} alignItems="flex-start">
              <IconWIP name="warning" color={ColorsWIP.Yellow500} />
              <div>
                {state.mustForce
                  ? `Could not force termination for ${errorCount} ${
                      errorCount === 1 ? 'run' : 'runs'
                    }:`
                  : `Could not request termination for ${errorCount} ${
                      errorCount === 1 ? 'run' : 'runs'
                    }:`}
              </div>
            </Group>
            <ul>
              {Object.keys(errors).map((runId) => (
                <li key={runId}>
                  <Group direction="row" spacing={8}>
                    <Mono>{runId.slice(0, 8)}</Mono>
                    {errors[runId] ? <div>{errors[runId]?.message}</div> : null}
                  </Group>
                </li>
              ))}
            </ul>
          </Group>
        ) : null}
      </Group>
    );
  };

  const canQuicklyClose = state.step !== 'terminating';

  return (
    <DialogWIP
      isOpen={isOpen}
      title="Terminate runs"
      canEscapeKeyClose={canQuicklyClose}
      canOutsideClickClose={canQuicklyClose}
      onClose={onClose}
    >
      <DialogBody>
        <Group direction="column" spacing={24}>
          {progressContent()}
          {completionContent()}
        </Group>
      </DialogBody>
      <DialogFooter>{buttons()}</DialogFooter>
    </DialogWIP>
  );
};
