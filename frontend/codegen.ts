import type { CodegenConfig } from '@graphql-codegen/cli';

const config: CodegenConfig = {
  schema: '../docs/api/graphql/schema.graphql',
  documents: [
    'apps/client/src/**/*.operations.graphql',
    'apps/client/src/graphql/fragments/*.graphql',
  ],
  generates: {
    'packages/api-client/src/graphql/generated/': {
      preset: 'client',
      presetConfig: { fragmentMasking: true },
      config: {
        documentMode: 'string',
        strictScalars: true,
        defaultScalarType: 'never',
        scalars: {
          UUID: 'string',
          DateTime: 'string',
          Decimal: 'string',
          JSON: 'unknown',
        },
      },
    },
  },
  ignoreNoDocuments: true,
};

export default config;
