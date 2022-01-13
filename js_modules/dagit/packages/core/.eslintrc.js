const fs = require('fs');
const path = require('path');

const schemaPath = path.resolve(path.join(__dirname, 'src', 'graphql', 'schema.graphql'));
const schema = fs.readFileSync(schemaPath).toString();
module.exports = {
  parser: '@typescript-eslint/parser',
  // Specifies the ESLint parser
  extends: [
    'plugin:react/recommended',
    'plugin:@typescript-eslint/recommended',
    'prettier',
    'plugin:prettier/recommended',
    'plugin:storybook/recommended',
  ],
  plugins: ['react-hooks', 'import', 'graphql'],
  parserOptions: {
    ecmaVersion: 2018,
    // Allows for the parsing of modern ECMAScript features
    sourceType: 'module',
    // Allows for the use of imports
    ecmaFeatures: {
      jsx: true, // Allows for the parsing of JSX
    },
  },
  rules: {
    curly: 'error',
    eqeqeq: [
      'error',
      'always',
      {
        null: 'ignore',
      },
    ],
    'graphql/required-fields': [
      'error',
      {
        env: 'apollo',
        schemaString: schema,
        requiredFields: ['id'],
      },
    ],
    'import/no-cycle': 'error',
    'import/no-default-export': 'error',
    'import/no-duplicates': 'error',
    'import/order': [
      'error',
      {
        alphabetize: {
          order: 'asc',
          caseInsensitive: false,
        },
        'newlines-between': 'always',
      },
    ],
    'no-alert': 'error',
    'no-restricted-imports': [
      'error',
      {
        patterns: ['!styled-components/macro'],
        paths: [
          {
            name: '@blueprintjs/core',
            importNames: [
              'Alert',
              'Button',
              'ButtonGroup',
              'Callout',
              'Checkbox',
              'Colors',
              'Dialog',
              'Icon',
              'InputGroup',
              'Menu',
              'MenuDivider',
              'MenuItem',
              'NonIdealState',
              'Popover',
              'Select',
              'Suggest',
              'Spinner',
              'Switch',
              'Tab',
              'Tabs',
              'Tag',
              'Toast',
              'Toaster',
              'Tooltip',
            ],
            message: 'Please use components in src/ui instead.',
          },
          {
            name: '@blueprintjs/popover2',
            importNames: ['Popover2', 'Tooltip2'],
            message: 'Please use components in src/ui instead.',
          },
          {
            name: '@blueprintjs/select',
            message: 'Please use components in src/ui instead.',
          },
          {
            name: 'graphql-tag',
            message: 'Please import from `@apollo/client`.',
          },
          {
            name: 'styled-components',
            message: 'Please import from `styled-components/macro`.',
          },
        ],
      },
    ],
    'react/jsx-curly-brace-presence': 'error',
    'react/jsx-no-target-blank': 'error',
    'react/prefer-stateless-function': 'error',
    'react/prop-types': 'off',
    'react/display-name': 'off',
    '@typescript-eslint/no-unused-vars': [
      'error',
      {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        ignoreRestSiblings: true,
      },
    ],
    '@typescript-eslint/interface-name-prefix': 'off',
    '@typescript-eslint/explicit-function-return-type': 'off',
    '@typescript-eslint/explicit-member-accessibility': 'off',
    '@typescript-eslint/explicit-module-boundary-types': 'off',
    '@typescript-eslint/camelcase': 'off',
    '@typescript-eslint/no-empty-function': 'off',
    '@typescript-eslint/no-explicit-any': 'off',
    '@typescript-eslint/no-empty-function': 'off',
    '@typescript-eslint/array-type': 'off',
    '@typescript-eslint/no-use-before-define': 'off',
    '@typescript-eslint/no-non-null-assertion': 'off',
    '@typescript-eslint/prefer-interface': 'off',
    '@typescript-eslint/no-empty-interface': 'off',
    'react-hooks/rules-of-hooks': 'error',
    'react-hooks/exhaustive-deps': 'warn',
  },
  settings: {
    'import/internal-regex': '^src/',
    react: {
      version: 'detect', // Tells eslint-plugin-react to automatically detect the version of React to use
    },
  },
};
