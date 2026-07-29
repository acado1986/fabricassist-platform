import {
  createAuthenticatedApiClient,
  FabricAssistApiError,
  scanDetailApiV1ScansScanIdGet,
  toFabricAssistApiError,
} from '@fabricassist/api-client';

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

test('normalizes the shared FabricAssist error envelope', () => {
  const error = toFabricAssistApiError(
    {
      error: {
        code: 'SCAN_NOT_FOUND',
        message: 'Scan was not found.',
        details: { safe: true },
        correlation_id: 'correlation-id',
      },
    },
    new Response(null, { status: 404 }),
  );

  expect(error).toBeInstanceOf(FabricAssistApiError);
  expect(error.code).toBe('SCAN_NOT_FOUND');
  expect(error.status).toBe(404);
  expect(error.correlationId).toBe('correlation-id');
});

test('injects auth and correlation and retries one 401 after refresh', async () => {
  const requests: Request[] = [];
  let token = 'old-token';
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    requests.push(request);
    if (requests.length === 1) {
      return new Response(
        JSON.stringify({
          error: { code: 'TOKEN_EXPIRED', message: 'Expired.' },
        }),
        { status: 401, headers: { 'content-type': 'application/json' } },
      );
    }
    return new Response(
      JSON.stringify({
        scan_id: '00000000-0000-0000-0000-000000000001',
        status: 'queued',
        images_completed: 1,
        progress_percent: 10,
      }),
      { status: 200, headers: { 'content-type': 'application/json' } },
    );
  };
  const client = createAuthenticatedApiClient({
    baseUrl: 'https://api.example.test',
    getAccessToken: () => token,
    refreshAccessToken: async () => {
      token = 'new-token';
      return token;
    },
  });

  const result = await scanDetailApiV1ScansScanIdGet({
    client,
    path: { scan_id: '00000000-0000-0000-0000-000000000001' },
  });

  expect(result.data?.status).toBe('queued');
  expect(requests).toHaveLength(2);
  expect(requests[0]?.headers.get('authorization')).toBe('Bearer old-token');
  expect(requests[1]?.headers.get('authorization')).toBe('Bearer new-token');
  expect(requests[0]?.headers.get('x-correlation-id')).toBe(
    requests[1]?.headers.get('x-correlation-id'),
  );
});
