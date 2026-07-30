import { createClient, type Client } from './generated/client';

type AuthenticatedClientOptions = {
  baseUrl: string;
  getAccessToken: () => string | null;
  refreshAccessToken: () => Promise<string | null>;
};

type ErrorEnvelope = {
  error: {
    code: string;
    message: string;
    details?: unknown;
    correlation_id?: string;
  };
};

export class FabricAssistApiError extends Error {
  readonly code: string;
  readonly correlationId?: string;
  readonly details?: unknown;
  readonly status?: number;

  constructor(
    code: string,
    message: string,
    options: {
      correlationId?: string;
      details?: unknown;
      status?: number;
    } = {},
  ) {
    super(message);
    this.name = 'FabricAssistApiError';
    this.code = code;
    this.correlationId = options.correlationId;
    this.details = options.details;
    this.status = options.status;
  }
}

function correlationId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `fa-${Date.now()}`;
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (!value || typeof value !== 'object' || !('error' in value)) return false;
  const error = value.error;
  return (
    error !== null &&
    typeof error === 'object' &&
    'code' in error &&
    typeof error.code === 'string' &&
    'message' in error &&
    typeof error.message === 'string'
  );
}

export function toFabricAssistApiError(
  error: unknown,
  response?: Response,
): FabricAssistApiError {
  if (error instanceof FabricAssistApiError) return error;
  if (isErrorEnvelope(error)) {
    return new FabricAssistApiError(error.error.code, error.error.message, {
      correlationId: error.error.correlation_id,
      details: error.error.details,
      status: response?.status,
    });
  }
  return new FabricAssistApiError(
    response ? 'API_REQUEST_FAILED' : 'API_NETWORK_ERROR',
    response
      ? 'The FabricAssist API rejected the request.'
      : 'The FabricAssist API is temporarily unavailable.',
    { status: response?.status },
  );
}

export function createAuthenticatedApiClient({
  baseUrl,
  getAccessToken,
  refreshAccessToken,
}: AuthenticatedClientOptions): Client {
  const authenticatedFetch: typeof fetch = async (input, init) => {
    const request = new Request(input, init);
    const headers = new Headers(request.headers);
    const token = getAccessToken();
    if (token) headers.set('Authorization', `Bearer ${token}`);
    if (!headers.has('X-Correlation-ID')) {
      headers.set('X-Correlation-ID', correlationId());
    }
    const execute = (accessToken: string | null): Promise<Response> => {
      const nextHeaders = new Headers(headers);
      if (accessToken)
        nextHeaders.set('Authorization', `Bearer ${accessToken}`);
      return fetch(
        new Request(request, {
          credentials: 'include',
          headers: nextHeaders,
        }),
      );
    };
    const response = await execute(token);
    if (
      response.status !== 401 ||
      request.url.includes('/api/v1/auth/refresh')
    ) {
      return response;
    }
    const refreshedToken = await refreshAccessToken();
    return refreshedToken ? execute(refreshedToken) : response;
  };
  const client = createClient({ baseUrl, fetch: authenticatedFetch });
  client.interceptors.error.use((error, response) =>
    toFabricAssistApiError(error, response),
  );
  return client;
}
