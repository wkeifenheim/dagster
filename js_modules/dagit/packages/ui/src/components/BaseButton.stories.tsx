import {Meta} from '@storybook/react/types-6-0';
import * as React from 'react';

import {BaseButton} from './BaseButton';
import {Box} from './Box';
import {ColorsWIP} from './Colors';
import {Group} from './Group';
import {IconWIP as Icon} from './Icon';

// eslint-disable-next-line import/no-default-export
export default {
  title: 'BaseButton',
  component: BaseButton,
} as Meta;

export const Default = () => {
  return (
    <Group direction="column" spacing={8}>
      <BaseButton label="Button" />
      <BaseButton label="Button" icon={<Icon name="star" />} />
      <BaseButton label="Button" rightIcon={<Icon name="close" />} />
      <BaseButton
        label="Button"
        icon={<Icon name="source" />}
        rightIcon={<Icon name="expand_more" />}
      />
      <BaseButton icon={<Icon name="cached" />} />
    </Group>
  );
};

export const Fill = () => {
  return (
    <Group direction="column" spacing={8}>
      <BaseButton label="Button" fillColor={ColorsWIP.Dark} textColor={ColorsWIP.White} />
      <BaseButton
        label="Button"
        fillColor={ColorsWIP.Blue500}
        textColor={ColorsWIP.White}
        icon={<Icon name="star" />}
      />
      <BaseButton
        label="Button"
        fillColor={ColorsWIP.Green500}
        textColor={ColorsWIP.White}
        rightIcon={<Icon name="close" />}
      />
      <BaseButton
        label="Button"
        fillColor={ColorsWIP.Red500}
        textColor={ColorsWIP.White}
        icon={<Icon name="source" />}
        rightIcon={<Icon name="expand_more" />}
      />
      <BaseButton
        label="Button"
        fillColor={ColorsWIP.Olive500}
        textColor={ColorsWIP.White}
        icon={<Icon name="folder_open" />}
      />
      <BaseButton
        fillColor={ColorsWIP.Yellow500}
        textColor={ColorsWIP.White}
        icon={<Icon name="cached" />}
      />
    </Group>
  );
};

export const Transparent = () => {
  return (
    <Box padding={12} background={ColorsWIP.Gray200}>
      <Group direction="column" spacing={8}>
        <BaseButton textColor={ColorsWIP.Dark} label="Button" fillColor="transparent" />
        <BaseButton
          textColor={ColorsWIP.Dark}
          label="Button"
          fillColor="transparent"
          icon={<Icon name="star" />}
        />
        <BaseButton
          textColor={ColorsWIP.Dark}
          label="Button"
          fillColor="transparent"
          rightIcon={<Icon name="close" />}
        />
        <BaseButton
          textColor={ColorsWIP.Dark}
          label="Button"
          fillColor="transparent"
          icon={<Icon name="source" />}
          rightIcon={<Icon name="expand_more" />}
        />
        <BaseButton
          textColor={ColorsWIP.Dark}
          fillColor="transparent"
          icon={<Icon name="cached" />}
        />
      </Group>
    </Box>
  );
};

export const Disabled = () => {
  return (
    <Group direction="column" spacing={8}>
      <BaseButton label="Button" icon={<Icon name="star" />} disabled />
      <BaseButton label="Button" fillColor={ColorsWIP.Dark} textColor={ColorsWIP.White} disabled />
      <BaseButton textColor={ColorsWIP.Dark} label="Button" fillColor="transparent" disabled />
    </Group>
  );
};
