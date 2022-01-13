import {Intent, Position} from '@blueprintjs/core';
import {Meta} from '@storybook/react/types-6-0';
import * as React from 'react';

import {ButtonWIP} from './Button';
import {Group} from './Group';
import {GlobalToasterStyle, Toaster} from './Toaster';

const SharedToaster = Toaster.create({position: Position.TOP}, document.body);

// eslint-disable-next-line import/no-default-export
export default {
  title: 'Toaster',
} as Meta;

export const Sizes = () => {
  return (
    <Group direction="column" spacing={16}>
      <GlobalToasterStyle />

      <ButtonWIP
        onClick={() =>
          SharedToaster.show({
            intent: Intent.NONE,
            message: 'Repository location reloaded',
            timeout: 300000,
            icon: 'done',
          })
        }
      >
        Basic Toast with Icon
      </ButtonWIP>
      <ButtonWIP
        onClick={() =>
          SharedToaster.show({
            intent: Intent.SUCCESS,
            message: (
              <div>
                Created backfill job:{' '}
                <strong>
                  <code>12345</code>
                </strong>
              </div>
            ),
          })
        }
      >
        Success Toast with React Content
      </ButtonWIP>
      <ButtonWIP
        onClick={() =>
          SharedToaster.show({
            intent: Intent.DANGER,
            message: 'This is an error message',
            icon: 'error',
          })
        }
      >
        Error Toast
      </ButtonWIP>
    </Group>
  );
};
