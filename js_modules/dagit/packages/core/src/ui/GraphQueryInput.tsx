import {Intent} from '@blueprintjs/core';
import {
  Box,
  ButtonWIP,
  ColorsWIP,
  IconWIP,
  MenuItemWIP,
  MenuWIP,
  Popover,
  TextInput,
} from '@dagster-io/ui';
import isEqual from 'lodash/isEqual';
import uniq from 'lodash/uniq';
import * as React from 'react';
import {Link} from 'react-router-dom';
import styled from 'styled-components/macro';

import {filterByQuery, GraphQueryItem} from '../app/GraphQueryImpl';
import {dynamicKeyWithoutIndex, isDynamicStep} from '../gantt/DynamicStepSupport';
import {workspacePipelinePath} from '../workspace/workspacePath';

interface GraphQueryInputProps {
  intent?: Intent;
  items: GraphQueryItem[];
  value: string;
  placeholder: string;
  autoFocus?: boolean;
  presets?: {name: string; value: string}[];
  width?: string | number;
  className?: string;
  disabled?: boolean;

  linkToPreview?: {
    repoName: string;
    repoLocation: string;
    pipelineName: string;
    isJob: boolean;
  };

  onChange: (value: string) => void;
  onKeyDown?: (e: React.KeyboardEvent<any>) => void;
  onFocus?: () => void;
  onBlur?: (value: string) => void;
}

interface ActiveSuggestionInfo {
  text: string;
  idx: number;
}

/** Generates placeholder text for the solid query box that includes a
 * practical example from the current DAG by finding the solid with the highest
 * number of immediate input or output connections and randomly highlighting
 * either the ++solid or solid++ or solid+* syntax.
 */
const placeholderTextForItems = (base: string, items: GraphQueryItem[]) => {
  const seed = items.length % 3;

  let placeholder = base;
  if (items.length === 0) {
    return placeholder;
  }

  const ranked = items.map<{
    incount: number;
    outcount: number;
    name: string;
  }>((s) => ({
    incount: s.inputs.reduce((sum, o) => sum + o.dependsOn.length, 0),
    outcount: s.outputs.reduce((sum, o) => sum + o.dependedBy.length, 0),
    name: s.name,
  }));

  if (seed === 0) {
    const example = ranked.sort((a, b) => b.outcount - a.outcount)[0];
    placeholder = `${placeholder} (ex: ${example!.name}+*)`;
  } else if (seed === 1) {
    const example = ranked.sort((a, b) => b.outcount - a.outcount)[0];
    placeholder = `${placeholder} (ex: ${example!.name}+)`;
  } else if (seed === 2) {
    const example = ranked.sort((a, b) => b.incount - a.incount)[0];
    placeholder = `${placeholder} (ex: ++${example!.name})`;
  }
  return placeholder;
};

const intentToStrokeColor = (intent: Intent | undefined) => {
  switch (intent) {
    case 'danger':
      return ColorsWIP.Red500;
    case 'success':
      return ColorsWIP.Green500;
    case 'warning':
      return ColorsWIP.Yellow500;
    case 'none':
    case 'primary':
    default:
      return ColorsWIP.Gray300;
  }
};

const buildSuggestions = (lastElementName: string, items: GraphQueryItem[], suffix: string) => {
  const available = items.map((s) => s.name);
  for (const name of available) {
    if (isDynamicStep(name)) {
      available.push(dynamicKeyWithoutIndex(name));
    }
  }

  const lastElementLower = lastElementName?.toLowerCase();
  const matching =
    lastElementLower && !suffix
      ? uniq(available)
          .sort()
          .filter((n) => n.toLowerCase().startsWith(lastElementLower))
      : [];

  // No need to show a match if our string exactly matches the one suggestion.
  if (matching.length === 1 && matching[0].toLowerCase() === lastElementLower) {
    return [];
  }

  return matching;
};

