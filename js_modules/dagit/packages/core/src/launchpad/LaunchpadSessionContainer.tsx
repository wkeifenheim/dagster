import {gql, useApolloClient, useQuery} from '@apollo/client';
import {
  Box,
  ButtonWIP,
  ColorsWIP,
  Group,
  IconWIP,
  SecondPanelToggle,
  SplitPanelContainer,
} from '@dagster-io/ui';
import merge from 'deepmerge';
import * as React from 'react';
import styled from 'styled-components/macro';
import * as yaml from 'yaml';

import {showCustomAlert} from '../app/CustomAlertProvider';
import {
  applyChangesToSession,
  applyCreateSession,
  IExecutionSessionChanges,
  PipelineRunTag,
  SessionBase,
  useStorage,
} from '../app/LocalStorage';
import {PythonErrorInfo} from '../app/PythonErrorInfo';
import {ShortcutHandler} from '../app/ShortcutHandler';
import {ConfigEditor} from '../configeditor/ConfigEditor';
import {ConfigEditorHelpContext} from '../configeditor/ConfigEditorHelpContext';
import {
  CONFIG_EDITOR_RUN_CONFIG_SCHEMA_FRAGMENT,
  CONFIG_EDITOR_VALIDATION_FRAGMENT,
  responseToYamlValidationResult,
} from '../configeditor/ConfigEditorUtils';
import {isHelpContextEqual} from '../configeditor/isHelpContextEqual';
import {DagsterTag} from '../runs/RunTag';
import {RepositorySelector} from '../types/globalTypes';
import {repoAddressToSelector} from '../workspace/repoAddressToSelector';
import {RepoAddress} from '../workspace/types';

import {
  ConfigEditorConfigPicker,
  CONFIG_PARTITION_SELECTION_QUERY,
} from './ConfigEditorConfigPicker';
import {ConfigEditorHelp} from './ConfigEditorHelp';
import {ConfigEditorModePicker} from './ConfigEditorModePicker';
import {LaunchRootExecutionButton} from './LaunchRootExecutionButton';
import {LaunchpadTabs} from './LaunchpadTabs';
import {LoadingOverlay} from './LoadingOverlay';
import {OpSelector} from './OpSelector';
import {RunPreview, RUN_PREVIEW_VALIDATION_FRAGMENT} from './RunPreview';
import {SessionSettingsBar} from './SessionSettingsBar';
import {TagContainer, TagEditor} from './TagEditor';
import {scaffoldPipelineConfig} from './scaffoldType';
import {ConfigEditorGeneratorPipelineFragment_presets} from './types/ConfigEditorGeneratorPipelineFragment';
import {LaunchpadSessionContainerPartitionSetsFragment} from './types/LaunchpadSessionContainerPartitionSetsFragment';
import {LaunchpadSessionContainerPipelineFragment} from './types/LaunchpadSessionContainerPipelineFragment';
import {PipelineExecutionConfigSchemaQuery} from './types/PipelineExecutionConfigSchemaQuery';
import {PreviewConfigQuery, PreviewConfigQueryVariables} from './types/PreviewConfigQuery';

const YAML_SYNTAX_INVALID = `The YAML you provided couldn't be parsed. Please fix the syntax errors and try again.`;
const LOADING_CONFIG_FOR_PARTITION = `Generating configuration...`;
const LOADING_CONFIG_SCHEMA = `Loading config schema...`;
const LOADING_RUN_PREVIEW = `Checking config...`;

type Preset = ConfigEditorGeneratorPipelineFragment_presets;

interface LaunchpadSessionContainerProps {
  pipeline: LaunchpadSessionContainerPipelineFragment;
  partitionSets: LaunchpadSessionContainerPartitionSetsFragment;
  repoAddress: RepoAddress;
}

interface ILaunchpadSessionState {
  preview: PreviewConfigQuery | null;
  previewLoading: boolean;
  previewedDocument: any | null;
  configLoading: boolean;
  editorHelpContext: ConfigEditorHelpContext | null;
  showWhitespace: boolean;
  tagEditorOpen: boolean;
}

