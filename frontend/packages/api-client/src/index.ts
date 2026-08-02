/** Generated client exports. Regenerate with `pnpm generate:api`; do not edit generated files. */
export * from './generated';
export { createClient } from './generated/client';
export * from './graphql/generated';
export * from './graphql/generated/graphql';
export { checkHealth } from './health';
export {
  createAuthenticatedApiClient,
  FabricAssistApiError,
  toFabricAssistApiError,
} from './authenticated';
export type { Client as FabricAssistApiClient } from './generated/client';
export {
  createApolloClient,
  refetchActiveGraphQLQueries,
  synchronizeCustomerResult,
  applyRestWriteCacheEffect,
} from './graphql/apollo';
export type { ApolloClientOptions } from './graphql/apollo';
export { RunStreamLifecycle } from './run-stream';
export type { RunStreamLifecycleOptions } from './run-stream';
export { createRestWriteClient, REST_WRITE_REGISTRY } from './rest-writes';
export type {
  CacheEffect,
  RestWriteEffectHandler,
  RestWriteCacheEffectContext,
  RestWriteOperation,
} from './rest-writes';
export {
  parseUuid,
  type DateTime,
  type Decimal,
  type UUID,
} from './graphql/scalars';
export {
  SseFrameParser,
  parseRunEvent,
  streamRunEvents,
  type ParsedSseEvent,
  type RunEvent,
} from './graphql/sse';
