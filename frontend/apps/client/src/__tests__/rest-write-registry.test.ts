import {
  REST_WRITE_REGISTRY,
  createRestWriteClient,
} from '@fabricassist/api-client';

const expectedOperations = [
  'login',
  'register',
  'refresh',
  'logout',
  'createScan',
  'addImage',
  'removeImage',
  'completeUpload',
  'requestAnalysis',
  'startRun',
  'retryRun',
  'cancelRun',
  'productLookup',
  'invalidateProductLookup',
  'postMessage',
  'confirmIdentity',
  'rejectIdentity',
  'submitFeedback',
  'deleteScan',
  'deleteGarment',
  'addServiceEvent',
  'assignReview',
  'correctReview',
  'approveReview',
  'confirmServiceEvent',
] as const;

test('every shared-app REST write has an explicit cache effect', () => {
  expect(Object.keys(REST_WRITE_REGISTRY).sort()).toEqual(
    [...expectedOperations].sort(),
  );
  expect(REST_WRITE_REGISTRY.refresh.kind).toBe('noGraphQLEffect');
});

test('cache effects run only after a successful REST write', async () => {
  const applyEffect = jest.fn();
  const client = {
    post: jest
      .fn()
      .mockResolvedValueOnce({
        data: undefined,
        error: undefined,
        response: new Response(null, { status: 204 }),
      })
      .mockResolvedValueOnce({
        data: undefined,
        error: { status: 400 },
        response: new Response(null, { status: 400 }),
      }),
  } as never;
  const writes = createRestWriteClient({ client, applyEffect });

  await writes.logout();
  await writes.logout();

  expect(applyEffect).toHaveBeenCalledTimes(1);
  expect(applyEffect).toHaveBeenCalledWith(
    'logout',
    REST_WRITE_REGISTRY.logout,
    {},
  );
});

test('aborted or rejected writes do not run cache effects', async () => {
  const applyEffect = jest.fn();
  const client = {
    post: jest.fn().mockRejectedValue(new Error('aborted')),
  } as never;
  const writes = createRestWriteClient({ client, applyEffect });

  await expect(writes.logout()).rejects.toThrow('aborted');
  expect(applyEffect).not.toHaveBeenCalled();
});

test('failed garment deletion does not apply its deletion effect', async () => {
  const applyEffect = jest.fn();
  const client = {
    delete: jest.fn().mockResolvedValue({
      data: undefined,
      error: { status: 500 },
      response: new Response(null, { status: 500 }),
    }),
  } as never;
  const writes = createRestWriteClient({ client, applyEffect });

  await writes.deleteGarment({ path: { garment_id: 'garment-1' } });

  expect(applyEffect).not.toHaveBeenCalled();
});

test('REST write context uses the current result language', async () => {
  const applyEffect = jest.fn();
  const client = {
    post: jest.fn().mockResolvedValue({
      data: { ok: true },
      error: undefined,
      response: new Response(null, { status: 200 }),
    }),
  } as never;
  const writes = createRestWriteClient({
    client,
    getLanguage: () => 'es',
    applyEffect,
  });

  await writes.submitFeedback({
    path: { scan_id: 'scan-1' },
    body: { request_review: true },
  });

  expect(applyEffect).toHaveBeenCalledWith(
    'submitFeedback',
    REST_WRITE_REGISTRY.submitFeedback,
    expect.objectContaining({ scanId: 'scan-1', language: 'es' }),
  );
});
