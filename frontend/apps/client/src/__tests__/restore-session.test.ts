import { restoreAccessToken } from '../auth/restoreSession';

test('uses the stored access token without refreshing', async () => {
  const refreshAccessToken = jest.fn<Promise<string | null>, []>();

  await expect(
    restoreAccessToken(async () => 'stored-token', refreshAccessToken),
  ).resolves.toBe('stored-token');

  expect(refreshAccessToken).not.toHaveBeenCalled();
});

test('restores a browser session through the refresh credential when needed', async () => {
  const refreshAccessToken = jest.fn(async () => 'refreshed-token');

  await expect(
    restoreAccessToken(async () => null, refreshAccessToken),
  ).resolves.toBe('refreshed-token');

  expect(refreshAccessToken).toHaveBeenCalledTimes(1);
});
