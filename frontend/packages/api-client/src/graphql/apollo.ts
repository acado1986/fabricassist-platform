import {
  ApolloClient,
  ApolloLink,
  HttpLink,
  InMemoryCache,
  Observable,
  from,
  type Operation,
  type FetchResult,
} from '@apollo/client';
import { onError } from '@apollo/client/link/error';
import { RetryLink } from '@apollo/client/link/retry';
import { getMainDefinition } from '@apollo/client/utilities';
import {
  GarmentHistoryDocument,
  ResultCompositeDocument,
} from './generated/graphql';
import type {
  CacheEffect,
  RestWriteCacheEffectContext,
  RestWriteOperation,
} from '../rest-writes';

export type ApolloClientOptions = {
  endpoint: string;
  getAccessToken: () => string | null;
  refreshAccessToken: () => Promise<string | null>;
  onAuthenticationFailure?: () => void;
};

/** Refetch only mounted queries; Apollo warns when a named query is not active. */
export async function refetchActiveGraphQLQueries(
  client: ApolloClient<unknown>,
  queryNames: readonly string[],
): Promise<void> {
  const requested = new Set(queryNames);
  const activeQueries = [...client.getObservableQueries('active').values()]
    .filter(
      (query) =>
        query.queryName !== undefined && requested.has(query.queryName),
    )
    .map((query) => query.refetch());
  // Cache synchronization is opportunistic. A stale query can legitimately
  // fail while a REST write has already succeeded (for example, when its
  // scan was deleted or replaced), and that must not turn the successful
  // write into a user-visible upload failure.
  await Promise.allSettled(activeQueries);
}

export async function synchronizeCustomerResult(
  client: ApolloClient<unknown>,
  scanId: string,
  language = 'en',
): Promise<void> {
  await client.query({
    query: ResultCompositeDocument,
    variables: { scanId, language },
    fetchPolicy: 'network-only',
  });
}

function removeFromRootConnection(
  cache: ApolloClient<unknown>['cache'],
  fieldName: string,
  deletedId: string,
): void {
  cache.modify({
    id: 'ROOT_QUERY',
    fields: {
      [fieldName](existing: unknown, helpers) {
        const store = existing as { items?: unknown[] } | undefined;
        if (!store?.items) return existing;
        return {
          ...store,
          items: store.items.filter(
            (item) =>
              helpers.readField<string>('id', item as never) !== deletedId,
          ),
        };
      },
    },
  });
}

function evictGarment(client: ApolloClient<unknown>, garmentId: string): void {
  const { cache } = client;
  for (const __typename of ['GarmentType', 'GarmentHistoryItemType']) {
    const id = cache.identify({ __typename, id: garmentId });
    if (id) cache.evict({ id });
  }
  cache.evict({ id: 'ROOT_QUERY', fieldName: 'garmentDetail' });
  removeFromRootConnection(cache, 'garmentHistory', garmentId);
  cache.gc();
}

function evictScan(client: ApolloClient<unknown>, scanId: string): void {
  const { cache } = client;
  for (const __typename of [
    'ScanType',
    'AnalysisRevisionType',
    'CareResultType',
    'AiRunType',
    'IdentityCandidateType',
  ]) {
    const id = cache.identify({ __typename, id: scanId });
    if (id) cache.evict({ id });
  }
  cache.evict({ id: 'ROOT_QUERY', fieldName: 'scanResult' });
  cache.modify({
    id: 'ROOT_QUERY',
    fields: {
      garmentHistory(existing: unknown, helpers) {
        const store = existing as { items?: unknown[] } | undefined;
        if (!store?.items) return existing;
        return {
          ...store,
          items: store.items.filter(
            (item) =>
              helpers.readField('thumbnailScanId', item as never) !== scanId,
          ),
        };
      },
    },
  });
  cache.gc();
}

export async function applyRestWriteCacheEffect(
  operation: RestWriteOperation,
  effect: CacheEffect,
  context: RestWriteCacheEffectContext,
): Promise<void> {
  const client = context.apolloClient;
  if (effect.kind === 'clear-authenticated-cache') {
    await client?.clearStore();
    return;
  }
  if (effect.kind === 'noGraphQLEffect' || !client) return;

  if (effect.kind === 'delete-garment' && context.garmentId) {
    evictGarment(client, context.garmentId);
    // History is the surviving canonical read. Never refetch the deleted detail.
    await client
      .query({
        query: GarmentHistoryDocument,
        variables: { first: 20, after: null },
        fetchPolicy: 'network-only',
      })
      .catch(() => undefined);
    return;
  }
  if (effect.kind === 'delete-scan' && context.scanId) {
    evictScan(client, context.scanId);
    return;
  }
  if (effect.kind === 'synchronize-result' && context.scanId) {
    await synchronizeCustomerResult(client, context.scanId, context.language);
    return;
  }
  if (effect.kind === 'refetch') {
    const resultQuery =
      effect.queries.includes('ResultComposite') && context.scanId
        ? synchronizeCustomerResult(client, context.scanId, context.language)
        : undefined;
    const otherQueries = effect.queries.filter(
      (queryName) => queryName !== 'ResultComposite',
    );
    const projections = [
      ...(resultQuery ? [resultQuery] : []),
      ...(otherQueries.length
        ? [refetchActiveGraphQLQueries(client, otherQueries)]
        : []),
    ];
    await Promise.allSettled(projections);
  }
}

