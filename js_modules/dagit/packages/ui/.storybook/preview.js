import '@blueprintjs/core/lib/css/blueprint.css';
import '@blueprintjs/icons/lib/css/blueprint-icons.css';
import '@blueprintjs/select/lib/css/blueprint-select.css';
import '@blueprintjs/table/lib/css/table.css';
import '@blueprintjs/popover2/lib/css/blueprint-popover2.css';

import {
  FontFamily,
  GlobalDialogStyle,
  GlobalPopoverStyle,
  GlobalSuggestStyle,
  GlobalToasterStyle,
  GlobalTooltipStyle,
  ColorsWIP,
} from '../src';

import * as React from 'react';

import {createGlobalStyle} from 'styled-components/macro';

const GlobalStyle = createGlobalStyle`
  * {
    box-sizing: border-box;
  }

  html, body {
    color: ${ColorsWIP.Gray800};
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  a,
  a:hover,
  a:active {
    color: ${ColorsWIP.Link};
  }

  body {
    margin: 0;
    padding: 0;
  }

  body, input, select, textarea {
    font-family: ${FontFamily.default};
  }

  button {
    font-family: inherit;
  }

  code, pre {
    font-family: ${FontFamily.monospace};
    font-size: 16px;
  }

  .material-icons {
    display: block;
  }

  /* todo dish: Remove these when we have buttons updated. */

  .bp3-button .material-icons {
    position: relative;
    top: 1px;
  }

  .bp3-button:disabled .material-icons {
    color: ${ColorsWIP.Gray300}
  }
`;

// Global decorator to apply the styles to all stories
export const decorators = [
  (Story) => (
    <>
      <GlobalStyle />
      <GlobalToasterStyle />
      <GlobalTooltipStyle />
      <GlobalPopoverStyle />
      <GlobalDialogStyle />
      <GlobalSuggestStyle />
      <Story />
    </>
  ),
];

export const parameters = {
  actions: {argTypesRegex: '^on[A-Z].*'},
};
