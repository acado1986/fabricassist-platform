const { defineConfig } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');

module.exports = defineConfig([
  ...expoConfig,
  {
    ignores: [
      'node_modules/',
      '.expo/',
      '**/dist/**',
      'packages/api-client/src/generated/',
    ],
  },
  {
    // Expo 57's React Compiler rules are not yet compatible with these
    // established provider/effect patterns.
    rules: {
      'react-hooks/refs': 'off',
      'react-hooks/set-state-in-effect': 'off',
    },
  },
]);
