import {Overlay} from '@blueprintjs/core';
import {Box, ColorsWIP, IconWIP, Spinner, FontFamily} from '@dagster-io/ui';
import Fuse from 'fuse.js';
import * as React from 'react';
import {useHistory, useLocation} from 'react-router-dom';
import styled from 'styled-components/macro';

import {ShortcutHandler} from '../app/ShortcutHandler';

import {SearchResults} from './SearchResults';
import {SearchResult} from './types';
import {useRepoSearch} from './useRepoSearch';

type State = {
  shown: boolean;
  queryString: string;
  searching: boolean;
  results: Fuse.FuseResult<SearchResult>[];
  highlight: number;
  loaded: boolean;
};

type Action =
  | {type: 'show-dialog'}
  | {type: 'hide-dialog'}
  | {type: 'highlight'; highlight: number}
  | {type: 'change-query'; queryString: string}
  | {type: 'complete-search'; results: Fuse.FuseResult<SearchResult>[]};

const reducer = (state: State, action: Action) => {
  switch (action.type) {
    case 'show-dialog':
      return {...state, shown: true, loaded: true};
    case 'hide-dialog':
      return {...state, shown: false, queryString: ''};
    case 'highlight':
      return {...state, highlight: action.highlight};
    case 'change-query':
      return {...state, queryString: action.queryString, searching: true, highlight: 0};
    case 'complete-search':
      return {...state, results: action.results, searching: false};
    default:
      return state;
  }
};

const initialState: State = {
  shown: false,
  queryString: '',
  searching: false,
  results: [],
  highlight: 0,
  loaded: false,
};

export const SearchDialog: React.FC<{searchPlaceholder: string}> = ({searchPlaceholder}) => {
  const location = useLocation();
  const history = useHistory();
  const {loading, performSearch} = useRepoSearch();

  const [state, dispatch] = React.useReducer(reducer, initialState);
  const {shown, queryString, results, highlight, loaded} = state;

  const numResults = results.length;

  const openSearch = React.useCallback(() => dispatch({type: 'show-dialog'}), []);
  const onChange = React.useCallback((e) => {
    dispatch({type: 'change-query', queryString: e.target.value});
  }, []);

  React.useEffect(() => {
    const results = performSearch(queryString, loaded);
    dispatch({type: 'complete-search', results});
  }, [queryString, performSearch, loaded]);

  React.useEffect(() => {
    dispatch({type: 'hide-dialog'});
  }, [location.pathname]);

  const onClickResult = React.useCallback(
    (result: Fuse.FuseResult<SearchResult>) => {
      dispatch({type: 'hide-dialog'});
      history.push(result.item.href);
    },
    [history],
  );

  const highlightedResult = results[highlight] || null;

  const onKeyDown = (e: React.KeyboardEvent) => {
    const {key} = e;
    if (key === 'Escape') {
      dispatch({type: 'hide-dialog'});
      return;
    }

    if (!numResults) {
      return;
    }

    const lastResult = numResults - 1;

    switch (key) {
      case 'ArrowUp':
        e.preventDefault();
        dispatch({
          type: 'highlight',
          highlight: highlight === 0 ? lastResult : highlight - 1,
        });
        break;
      case 'ArrowDown':
        e.preventDefault();
        dispatch({
          type: 'highlight',
          highlight: highlight === lastResult ? 0 : highlight + 1,
        });
        break;
      case 'Enter':
        e.preventDefault();
        if (highlightedResult) {
          dispatch({type: 'hide-dialog'});
          history.push(highlightedResult.item.href);
        }
    }
  };

  return (
    <>
      <ShortcutHandler
        onShortcut={() => dispatch({type: 'show-dialog'})}
        shortcutLabel="/"
        shortcutFilter={(e) =>
          e.key === '/' && !e.altKey && !e.metaKey && !e.shiftKey && !e.ctrlKey
        }
      >
        <SearchTrigger onClick={openSearch}>
          <Box flex={{justifyContent: 'space-between', alignItems: 'center'}}>
            <Box flex={{alignItems: 'center', gap: 8}}>
              <div
                style={{
                  background: ColorsWIP.Gray900,
                  borderRadius: '12px',
                  height: '24px',
                  width: '24px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <IconWIP name="search" color={ColorsWIP.Gray50} />
              </div>
              <Placeholder>{searchPlaceholder}</Placeholder>
            </Box>
            <SlashShortcut>/</SlashShortcut>
          </Box>
        </SearchTrigger>
      </ShortcutHandler>
      <Overlay
        backdropProps={{style: {backgroundColor: ColorsWIP.WashGray}}}
        isOpen={shown}
        onClose={() => dispatch({type: 'hide-dialog'})}
        transitionDuration={100}
      >
        <Container>
          <SearchBox hasQueryString={!!queryString.length}>
            <IconWIP name="search" color={ColorsWIP.Gray200} size={20} />
            <SearchInput
              autoFocus
              spellCheck={false}
              onChange={onChange}
              onKeyDown={onKeyDown}
              placeholder="Search jobs, schedules, sensors…"
              type="text"
              value={queryString}
            />
            {loading ? <Spinner purpose="body-text" /> : null}
          </SearchBox>
          <SearchResults
            highlight={highlight}
            queryString={queryString}
            results={results}
            onClickResult={onClickResult}
          />
        </Container>
      </Overlay>
    </>
  );
};

const SearchTrigger = styled.button`
  background-color: ${ColorsWIP.Gray800};
  border-radius: 24px;
  border: none;
  color: ${ColorsWIP.Gray50};
  font-size: 14px;
  cursor: pointer;
  padding: 4px 16px 4px 4px;
  outline: none;
  user-select: none;
  width: 188px;
  height: 32px;

  :focus {
    border-color: ${ColorsWIP.Gray100};
  }
`;

const Placeholder = styled.div`
  position: relative;
  top: -1px;
`;

const Container = styled.div`
  background-color: ${ColorsWIP.White};
  border-radius: 4px;
  box-shadow: 2px 2px 8px rgba(0, 0, 0, 0.1);
  max-height: 60vh;
  left: calc(50% - 300px);
  overflow: hidden;
  width: 600px;
  top: 20vh;
`;

interface SearchBoxProps {
  readonly hasQueryString: boolean;
}

const SearchBox = styled.div<SearchBoxProps>`
  align-items: center;
  border-bottom: ${({hasQueryString}) =>
    hasQueryString ? `1px solid ${ColorsWIP.Gray100}` : 'none'};
  display: flex;
  padding: 12px 20px 12px 12px;
`;

const SearchInput = styled.input`
  border: none;
  color: ${ColorsWIP.Gray600};
  font-family: ${FontFamily.default};
  font-size: 18px;
  margin-left: 4px;
  outline: none;
  width: 100%;

  &::placeholder {
    color: ${ColorsWIP.Gray200};
  }
`;

const SlashShortcut = styled.div`
  background-color: ${ColorsWIP.Gray700};
  border-radius: 3px;
  color: ${ColorsWIP.Gray100};
  font-size: 14px;
  font-family: ${FontFamily.monospace};
  padding: 2px 6px;
`;
