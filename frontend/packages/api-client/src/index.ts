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
  createGraphQLExecutor,
  FabricAssistGraphQLError,
} from './graphql/client';
export {
  parseUuid,
  type DateTime,
  type Decimal,
  type UUID,
} from './graphql/scalars';
export {
  SseFrameParser,
  streamRunEvents,
  type ParsedSseEvent,
  type RunEvent,
} from './graphql/sse';
