import {Meta} from '@storybook/react/types-6-0';
import * as React from 'react';

import {ColorsWIP} from './Colors';
import {CustomTooltipProvider} from './CustomTooltipProvider';
import {Group} from './Group';
import {IconWIP} from './Icon';
import {Tooltip, GlobalTooltipStyle} from './Tooltip';

const SOLID_STYLES: React.CSSProperties = {
  background: ColorsWIP.Yellow200,
  transform: 'translate(0,0)',
  border: `1px solid ${ColorsWIP.Yellow500}`,
  color: ColorsWIP.Gray900,
  fontSize: '12px',
  padding: 6,
};

const JOB_STYLES: React.CSSProperties = {
  background: ColorsWIP.Gray700,
  border: `1px solid ${ColorsWIP.Gray900}`,
  color: ColorsWIP.White,
  fontSize: '15px',
  padding: 3,
};

// eslint-disable-next-line import/no-default-export
export default {
  title: 'Tooltip',
  component: Tooltip,
} as Meta;

export const Default = () => {
  const content = (
    <>
      View snapshot as of <strong>12cad35e</strong>
    </>
  );

  return (
    <Group spacing={8} direction="column">
      <CustomTooltipProvider />
      <GlobalTooltipStyle />

      <p style={{color: ColorsWIP.Gray500}}>
        Use the <code>Tooltip</code> component to attach additional explanations, descriptions, and
        context to controls, icons, etc.
      </p>
      <Tooltip content={content} placement="bottom">
        Tooltip Below
      </Tooltip>
      <Tooltip content={content} placement="top">
        Tooltip Above
      </Tooltip>
      <Tooltip
        content={content}
        modifiers={{offset: {enabled: true, options: {offset: [0, 16]}}}}
        placement="right"
      >
        Tooltip After, Custom Offset
      </Tooltip>
      <Tooltip
        content={
          <div style={{display: 'flex', width: 400, gap: 8}}>
            <IconWIP name="warning" color={ColorsWIP.Yellow500} />
            <div>
              Wow, who would have thought you can put an entire paragraph into a tooltip? Just
              don&apos;t try to put interactable content here, they don&apos;t hold focus.
            </div>
          </div>
        }
        placement="top"
      >
        Tooltip with Block Content
      </Tooltip>

      <hr />

      <p style={{color: ColorsWIP.Gray500}}>
        Use the <code>data-tooltip</code> attribute to expand truncated job, op names, etc. on
        hover. These are highly stylable via <code>data-tooltip-style</code> so they can look like
        boxes / nodes expanding in place to reveal their full text. There is no per-component render
        cost to these annotations so they can be used in cases when thousands of nodes are rendered.
        <br />
        <br />
        These tooltips automatically appear only when the content is truncated or when content
        contains a <code>…</code>
      </p>
      {['short_solid', 'long_solid_name_here'].map((name) => (
        <div
          key={name}
          data-tooltip={name}
          data-tooltip-style={JSON.stringify(SOLID_STYLES)}
          style={{
            width: '100px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            position: 'relative',
            ...SOLID_STYLES,
          }}
        >
          {name}
        </div>
      ))}

      <span
        data-tooltip="fetch_from_redshift_cloud_prod"
        data-tooltip-style={JSON.stringify(JOB_STYLES)}
        style={JOB_STYLES}
      >
        fetch_from_redshift…
      </span>
    </Group>
  );
};
