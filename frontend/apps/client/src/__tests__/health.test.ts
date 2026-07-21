import { checkHealth } from '@fabricassist/api-client';

test('health diagnostics uses the generated health client contract', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = jest.fn(
    async () =>
      new Response(JSON.stringify({ status: 'ok' }), {
        headers: { 'Content-Type': 'application/json' },
      }),
  );

  await expect(checkHealth('http://localhost:8000')).resolves.toBe(true);
  globalThis.fetch = originalFetch;
});
