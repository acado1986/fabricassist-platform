/** Generated client exports. Regenerate with `pnpm generate:api`; do not edit generated files. */
export * from './generated';
export { createClient } from './generated/client';
export { checkHealth } from './health';
export {
  createAuthenticatedApiClient,
  FabricAssistApiError,
  toFabricAssistApiError,
} from './authenticated';
export type { Client as FabricAssistApiClient } from './generated/client';
