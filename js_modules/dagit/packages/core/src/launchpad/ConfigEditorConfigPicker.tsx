import {gql, useQuery} from '@apollo/client';
import {HTMLInputProps, InputGroupProps2, Intent} from '@blueprintjs/core';
import {
  Box,
  ButtonWIP,
  ColorsWIP,
  IconWIP,
  IconWrapper,
  MenuDividerWIP,
  MenuItemWIP,
  MenuWIP,
  SelectWIP,
  Spinner,
  SuggestWIP,
} from '@dagster-io/ui';
import * as React from 'react';
import styled from 'styled-components/macro';

import {showCustomAlert} from '../app/CustomAlertProvider';
import {IExecutionSession} from '../app/LocalStorage';
import {PythonErrorInfo, PYTHON_ERROR_FRAGMENT} from '../app/PythonErrorInfo';
import {ShortcutHandler} from '../app/ShortcutHandler';
import {PythonErrorFragment} from '../app/types/PythonErrorFragment';
import {RepositorySelector} from '../types/globalTypes';
import {repoAddressToSelector} from '../workspace/repoAddressToSelector';
import {RepoAddress} from '../workspace/types';

import {ConfigEditorGeneratorPartitionSetsFragment_results} from './types/ConfigEditorGeneratorPartitionSetsFragment';
import {
  ConfigEditorGeneratorPipelineFragment,
  ConfigEditorGeneratorPipelineFragment_presets,
} from './types/ConfigEditorGeneratorPipelineFragment';
import {
  ConfigPartitionsQuery,
  ConfigPartitionsQuery_partitionSetOrError_PartitionSet_partitionsOrError_Partitions_results,
} from './types/ConfigPartitionsQuery';

type Pipeline = ConfigEditorGeneratorPipelineFragment;
type Preset = ConfigEditorGeneratorPipelineFragment_presets;
type PartitionSet = ConfigEditorGeneratorPartitionSetsFragment_results;
type Partition = ConfigPartitionsQuery_partitionSetOrError_PartitionSet_partitionsOrError_Partitions_results;
type ConfigGenerator = Preset | PartitionSet;

interface ConfigEditorConfigPickerProps {
  base: IExecutionSession['base'];
  pipeline: Pipeline;
  pipelineMode?: string;
  partitionSets: PartitionSet[];
  onSaveSession: (updates: Partial<IExecutionSession>) => void;
  onSelectPreset: (preset: Preset) => Promise<void>;
  onSelectPartition: (
    repositorySelector: RepositorySelector,
    partitionSetName: string,
    partitionName: string,
  ) => Promise<void>;
  repoAddress: RepoAddress;
}

export const ConfigEditorConfigPicker: React.FC<ConfigEditorConfigPickerProps> = (props) => {
  const {
    pipeline,
    base,
    onSaveSession,
    onSelectPreset,
    onSelectPartition,
    partitionSets,
    repoAddress,
  } = props;

  const {isJob, presets} = pipeline;

  const configGenerators: ConfigGenerator[] = React.useMemo(() => {
    const byName = (a: {name: string}, b: {name: string}) => a.name.localeCompare(b.name);
    return [...presets, ...partitionSets].sort(byName);
  }, [presets, partitionSets]);

  const label = () => {
    if (!base) {
      if (presets.length && !partitionSets.length) {
        return 'Preset';
      }
      if (!presets.length && partitionSets.length) {
        return 'Partition Set';
      }
      return 'Preset / Partition Set';
    }

    if ('presetName' in base) {
      return `Preset: ${base.presetName}`;
    }

    return `Partition Set: ${base.partitionsSetName}`;
  };

  const onSelect = (item: ConfigGenerator) => {
    if (item.__typename === 'PartitionSet') {
      onSaveSession({
        mode: item.mode,
        base: {
          partitionsSetName: item.name,
          partitionName: null,
        },
      });
    } else {
      onSelectPreset(item);
    }
  };

  return (
    <PickerContainer>
      {isJob || configGenerators.length < 1 ? null : (
        <ConfigEditorConfigGeneratorPicker
          label={label()}
          configGenerators={configGenerators}
          onSelect={onSelect}
        />
      )}
      {base && 'partitionsSetName' in base ? (
        <ConfigEditorPartitionPicker
          pipeline={pipeline}
          partitionSetName={base.partitionsSetName}
          value={base.partitionName}
          onSelect={onSelectPartition}
          repoAddress={repoAddress}
        />
      ) : null}
    </PickerContainer>
  );
};

interface ConfigEditorPartitionPickerProps {
  pipeline: Pipeline;
  partitionSetName: string;
  value: string | null;
  onSelect: (
    repositorySelector: RepositorySelector,
    partitionSetName: string,
    partitionName: string,
  ) => void;
  repoAddress: RepoAddress;
}

