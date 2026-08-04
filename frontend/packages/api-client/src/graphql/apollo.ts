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
  await Promise.all(activeQueries);
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
            messages: {
              keyArgs: ['scanId'],
              merge(existing, incoming) {
                const incomingItems = incoming.items as { id: string }[];
                const incomingById = new Map(
                  incomingItems.map((item) => [item.id, item]),
                );
                const items = (existing?.items ?? []).map(
                  (item: { id: string }) => incomingById.get(item.id) ?? item,
                );
                const existingIds = new Set(items.map((item) => item.id));
                items.push(
                  ...incomingItems.filter((item) => !existingIds.has(item.id)),
                );
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
