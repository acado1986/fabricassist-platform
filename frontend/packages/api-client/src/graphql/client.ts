import { FabricAssistApiError } from '../authenticated';
import type { DocumentTypeDecoration } from '@graphql-typed-document-node/core';

/** Codegen's TypedDocumentString is intentionally a string-like object. */
export type GraphQLDocument<TResult, TVariables> =
  | (DocumentTypeDecoration<TResult, TVariables> & { toString(): string })
  | string;

export type GraphQLExecutor = <
  TResult,
  TVariables extends Record<string, unknown>,
>(
  document: GraphQLDocument<TResult, TVariables>,
  variables: TVariables,
  signal?: AbortSignal,
) => Promise<TResult>;

export class FabricAssistGraphQLError extends FabricAssistApiError {
  readonly path?: readonly (string | number)[];

  constructor(
    code: string,
    message: string,
    options: {
      correlationId?: string;
      path?: readonly (string | number)[];
    } = {},
  ) {
    super(code, message, { correlationId: options.correlationId });
    this.name = 'FabricAssistGraphQLError';
    this.path = options.path;
  }
}

type GraphQLErrorPayload = {
  message: string;
  path?: (string | number)[];
  extensions?: { code?: string; correlation_id?: string };
};

type GraphQLPayload<T> = { data?: T; errors?: GraphQLErrorPayload[] };

export type GraphQLExecutorOptions = {
  endpoint: string;
  getAccessToken: () => string | null;
  refreshAccessToken: () => Promise<string | null>;
};

function correlationId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `fa-${Date.now()}`;
}

export function createGraphQLExecutor({
  endpoint,
  getAccessToken,
  refreshAccessToken,
}: GraphQLExecutorOptions): GraphQLExecutor {
  return async function execute<
    TResult,
    TVariables extends Record<string, unknown>,
  >(
    document: GraphQLDocument<TResult, TVariables>,
    variables: TVariables,
    signal?: AbortSignal,
  ): Promise<TResult> {
    const run = async (token: string | null): Promise<Response> =>
      fetch(endpoint, {
        method: 'POST',
        credentials: 'include',
        signal,
        headers: {
          'Content-Type': 'application/json',
          'X-Correlation-ID': correlationId(),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ query: document.toString(), variables }),
      });
    let token = getAccessToken();
    let response = await run(token);
    if (response.status === 401) {
      token = await refreshAccessToken();
      if (token) response = await run(token);
    }
    let payload: GraphQLPayload<TResult>;
    try {
      payload = (await response.json()) as GraphQLPayload<TResult>;
    } catch {
      throw new FabricAssistGraphQLError(
        response.ok ? 'GRAPHQL_INVALID_RESPONSE' : 'API_REQUEST_FAILED',
        'The FabricAssist API returned an invalid response.',
      );
    }
    const error = payload.errors?.[0];
    if (error) {
      throw new FabricAssistGraphQLError(
        error.extensions?.code ?? 'GRAPHQL_ERROR',
        error.message,
        {
          correlationId: error.extensions?.correlation_id,
          path: error.path,
        },
      );
    }
    if (!response.ok || payload.data === undefined) {
      throw new FabricAssistGraphQLError(
        'API_REQUEST_FAILED',
        'The FabricAssist API rejected the request.',
      );
    }
    return payload.data;
  };
}