const ConfigEditorPartitionPicker: React.FC<ConfigEditorPartitionPickerProps> = React.memo(
  (props) => {
    const {partitionSetName, value, onSelect, repoAddress} = props;
    const repositorySelector = repoAddressToSelector(repoAddress);
    const {data, loading} = useQuery<ConfigPartitionsQuery>(CONFIG_PARTITIONS_QUERY, {
      variables: {repositorySelector, partitionSetName},
      fetchPolicy: 'network-only',
    });

    const [sortOrder, setSortOrder] = React.useState('asc');

    const partitions: Partition[] = React.useMemo(() => {
      const retrieved =
        data?.partitionSetOrError.__typename === 'PartitionSet' &&
        data?.partitionSetOrError.partitionsOrError.__typename === 'Partitions'
          ? data.partitionSetOrError.partitionsOrError.results
          : [];
      return sortOrder === 'asc' ? retrieved : [...retrieved].reverse();
    }, [data, sortOrder]);

    const error: PythonErrorFragment | null =
      data?.partitionSetOrError.__typename === 'PartitionSet' &&
      data?.partitionSetOrError.partitionsOrError.__typename !== 'Partitions'
        ? data.partitionSetOrError.partitionsOrError
        : null;

    const selected = partitions.find((p) => p.name === value);

    const onClickSort = React.useCallback((event) => {
      event.preventDefault();
      setSortOrder((order) => (order === 'asc' ? 'desc' : 'asc'));
    }, []);

    const rightElement = partitions.length ? (
      <SortButton onMouseDown={onClickSort}>
        <IconWIP name="sort_by_alpha" color={ColorsWIP.Gray400} />
      </SortButton>
    ) : undefined;

    const inputProps: InputGroupProps2 & HTMLInputProps = {
      placeholder: 'Partition',
      style: {width: 180},
      intent: (loading ? !!value : !!selected) ? Intent.NONE : Intent.DANGER,
      rightElement,
    };

    // If we are loading the partitions and do NOT have any cached data to display,
    // show the component in a loading state with a spinner and fill it with the
    // current partition's name so it doesn't flicker (if one is set already.)
    if (loading && partitions.length === 0) {
      return (
        <SuggestWIP<string>
          key="loading"
          inputProps={{
            ...inputProps,
            rightElement: !value ? (
              <Box
                flex={{direction: 'column', justifyContent: 'center'}}
                padding={{right: 4}}
                style={{height: '30px'}}
              >
                <Spinner purpose="body-text" />
              </Box>
            ) : undefined,
          }}
          items={[]}
          itemRenderer={() => null}
          noResults={<MenuItemWIP disabled={true} text="Loading..." />}
          inputValueRenderer={(str) => str}
          selectedItem={value}
          onItemSelect={() => {}}
        />
      );
    }

    if (error) {
      showCustomAlert({
        body: <PythonErrorInfo error={error} />,
      });
    }

    // Note: We don't want this Suggest to be a fully "controlled" React component.
    // Keeping it's state is annoyign and we only want to update our data model on
    // selection change. However, we need to set an initial value (defaultSelectedItem)
    // and ensure it is re-applied to the internal state when it changes (via `key` below).
    return (
      <SuggestWIP<Partition>
        key={selected ? selected.name : 'none'}
        defaultSelectedItem={selected}
        items={partitions}
        inputProps={inputProps}
        inputValueRenderer={(partition) => partition.name}
        itemPredicate={(query, partition) => query.length === 0 || partition.name.includes(query)}
        itemRenderer={(partition, props) => (
          <MenuItemWIP
            active={props.modifiers.active}
            onClick={props.handleClick}
            key={partition.name}
            text={partition.name}
          />
        )}
        noResults={<MenuItemWIP disabled={true} text="No presets." />}
        onItemSelect={(item) => {
          onSelect(repositorySelector, partitionSetName, item.name);
        }}
        popoverProps={{modifiers: {offset: {enabled: true, offset: '-5px 8px'}}}}
      />
    );
  },
);

interface ConfigEditorConfigGeneratorPickerProps {
  label: string;
  configGenerators: ConfigGenerator[];
  onSelect: (configGenerator: ConfigGenerator) => void;
}