export const GraphQueryInput = React.memo(
  React.forwardRef((props: GraphQueryInputProps, ref) => {
    const [active, setActive] = React.useState<ActiveSuggestionInfo | null>(null);
    const [focused, setFocused] = React.useState<boolean>(false);
    const [pendingValue, setPendingValue] = React.useState<string>(props.value);
    const inputRef = React.useRef<HTMLInputElement>(null);

    React.useEffect(() => {
      // props.value is our source of truth, but we hold "un-committed" changes in
      // pendingValue while the field is being edited. Ensure the pending value
      // is synced whenever props.value changes.
      setPendingValue(props.value);
    }, [props.value]);

    const lastClause = /(\*?\+*)([\w\d\[\]_-]+)(\+*\*?)$/.exec(pendingValue);

    const [, prefix, lastElementName, suffix] = lastClause || [];
    const suggestions = React.useMemo(
      () => buildSuggestions(lastElementName, props.items, suffix),
      [lastElementName, props.items, suffix],
    );

    const onConfirmSuggestion = (suggestion: string) => {
      const preceding = lastClause ? pendingValue.substr(0, lastClause.index) : '';
      setPendingValue(preceding + prefix + suggestion + suffix);
    };

    React.useEffect(() => {
      if (!active && suggestions.length) {
        setActive({text: suggestions[0], idx: 0});
        return;
      }
      if (!active) {
        return;
      }
      // Relocate the currently active item in the latest suggestions list
      const pos = suggestions.findIndex((a) => a === active.text);

      // The new index is the index of the active item, or whatever item
      // is now at it's location if it's gone, bounded to the array.
      let nextIdx = pos !== -1 ? pos : active.idx;
      nextIdx = Math.max(0, Math.min(suggestions.length - 1, nextIdx));
      const nextText = suggestions[nextIdx];

      if (nextIdx !== active.idx || nextText !== active.text) {
        setActive({text: nextText, idx: nextIdx});
      }
    }, [active, suggestions]);

    React.useImperativeHandle(ref, () => ({
      focus() {
        if (inputRef.current) {
          inputRef.current.focus();
        }
      },
    }));

    const onKeyDown = (e: React.KeyboardEvent<any>) => {
      if (e.key === 'Enter' || e.key === 'Return' || e.key === 'Tab') {
        if (active && active.text) {
          onConfirmSuggestion(active.text);
          e.preventDefault();
          e.stopPropagation();
        } else {
          e.currentTarget.blur();
        }
      }

      // The up/down arrow keys shift selection in the dropdown.
      // Note: The first down arrow press activates the first item.
      const shift = {ArrowDown: 1, ArrowUp: -1}[e.key];
      if (shift && suggestions.length > 0) {
        e.preventDefault();
        let idx = (active ? active.idx : -1) + shift;
        idx = Math.max(0, Math.min(idx, suggestions.length - 1));
        setActive({text: suggestions[idx], idx});
      }

      props.onKeyDown?.(e);
    };

    const uncomitted = (pendingValue || '*') !== (props.value || '*');

    return (
      <Box flex={{direction: 'row', alignItems: 'center', gap: 8}}>
        <Popover
          isOpen={focused}
          position="top-left"
          content={
            suggestions.length ? (
              <MenuWIP style={{width: props.width || '30vw'}}>
                {suggestions.slice(0, 15).map((suggestion) => (
                  <MenuItemWIP
                    key={suggestion}
                    text={suggestion}
                    active={active ? active.text === suggestion : false}
                    onMouseDown={(e: React.MouseEvent<any>) => {
                      e.preventDefault();
                      e.stopPropagation();
                      onConfirmSuggestion(suggestion);
                    }}
                  />
                ))}
              </MenuWIP>
            ) : (
              <div />
            )
          }
        >
          <div style={{position: 'relative'}}>
            <TextInput
              disabled={props.disabled}
              value={pendingValue}
              icon="op_selector"
              strokeColor={intentToStrokeColor(props.intent)}
              autoFocus={props.autoFocus}
              placeholder={placeholderTextForItems(props.placeholder, props.items)}
              onChange={(e: React.ChangeEvent<any>) => setPendingValue(e.target.value)}
              onFocus={() => {
                setFocused(true);
                props.onFocus?.();
              }}
              onBlur={() => {
                setFocused(false);
                props.onChange(pendingValue);
                props.onBlur?.(pendingValue);
              }}
              onKeyDown={onKeyDown}
              style={{width: props.width || '30vw'}}
              className={props.className}
              ref={inputRef}
            />
            {focused && uncomitted && <EnterHint>Enter</EnterHint>}
            {focused && props.linkToPreview && (
              <OpCountWrap>
                {`${filterByQuery(props.items, pendingValue).all.length} matching ops`}
                <Link
                  target="_blank"
                  style={{display: 'flex', alignItems: 'center', gap: 4}}
                  onMouseDown={(e) => e.currentTarget.click()}
                  to={workspacePipelinePath({
                    ...props.linkToPreview,
                    pipelineName: `${props.linkToPreview.pipelineName}~${pendingValue}`,
                  })}
                >
                  Graph Preview <IconWIP color={ColorsWIP.Link} name="open_in_new" />
                </Link>
              </OpCountWrap>
            )}
          </div>
        </Popover>
        {props.presets &&
          (props.presets.find((p) => p.value === pendingValue) ? (
            <ButtonWIP
              icon={<IconWIP name="layers" />}
              rightIcon={<IconWIP name="cancel" />}
              onClick={() => props.onChange('*')}
              intent="none"
            />
          ) : (
            <Popover
              position="top"
              content={
                <MenuWIP>
                  {props.presets.map((preset) => (
                    <MenuItemWIP
                      key={preset.name}
                      text={preset.name}
                      onMouseDown={(e: React.MouseEvent<any>) => {
                        e.preventDefault();
                        e.stopPropagation();
                        props.onChange(preset.value);
                      }}
                    />
                  ))}
                </MenuWIP>
              }
            >
              <ButtonWIP
                icon={<IconWIP name="layers" />}
                rightIcon={<IconWIP name="expand_less" />}
                intent="none"
              />
            </Popover>
          ))}
      </Box>
    );
  }),

  (prevProps, nextProps) =>
    prevProps.items === nextProps.items &&
    prevProps.width === nextProps.width &&
    prevProps.value === nextProps.value &&
    isEqual(prevProps.presets, nextProps.presets),
);

const OpCountWrap = styled.div`
  width: 350px;
  padding: 10px;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  position: absolute;
  top: 100%;
  margin-top: 2px;
  font-size: 0.85rem;
  background: ${ColorsWIP.White};
  color: ${ColorsWIP.Gray600};
  box-shadow: 1px 1px 3px rgba(0, 0, 0, 0.2);
  z-index: 2;
  left: 0;
`;

const EnterHint = styled.div`
  position: absolute;
  right: 6px;
  top: 5px;
  border-radius: 5px;
  border: 1px solid ${ColorsWIP.Gray500};
  font-weight: 500;
  font-size: 12px;
  color: ${ColorsWIP.Gray500};
  padding: 2px 6px;
`;
