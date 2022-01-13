import {gql} from '@apollo/client';
import {Box, ColorsWIP, Tab, Tabs} from '@dagster-io/ui';
import * as React from 'react';

import {OpNameOrPath} from '../ops/OpNameOrPath';
import {TypeExplorerContainer} from '../typeexplorer/TypeExplorerContainer';
import {TypeListContainer} from '../typeexplorer/TypeListContainer';
import {RepoAddress} from '../workspace/types';

import {RightInfoPanelContent} from './GraphExplorer';
import {GraphExplorerJobContext} from './GraphExplorerJobContext';
import {ExplorerPath} from './PipelinePathUtils';
import {SidebarOpContainer} from './SidebarOpContainer';
import {SidebarOpContainerInfo, SIDEBAR_OP_CONTAINER_INFO_FRAGMENT} from './SidebarPipelineInfo';
import {SidebarTabbedContainerPipelineFragment} from './types/SidebarTabbedContainerPipelineFragment';

type TabKey = 'types' | 'info';

interface TabDefinition {
  name: string;
  key: TabKey;
  content: () => React.ReactNode;
}

interface ISidebarTabbedContainerProps {
  tab?: TabKey;
  typeName?: string;
  pipeline: SidebarTabbedContainerPipelineFragment;
  explorerPath: ExplorerPath;
  opHandleID?: string;
  parentOpHandleID?: string;
  getInvocations?: (definitionName: string) => {handleID: string}[];
  onEnterSubgraph: (arg: OpNameOrPath) => void;
  onClickOp: (arg: OpNameOrPath) => void;
  repoAddress?: RepoAddress;
  isGraph: boolean;
}

export const SidebarTabbedContainer: React.FC<ISidebarTabbedContainerProps> = (props) => {
  const {
    tab,
    typeName,
    pipeline,
    explorerPath,
    opHandleID,
    getInvocations,
    parentOpHandleID,
    onEnterSubgraph,
    onClickOp,
    repoAddress,
    isGraph,
  } = props;

  const jobContext = React.useContext(GraphExplorerJobContext);

  const activeTab = tab || 'info';

  const TabDefinitions: Array<TabDefinition> = [
    {
      name: 'Info',
      key: 'info',
      content: () =>
        opHandleID ? (
          <SidebarOpContainer
            key={opHandleID}
            explorerPath={explorerPath}
            handleID={opHandleID}
            showingSubgraph={false}
            getInvocations={getInvocations}
            onEnterSubgraph={onEnterSubgraph}
            onClickOp={onClickOp}
            repoAddress={repoAddress}
            isGraph={isGraph}
          />
        ) : parentOpHandleID ? (
          <SidebarOpContainer
            key={parentOpHandleID}
            explorerPath={explorerPath}
            handleID={parentOpHandleID}
            showingSubgraph={true}
            getInvocations={getInvocations}
            onEnterSubgraph={onEnterSubgraph}
            onClickOp={onClickOp}
            repoAddress={repoAddress}
            isGraph={isGraph}
          />
        ) : jobContext ? (
          jobContext.sidebarTab
        ) : (
          <SidebarOpContainerInfo isGraph={!!isGraph} pipeline={pipeline} key={pipeline.name} />
        ),
    },
    {
      name: 'Types',
      key: 'types',
      content: () =>
        typeName ? (
          <TypeExplorerContainer
            explorerPath={explorerPath}
            repoAddress={repoAddress}
            typeName={typeName}
          />
        ) : (
          <TypeListContainer repoAddress={repoAddress} explorerPath={explorerPath} />
        ),
    },
  ];

  return (
    <>
      <Box
        padding={{horizontal: 24}}
        border={{side: 'bottom', width: 1, color: ColorsWIP.KeylineGray}}
      >
        <Tabs selectedTabId={activeTab}>
          {TabDefinitions.map(({name, key}) => (
            <Tab id={key} key={key} to={{search: `?tab=${key}`}} title={name} />
          ))}
        </Tabs>
      </Box>
      <RightInfoPanelContent>
        {TabDefinitions.find((t) => t.key === activeTab)?.content()}
      </RightInfoPanelContent>
    </>
  );
};

export const SIDEBAR_TABBED_CONTAINER_PIPELINE_FRAGMENT = gql`
  fragment SidebarTabbedContainerPipelineFragment on SolidContainer {
    id
    name
    ...SidebarOpContainerInfoFragment
  }

  ${SIDEBAR_OP_CONTAINER_INFO_FRAGMENT}
`;