const ConfigEditorConfigGeneratorPicker: React.FC<ConfigEditorConfigGeneratorPickerProps> = React.memo(
  (props) => {
    const {configGenerators, label, onSelect} = props;
    const button = React.useRef<HTMLButtonElement>(null);

    return (
      <div>
        <ShortcutHandler
          shortcutLabel="⌥E"
          shortcutFilter={(e) => e.keyCode === 69 && e.altKey}
          onShortcut={() => button.current?.click()}
        >
          <SelectWIP<ConfigGenerator>
            items={configGenerators}
            itemPredicate={(query, configGenerator) =>
              query.length === 0 || configGenerator.name.includes(query)
            }
            itemListRenderer={({itemsParentRef, renderItem, filteredItems}) => {
              const renderedPresetItems = filteredItems
                .filter((item) => item.__typename === 'PipelinePreset')
                .map(renderItem)
                .filter(Boolean);

              const renderedPartitionSetItems = filteredItems
                .filter((item) => item.__typename === 'PartitionSet')
                .map(renderItem)
                .filter(Boolean);

              const bothTypesPresent =
                renderedPresetItems.length > 0 && renderedPartitionSetItems.length > 0;

              return (
                <MenuWIP ulRef={itemsParentRef}>
                  {bothTypesPresent && <MenuItemWIP disabled={true} text="Presets" />}
                  {renderedPresetItems}
                  {bothTypesPresent && <MenuDividerWIP />}
                  {bothTypesPresent && <MenuItemWIP disabled={true} text="Partition Sets" />}
                  {renderedPartitionSetItems}
                </MenuWIP>
              );
            }}
            itemRenderer={(item, props) => (
              <MenuItemWIP
                active={props.modifiers.active}
                onClick={props.handleClick}
                key={item.name}
                text={
                  <div>
                    {item.name}
                    <div style={{opacity: 0.4, fontSize: '0.75rem'}}>
                      {[
                        item.solidSelection
                          ? item.solidSelection.length === 1
                            ? `Ops: ${item.solidSelection[0]}`
                            : `Ops: ${item.solidSelection.length}`
                          : `Ops: All`,
                        `Mode: ${item.mode}`,
                      ].join(' - ')}
                    </div>
                  </div>
                }
              />
            )}
            noResults={<MenuItemWIP disabled={true} text="No presets." />}
            onItemSelect={onSelect}
          >
            <ButtonWIP
              ref={button}
              data-test-id="preset-selector-button"
              rightIcon={<IconWIP name="expand_more" />}
            >
              {label}
            </ButtonWIP>
          </SelectWIP>
        </ShortcutHandler>
      </div>
    );
  },
);

const SortButton = styled.button`
  border: 0;
  cursor: pointer;
  padding: 4px;
  margin: 3px 3px 0 0;
  background-color: ${ColorsWIP.White};
  border-radius: 4px;
  transition: background-color 100ms;

  :hover,
  :focus {
    background-color: ${ColorsWIP.Gray100};
    outline: none;

    ${IconWrapper} {
      background-color: ${ColorsWIP.Gray700};
    }
  }
`;

const PickerContainer = styled.div`
  display: flex;
  justify: space-between;
  align-items: center;
  gap: 6px;
`;

export const CONFIG_EDITOR_GENERATOR_PIPELINE_FRAGMENT = gql`
  fragment ConfigEditorGeneratorPipelineFragment on Pipeline {
    id
    isJob
    name
    presets {
      __typename
      name
      mode
      solidSelection
      runConfigYaml
      tags {
        key
        value
      }
    }
    tags {
      key
      value
    }
  }
`;

export const CONFIG_EDITOR_GENERATOR_PARTITION_SETS_FRAGMENT = gql`
  fragment ConfigEditorGeneratorPartitionSetsFragment on PartitionSets {
    results {
      id
      name
      mode
      solidSelection
    }
  }
`;

const CONFIG_PARTITIONS_QUERY = gql`
  query ConfigPartitionsQuery(
    $repositorySelector: RepositorySelector!
    $partitionSetName: String!
  ) {
    partitionSetOrError(
      repositorySelector: $repositorySelector
      partitionSetName: $partitionSetName
    ) {
      __typename
      ... on PartitionSet {
        id
        partitionsOrError {
          ... on Partitions {
            results {
              name
            }
          }
          ... on PythonError {
            ...PythonErrorFragment
          }
        }
      }
    }
  }
  ${PYTHON_ERROR_FRAGMENT}
`;

export const CONFIG_PARTITION_SELECTION_QUERY = gql`
  query ConfigPartitionSelectionQuery(
    $repositorySelector: RepositorySelector!
    $partitionSetName: String!
    $partitionName: String!
  ) {
    partitionSetOrError(
      repositorySelector: $repositorySelector
      partitionSetName: $partitionSetName
    ) {
      __typename
      ... on PartitionSet {
        id
        partition(partitionName: $partitionName) {
          name
          solidSelection
          runConfigOrError {
            ... on PartitionRunConfig {
              yaml
            }
            ... on PythonError {
              ...PythonErrorFragment
            }
          }
          mode
          tagsOrError {
            ... on PartitionTags {
              results {
                key
                value
              }
            }
            ... on PythonError {
              ...PythonErrorFragment
            }
          }
        }
      }
    }
  }
  ${PYTHON_ERROR_FRAGMENT}
`;
