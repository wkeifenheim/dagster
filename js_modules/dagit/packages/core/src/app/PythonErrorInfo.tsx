import {gql} from '@apollo/client';
import {ButtonWIP, IconWIP, FontFamily} from '@dagster-io/ui';
import * as React from 'react';
import styled from 'styled-components/macro';

import {MetadataEntries} from '../runs/MetadataEntry';
import {MetadataEntryFragment} from '../runs/types/MetadataEntryFragment';
import {ErrorSource} from '../types/globalTypes';

import {PythonErrorFragment} from './types/PythonErrorFragment';

interface IPythonErrorInfoProps {
  showReload?: boolean;
  centered?: boolean;
  error: {message: string} | PythonErrorFragment;
  failureMetadata?: {metadataEntries: MetadataEntryFragment[]} | null;
  errorSource?: ErrorSource | null;
}

export const PythonErrorInfo: React.FC<IPythonErrorInfoProps> = (props) => {
  const message = props.error.message;
  const stack = (props.error as PythonErrorFragment).stack;
  const cause = (props.error as PythonErrorFragment).cause;

  const Wrapper = props.centered ? ErrorWrapperCentered : ErrorWrapper;
  const context = props.errorSource ? <ErrorContext errorSource={props.errorSource} /> : null;
  const metadataEntries = props.failureMetadata?.metadataEntries;

  return (
    <>
      {context}
      <Wrapper>
        <ErrorHeader>{message}</ErrorHeader>
        {metadataEntries ? (
          <div style={{marginTop: 10, marginBottom: 10}}>
            <MetadataEntries entries={metadataEntries} />
          </div>
        ) : null}
        {stack ? <Trace>{stack.join('')}</Trace> : null}
        {cause ? (
          <>
            <CauseHeader>The above exception was caused by the following exception:</CauseHeader>
            <ErrorHeader>{cause.message}</ErrorHeader>
            {stack ? <Trace>{cause.stack.join('')}</Trace> : null}
          </>
        ) : null}
        {props.showReload && (
          <ButtonWIP icon={<IconWIP name="refresh" />} onClick={() => window.location.reload()}>
            Reload
          </ButtonWIP>
        )}
      </Wrapper>
    </>
  );
};

const ErrorContext: React.FC<{errorSource: ErrorSource}> = ({errorSource}) => {
  switch (errorSource) {
    case ErrorSource.UNEXPECTED_ERROR:
      return (
        <ContextHeader>An unexpected exception was thrown. Please file an issue.</ContextHeader>
      );
    default:
      return null;
  }
};

export const UNAUTHORIZED_ERROR_FRAGMENT = gql`
  fragment UnauthorizedErrorFragment on UnauthorizedError {
    message
  }
`;

export const PYTHON_ERROR_FRAGMENT = gql`
  fragment PythonErrorFragment on PythonError {
    __typename
    message
    stack
    cause {
      message
      stack
    }
  }
`;

const ContextHeader = styled.h4`
  font-weight: 400;
  margin: 0 0 1em;
`;

const CauseHeader = styled.h3`
  font-weight: 400;
  margin: 1em 0 1em;
`;

const ErrorHeader = styled.h3`
  color: #b05c47;
  font-weight: 400;
  margin: 0.5em 0 0.25em;
`;

const Trace = styled.div`
  color: rgb(41, 50, 56);
  font-family: ${FontFamily.monospace};
  font-size: 1em;
  white-space: pre;
  padding-bottom: 1em;
`;

const ErrorWrapper = styled.div`
  background-color: #fdf2f4;
  border: 1px solid #d17257;
  border-radius: 3px;
  max-width: 90vw;
  max-height: calc(100vh - 250px);
  padding: 1em 2em;
  overflow: auto;
`;

const ErrorWrapperCentered = styled(ErrorWrapper)`
  position: absolute;
  left: 50%;
  top: 100px;
  transform: translate(-50%, 0);
`;
