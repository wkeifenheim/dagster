import {Meta} from '@storybook/react/types-6-0';
import * as React from 'react';

import {Group} from './Group';
import {TagWIP as Tag} from './TagWIP';

// eslint-disable-next-line import/no-default-export
export default {
  title: 'Tag',
  component: Tag,
} as Meta;

const INTENTS = ['none', 'primary', 'success', 'warning', 'danger'] as any[];

export const Basic = () => {
  return (
    <Group direction="column" spacing={8}>
      {INTENTS.map((intent) => (
        <Group direction="row" spacing={8} key={intent}>
          <Tag intent={intent} icon="info" />
          <Tag intent={intent} icon="alternate_email">
            Lorem
          </Tag>
          <Tag intent={intent} rightIcon="toggle_off">
            Lorem
          </Tag>
          <Tag intent={intent}>Lorem</Tag>
        </Group>
      ))}
    </Group>
  );
};