type Action =
  | {type: 'preview-loading'; payload: boolean}
  | {
      type: 'set-preview';
      payload: {
        preview: PreviewConfigQuery | null;
        previewLoading: boolean;
        previewedDocument: any | null;
      };
    }
  | {type: 'toggle-tag-editor'; payload: boolean}
  | {type: 'toggle-config-loading'; payload: boolean}
  | {type: 'set-editor-help-context'; payload: ConfigEditorHelpContext | null}
  | {type: 'toggle-whitepsace'; payload: boolean};

const reducer = (state: ILaunchpadSessionState, action: Action) => {
  switch (action.type) {
    case 'preview-loading':
      return {...state, previewLoading: action.payload};
    case 'set-preview': {
      const {preview, previewedDocument, previewLoading} = action.payload;
      return {
        ...state,
        preview,
        previewedDocument,
        previewLoading,
      };
    }
    case 'toggle-tag-editor':
      return {...state, tagEditorOpen: action.payload};
    case 'toggle-config-loading':
      return {...state, configLoading: action.payload};
    case 'set-editor-help-context':
      return {...state, editorHelpContext: action.payload};
    case 'toggle-whitepsace':
      return {...state, showWhitespace: action.payload};
    default:
      return state;
  }
};

const initialState: ILaunchpadSessionState = {
  preview: null,
  previewLoading: false,
  previewedDocument: null,
  configLoading: false,
  showWhitespace: true,
  editorHelpContext: null,
  tagEditorOpen: false,
};