function isQuery(operation: Operation): boolean {
  const definition = getMainDefinition(operation.query);
  return (
    definition.kind === 'OperationDefinition' &&
    definition.operation === 'query'
  );
}

function isAuthenticationFailure(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false;
  const statusCode = 'statusCode' in error ? error.statusCode : undefined;
  return statusCode === 401;
}

function authRetryLink({
  refreshAccessToken,
  onAuthenticationFailure,
}: Pick<
  ApolloClientOptions,
  'refreshAccessToken' | 'onAuthenticationFailure'
>): ApolloLink {
  return onError(({ graphQLErrors, networkError, operation, forward }) => {
    const unauthenticated = graphQLErrors?.some(
      (error) => error.extensions?.['code'] === 'UNAUTHENTICATED',
    );
    if (
      (!unauthenticated && !isAuthenticationFailure(networkError)) ||
      operation.getContext().authRetried === true
    ) {
      return undefined;
    }
    operation.setContext({ authRetried: true });
    return new Observable<FetchResult>((observer) => {
      let subscription: { unsubscribe: () => void } | undefined;
      void refreshAccessToken()
        .then((token) => {
          if (!token) {
            onAuthenticationFailure?.();
            observer.error(new Error('UNAUTHENTICATED'));
            return;
          }
          operation.setContext(
            ({ headers = {} }: { headers?: Record<string, string> }) => ({
              headers: { ...headers, Authorization: `Bearer ${token}` },
            }),
          );
          subscription = forward(operation).subscribe(
            (value) => observer.next(value),
            (error: unknown) => observer.error(error),
            () => observer.complete(),
          );
        })
        .catch((error: unknown) => {
          onAuthenticationFailure?.();
          observer.error(error);
        });
      return () => subscription?.unsubscribe();
    });
  });
}

export function createApolloClient({
  endpoint,
  getAccessToken,
  refreshAccessToken,
  onAuthenticationFailure,
}: ApolloClientOptions): ApolloClient<unknown> {
  const authLink = new ApolloLink((operation, forward) => {
    operation.setContext(
      ({ headers = {} }: { headers?: Record<string, string> }) => {
        const token = getAccessToken();
        return {
          headers: {
            ...headers,
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            'X-Correlation-ID':
              globalThis.crypto?.randomUUID?.() ?? `fa-${Date.now()}`,
          },
        };
      },
    );
    return forward(operation);
  });
  const retryLink = new RetryLink({
    delay: { initial: 300, max: 2_000, jitter: true },
    attempts: {
      max: 2,
      retryIf: (error: unknown, operation: Operation) =>
        isQuery(operation) &&
        !operation.getContext().authRetried &&
        Boolean(error),
    },
  });
  const httpLink = new HttpLink({
    uri: endpoint,
    credentials: 'include',
  });
  return new ApolloClient({
    cache: new InMemoryCache({
      typePolicies: {
        CurrentUserType: { keyFields: ['id'] },
        ScanType: { keyFields: ['id'] },
        GarmentType: { keyFields: ['id'] },
        GarmentDetailType: {
          keyFields: ['id'],
          fields: {
            analyses: {
              merge(existing, incoming) {
                const items = [...(existing?.items ?? [])];
                const seen = new Set(
                  items.map((item: { scanId: string }) => item.scanId),
                );
                for (const item of incoming.items as { scanId: string }[]) {
                  if (!seen.has(item.scanId)) items.push(item);
                }
                return { ...incoming, items };
              },
            },
          },
        },
        GarmentHistoryItemType: { keyFields: ['id'] },
        ConversationMessageType: { keyFields: ['id'] },
        AnalysisRevisionType: { keyFields: ['id'] },
        CareResultType: { keyFields: ['id'] },
        IdentityCandidateType: { keyFields: ['id'] },
        AiRunType: { keyFields: ['id'] },
        ScanImageMetadataType: { keyFields: ['id'] },
        Query: {
          fields: {
            garmentHistory: {
              keyArgs: false,
              merge(existing, incoming, { args }) {
                // The first page is a canonical snapshot. Replacing it is
                // important after a garment deletion; appending every server
                // response would resurrect deleted items from the memory
                // cache. Only cursor-based pages append.
                if (args?.after == null) return incoming;
                const items = [...(existing?.items ?? [])];
                const seen = new Set(
                  items.map((item: { id: string }) => item.id),
                );
                for (const item of incoming.items as { id: string }[]) {
                  if (!seen.has(item.id)) items.push(item);
                }
                return { ...incoming, items };
              },
            },
            messages: {
              keyArgs: ['scanId'],
              merge(existing, incoming) {
                const items = [...(existing?.items ?? [])];
                const seen = new Set(
                  items.map((item: { id: string }) => item.id),
                );
                for (const item of incoming.items as { id: string }[]) {
                  if (!seen.has(item.id)) items.push(item);
                }
                return { ...incoming, items };
              },
            },
            scanResult: {
              keyArgs: ['scanId', 'language'],
            },
          },
        },
      },
    }),
    link: from([
      authRetryLink({ refreshAccessToken, onAuthenticationFailure }),
      authLink,
      retryLink,
      httpLink,
    ]),
    defaultOptions: {
      watchQuery: { fetchPolicy: 'cache-first', errorPolicy: 'none' },
      query: { fetchPolicy: 'cache-first', errorPolicy: 'none' },
    },
  });
}
