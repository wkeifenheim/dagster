import styled from 'styled-components/macro';

import {ColorsWIP} from './Colors';
import {FontFamily} from './styles';

export const Trace = styled.div`
  background-color: ${ColorsWIP.Gray200};
  color: rgb(41, 50, 56);
  font-family: ${FontFamily.monospace};
  font-size: 14px;
  max-height: 90vh;
  overflow: auto;
  white-space: pre;
  padding: 16px;
`;