const LaunchpadSessionContainer: React.FC<LaunchpadSessionContainerProps> = (props) => {
  const {partitionSets, pipeline, repoAddress} = props;

  const client = useApolloClient();
  const [state, dispatch] = React.useReducer(reducer, initialState);

  const mounted = React.useRef<boolean>(false);
  const editor = React.useRef<ConfigEditor | null>(null);
  const editorSplitPanelContainer = React.useRef<SplitPanelContainer | null>(null);
  const previewCounter = React.useRef(0);

  const {isJob, presets} = pipeline;

  const initialDataForMode = React.useMemo(() => {
    const presetsForMode = isJob ? (presets.length ? [presets[0]] : []) : presets;
    const partitionSetsForMode = partitionSets.results;

    if (presetsForMode.length === 1 && partitionSetsForMode.length === 0) {
      return {runConfigYaml: presetsForMode[0].runConfigYaml};
    }

    if (!presetsForMode.length && partitionSetsForMode.length === 1) {
      return {base: {partitionsSetName: partitionSetsForMode[0].name, partitionName: null}};
    }

    return {};
  }, [isJob, partitionSets.results, presets]);

  const [data, onSave] = useStorage(repoAddress.name || '', pipeline.name, initialDataForMode);

  const currentSession = data.sessions[data.current];

  const pipelineSelector = {
    ...repoAddressToSelector(repoAddress),
    pipelineName: pipeline.name,
    solidSelection: currentSession?.solidSelection || undefined,
  };

  const configResult = useQuery<PipelineExecutionConfigSchemaQuery>(
    PIPELINE_EXECUTION_CONFIG_SCHEMA_QUERY,
    {
      variables: {selector: pipelineSelector, mode: currentSession?.mode},
      fetchPolicy: 'cache-and-network',
      partialRefetch: true,
    },
  );

  const configSchemaOrError = configResult?.data?.runConfigSchemaOrError;

  React.useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  });

  const onSaveSession = (changes: IExecutionSessionChanges) => {
    onSave(applyChangesToSession(data, data.current, changes));
  };

  const onConfigChange = (config: any) => {
    onSaveSession({
      runConfigYaml: config,
    });
  };

  const onOpSelectionChange = (
    solidSelection: string[] | null,
    solidSelectionQuery: string | null,
  ) => {
    onSaveSession({
      solidSelection,
      solidSelectionQuery,
    });
  };

  const onModeChange = (mode: string) => {
    onSaveSession({mode});
  };

  const onRemoveExtraPaths = (paths: string[]) => {
    const deletePropertyPath = (obj: any, path: string) => {
      const parts = path.split('.');

      // Here we iterate through the parts of the path to get to
      // the second to last nested object. This is so we can call `delete` using
      // this object and the last part of the path.
      for (let i = 0; i < parts.length - 1; i++) {
        obj = obj[parts[i]];
        if (typeof obj === 'undefined') {
          return;
        }
      }

      const lastKey = parts.pop();
      if (lastKey) {
        delete obj[lastKey];
      }
    };

    let runConfigData = {};
    try {
      // Note: parsing `` returns null rather than an empty object,
      // which is preferable for representing empty config.
      runConfigData = yaml.parse(currentSession.runConfigYaml || '') || {};

      for (const path of paths) {
        deletePropertyPath(runConfigData, path);
      }

      const runConfigYaml = yaml.stringify(runConfigData);
      onSaveSession({runConfigYaml});
    } catch (err) {
      showCustomAlert({title: 'Invalid YAML', body: YAML_SYNTAX_INVALID});
      return;
    }
  };

  const runConfigSchema =
    configSchemaOrError?.__typename === 'RunConfigSchema' ? configSchemaOrError : undefined;
  const modeError =
    configSchemaOrError?.__typename === 'ModeNotFoundError' ? configSchemaOrError : undefined;

  const onScaffoldMissingConfig = () => {
    const config = runConfigSchema ? scaffoldPipelineConfig(runConfigSchema) : {};
    try {
      // Note: parsing `` returns null rather than an empty object,
      // which is preferable for representing empty config.
      const runConfigData = yaml.parse(currentSession.runConfigYaml || '') || {};

      const updatedRunConfigData = merge(config, runConfigData);
      const runConfigYaml = yaml.stringify(updatedRunConfigData);
      onSaveSession({runConfigYaml});
    } catch (err) {
      showCustomAlert({title: 'Invalid YAML', body: YAML_SYNTAX_INVALID});
    }
  };

  const buildExecutionVariables = () => {
    if (!currentSession) {
      return;
    }

    const tags = currentSession.tags || [];
    let runConfigData = {};
    try {
      // Note: parsing `` returns null rather than an empty object,
      // which is preferable for representing empty config.
      runConfigData = yaml.parse(currentSession.runConfigYaml || '') || {};
    } catch (err) {
      showCustomAlert({title: 'Invalid YAML', body: YAML_SYNTAX_INVALID});
      return;
    }

    return {
      executionParams: {
        runConfigData,
        selector: pipelineSelector,
        mode: currentSession.mode || 'default',
        executionMetadata: {
          tags: [
            ...tags.map((tag) => ({key: tag.key, value: tag.value})),
            // pass solid selection query via tags
            // clean up https://github.com/dagster-io/dagster/issues/2495
            ...(currentSession.solidSelectionQuery
              ? [
                  {
                    key: DagsterTag.SolidSelection,
                    value: currentSession.solidSelectionQuery,
                  },
                ]
              : []),
            ...(currentSession?.base?.['presetName']
              ? [
                  {
                    key: DagsterTag.PresetName,
                    value: currentSession?.base?.['presetName'],
                  },
                ]
              : []),
          ],
        },
      },
    };
  };

  const saveTags = (tags: PipelineRunTag[]) => {
    const tagDict = {};
    const toSave: PipelineRunTag[] = [];
    tags.forEach((tag: PipelineRunTag) => {
      if (!(tag.key in tagDict)) {
        tagDict[tag.key] = tag.value;
        toSave.push(tag);
      }
    });
    onSaveSession({tags: toSave});
  };

  const checkConfig = async (configJSON: Record<string, unknown>) => {
    // Another request to preview a newer document may be made while this request
    // is in flight, in which case completion of this async method should not set loading=false.
    previewCounter.current += 1;
    const currentPreviewCount = previewCounter.current;

    dispatch({type: 'preview-loading', payload: true});

    const {data} = await client.query<PreviewConfigQuery, PreviewConfigQueryVariables>({
      fetchPolicy: 'no-cache',
      query: PREVIEW_CONFIG_QUERY,
      variables: {
        runConfigData: configJSON,
        pipeline: pipelineSelector,
        mode: currentSession.mode || 'default',
      },
    });

    if (mounted.current) {
      const isLatestRequest = currentPreviewCount === previewCounter.current;
      dispatch({
        type: 'set-preview',
        payload: {
          preview: data,
          previewedDocument: configJSON,
          previewLoading: isLatestRequest ? false : state.previewLoading,
        },
      });
    }

    return responseToYamlValidationResult(configJSON, data.isPipelineConfigValid);
  };

  const onSelectPreset = async (preset: Preset) => {
    const tagsDict: {[key: string]: string} = [...(pipeline?.tags || []), ...preset.tags].reduce(
      (tags, kv) => {
        tags[kv.key] = kv.value;
        return tags;
      },
      {},
    );

    onSaveSession({
      base: {presetName: preset.name},
      name: preset.name,
      runConfigYaml: preset.runConfigYaml || '',
      solidSelection: preset.solidSelection,
      solidSelectionQuery: preset.solidSelection === null ? '*' : preset.solidSelection.join(','),
      mode: preset.mode,
      tags: Object.entries(tagsDict).map(([key, value]) => ({key, value})),
      needsRefresh: false,
    });
  };

  const onSelectPartition = async (
    repositorySelector: RepositorySelector,
    partitionSetName: string,
    partitionName: string,
    sessionSolidSelection?: string[] | null,
  ) => {
    onConfigLoading();
    try {
      const {base} = currentSession;
      const {data} = await client.query({
        query: CONFIG_PARTITION_SELECTION_QUERY,
        variables: {repositorySelector, partitionSetName, partitionName},
      });

      if (
        !data ||
        !data.partitionSetOrError ||
        data.partitionSetOrError.__typename !== 'PartitionSet'
      ) {
        onConfigLoaded();
        return;
      }

      const {partition} = data.partitionSetOrError;

      let tags;
      if (partition.tagsOrError.__typename === 'PythonError') {
        tags = (pipeline?.tags || []).slice();
        showCustomAlert({
          body: <PythonErrorInfo error={partition.tagsOrError} />,
        });
      } else {
        tags = [...(pipeline?.tags || []), ...partition.tagsOrError.results];
      }

      let runConfigYaml;
      if (partition.runConfigOrError.__typename === 'PythonError') {
        runConfigYaml = '';
        showCustomAlert({
          body: <PythonErrorInfo error={partition.runConfigOrError} />,
        });
      } else {
        runConfigYaml = partition.runConfigOrError.yaml;
      }

      const solidSelection = sessionSolidSelection || partition.solidSelection;

      onSaveSession({
        name: partition.name,
        base: Object.assign({}, base, {
          partitionName: partition.name,
        }),
        runConfigYaml,
        solidSelection,
        solidSelectionQuery: solidSelection === null ? '*' : solidSelection.join(','),
        mode: partition.mode,
        tags,
        needsRefresh: false,
      });
    } catch {}
    onConfigLoaded();
  };

  const onRefreshConfig = async (base: SessionBase) => {
    // Handle preset-based configuration.
    if ('presetName' in base) {
      const {presetName} = base;
      const matchingPreset = pipeline.presets.find((preset) => preset.name === presetName);
      if (matchingPreset) {
        onSelectPreset({
          ...matchingPreset,
          solidSelection: currentSession.solidSelection || matchingPreset.solidSelection,
        });
      }
      return;
    }

    // Otherwise, handle partition-based configuration.
    const {partitionName, partitionsSetName} = base;
    const repositorySelector = repoAddressToSelector(repoAddress);

    // It is expected that `partitionName` is set here, since we shouldn't be showing the
    // button at all otherwise.
    if (partitionName) {
      onConfigLoading();
      await onSelectPartition(
        repositorySelector,
        partitionsSetName,
        partitionName,
        currentSession.solidSelection,
      );
      onConfigLoaded();
    }
  };

  const onDismissRefreshWarning = () => {
    onSaveSession({needsRefresh: false});
  };

  const openTagEditor = () => dispatch({type: 'toggle-tag-editor', payload: true});
  const closeTagEditor = () => dispatch({type: 'toggle-tag-editor', payload: false});

  const onConfigLoading = () => dispatch({type: 'toggle-config-loading', payload: true});
  const onConfigLoaded = () => dispatch({type: 'toggle-config-loading', payload: false});

  const onCreateSession = () => {
    onSave(applyCreateSession(data, initialDataForMode));
  };

  const {
    preview,
    previewLoading,
    previewedDocument,
    configLoading,
    editorHelpContext,
    showWhitespace,
    tagEditorOpen,
  } = state;

  const tagsFromDefinition: PipelineRunTag[] = React.useMemo(() => pipeline.tags || [], [pipeline]);
  const tagsFromSession = React.useMemo(() => currentSession.tags || [], [currentSession]);
  const allTags = React.useMemo(
    () => ({fromDefinition: tagsFromDefinition, fromSession: tagsFromSession}),
    [tagsFromDefinition, tagsFromSession],
  );

  const refreshableSessionBase = React.useMemo(() => {
    const {base, needsRefresh} = currentSession;
    if (
      base &&
      needsRefresh &&
      ('presetName' in base || (base.partitionsSetName && base.partitionName))
    ) {
      return base;
    }
    return null;
  }, [currentSession]);

  return (
    <>
      <LaunchpadTabs data={data} onCreate={onCreateSession} onSave={onSave} />
      <SplitPanelContainer
        axis="vertical"
        identifier="execution"
        firstMinSize={100}
        firstInitialPercent={75}
        first={
          <>
            <LoadingOverlay isLoading={configLoading} message={LOADING_CONFIG_FOR_PARTITION} />
            <SessionSettingsBar>
              <ConfigEditorConfigPicker
                pipeline={pipeline}
                partitionSets={partitionSets.results}
                base={currentSession.base}
                onSaveSession={onSaveSession}
                onSelectPreset={onSelectPreset}
                onSelectPartition={onSelectPartition}
                repoAddress={repoAddress}
              />
              <SessionSettingsSpacer />
              <OpSelector
                serverProvidedSubsetError={
                  preview?.isPipelineConfigValid.__typename === 'InvalidSubsetError'
                    ? preview.isPipelineConfigValid
                    : undefined
                }
                pipelineName={pipeline.name}
                value={currentSession.solidSelection || null}
                query={currentSession.solidSelectionQuery || null}
                onChange={onOpSelectionChange}
                repoAddress={repoAddress}
              />
              {isJob ? (
                <span />
              ) : (
                <>
                  <SessionSettingsSpacer />
                  <ConfigEditorModePicker
                    modes={pipeline.modes}
                    modeError={modeError}
                    onModeChange={onModeChange}
                    modeName={currentSession.mode}
                  />
                </>
              )}
              <TagEditor
                tagsFromDefinition={tagsFromDefinition}
                tagsFromSession={tagsFromSession}
                onChange={saveTags}
                open={tagEditorOpen}
                onRequestClose={closeTagEditor}
              />
              <div style={{flex: 1}} />
              {tagsFromSession.length ? null : (
                <>
                  <ShortcutHandler
                    shortcutLabel="⌥T"
                    shortcutFilter={(e) => e.keyCode === 84 && e.altKey}
                    onShortcut={openTagEditor}
                  >
                    <ButtonWIP onClick={openTagEditor} icon={<IconWIP name="add_circle" />}>
                      Add tags
                    </ButtonWIP>
                  </ShortcutHandler>
                  <SessionSettingsSpacer />
                </>
              )}
              <ButtonWIP
                title="Toggle whitespace"
                icon={<IconWIP name="toggle_whitespace" />}
                active={showWhitespace}
                onClick={() => dispatch({type: 'toggle-whitepsace', payload: !showWhitespace})}
              />
              <SessionSettingsSpacer />
              <SecondPanelToggle axis="horizontal" container={editorSplitPanelContainer} />
            </SessionSettingsBar>
            {allTags.fromDefinition.length || allTags.fromSession.length ? (
              <Box
                padding={{vertical: 8, left: 12, right: 0}}
                border={{side: 'bottom', width: 1, color: ColorsWIP.Gray200}}
              >
                <TagContainer tags={allTags} onRequestEdit={openTagEditor} />
              </Box>
            ) : null}
            {refreshableSessionBase ? (
              <Box
                padding={{vertical: 8, horizontal: 12}}
                border={{side: 'bottom', width: 1, color: ColorsWIP.Gray200}}
              >
                <Group direction="row" spacing={8} alignItems="center">
                  <IconWIP name="warning" color={ColorsWIP.Yellow500} />
                  <div>
                    Your repository has been manually refreshed, and this configuration may now be
                    out of date.
                  </div>
                  <ButtonWIP
                    intent="primary"
                    onClick={() => onRefreshConfig(refreshableSessionBase)}
                    disabled={state.configLoading}
                  >
                    Refresh config
                  </ButtonWIP>
                  <ButtonWIP onClick={onDismissRefreshWarning}>Dismiss</ButtonWIP>
                </Group>
              </Box>
            ) : null}
            <SplitPanelContainer
              ref={editorSplitPanelContainer}
              axis="horizontal"
              identifier="execution-editor"
              firstMinSize={100}
              firstInitialPercent={70}
              first={
                <ConfigEditor
                  ref={editor}
                  readOnly={false}
                  runConfigSchema={runConfigSchema}
                  configCode={currentSession.runConfigYaml}
                  onConfigChange={onConfigChange}
                  onHelpContextChange={(next) => {
                    if (!isHelpContextEqual(editorHelpContext, next)) {
                      dispatch({type: 'set-editor-help-context', payload: next});
                    }
                  }}
                  showWhitespace={showWhitespace}
                  checkConfig={checkConfig}
                />
              }
              second={
                <ConfigEditorHelp
                  context={editorHelpContext}
                  allInnerTypes={runConfigSchema?.allConfigTypes || []}
                />
              }
            />
          </>
        }
        second={
          <>
            <LoadingOverlay
              isLoading={previewLoading}
              message={!runConfigSchema ? LOADING_CONFIG_SCHEMA : LOADING_RUN_PREVIEW}
            />
            <RunPreview
              document={previewedDocument}
              validation={preview ? preview.isPipelineConfigValid : null}
              solidSelection={currentSession.solidSelection}
              runConfigSchema={runConfigSchema}
              onHighlightPath={(path) => editor.current?.moveCursorToPath(path)}
              onRemoveExtraPaths={(paths) => onRemoveExtraPaths(paths)}
              onScaffoldMissingConfig={onScaffoldMissingConfig}
            />
          </>
        }
      />
      <div style={{position: 'absolute', bottom: 12, right: 12, zIndex: 1}}>
        <LaunchRootExecutionButton
          pipelineName={pipeline.name}
          getVariables={buildExecutionVariables}
          disabled={preview?.isPipelineConfigValid?.__typename !== 'PipelineConfigValidationValid'}
        />
      </div>
    </>
  );
};

// Imported via React.lazy, which requires a default export.
// eslint-disable-next-line import/no-default-export
export default LaunchpadSessionContainer;

const PREVIEW_CONFIG_QUERY = gql`
  query PreviewConfigQuery(
    $pipeline: PipelineSelector!
    $runConfigData: RunConfigData!
    $mode: String!
  ) {
    isPipelineConfigValid(pipeline: $pipeline, runConfigData: $runConfigData, mode: $mode) {
      ...ConfigEditorValidationFragment
      ...RunPreviewValidationFragment
    }
  }
  ${RUN_PREVIEW_VALIDATION_FRAGMENT}
  ${CONFIG_EDITOR_VALIDATION_FRAGMENT}
`;

const SessionSettingsSpacer = styled.div`
  width: 5px;
`;

const RUN_CONFIG_SCHEMA_OR_ERROR_FRAGMENT = gql`
  fragment LaunchpadSessionContainerRunConfigSchemaFragment on RunConfigSchemaOrError {
    __typename
    ... on RunConfigSchema {
      ...ConfigEditorRunConfigSchemaFragment
    }
    ... on ModeNotFoundError {
      message
    }
  }
  ${CONFIG_EDITOR_RUN_CONFIG_SCHEMA_FRAGMENT}
`;

const PIPELINE_EXECUTION_CONFIG_SCHEMA_QUERY = gql`
  query PipelineExecutionConfigSchemaQuery($selector: PipelineSelector!, $mode: String) {
    runConfigSchemaOrError(selector: $selector, mode: $mode) {
      ...LaunchpadSessionContainerRunConfigSchemaFragment
    }
  }

  ${RUN_CONFIG_SCHEMA_OR_ERROR_FRAGMENT}
`;
