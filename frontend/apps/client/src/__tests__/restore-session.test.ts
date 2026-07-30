import {
  isAccessTokenUsable,
  restoreAccessToken,
} from '../auth/restoreSession';

function accessTokenWithExpiration(expirationSeconds: number): string {
  const payload = globalThis
    .btoa(JSON.stringify({ exp: expirationSeconds }))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
  return `header.${payload}.signature`;
}

test('uses the stored access token without refreshing', async () => {
  const refreshAccessToken = jest.fn<Promise<string | null>, []>();

  await expect(
    restoreAccessToken(
      async () => accessTokenWithExpiration(Date.now() / 1000 + 60),
      refreshAccessToken,
    ),
  ).resolves.toContain('.');

  expect(refreshAccessToken).not.toHaveBeenCalled();
});

test('restores a browser session through the refresh credential when needed', async () => {
  const refreshAccessToken = jest.fn(async () => 'refreshed-token');

  await expect(
    restoreAccessToken(async () => null, refreshAccessToken),
  ).resolves.toBe('refreshed-token');

  expect(refreshAccessToken).toHaveBeenCalledTimes(1);
});

test('refreshes instead of accepting an expired or malformed access token', async () => {
  const refreshAccessToken = jest.fn(async () => 'refreshed-token');
  const expiredToken = accessTokenWithExpiration(Date.now() / 1000 - 60);

  expect(isAccessTokenUsable('not-a-jwt')).toBe(false);
  expect(isAccessTokenUsable(expiredToken)).toBe(false);

  await expect(
    restoreAccessToken(async () => expiredToken, refreshAccessToken),
  ).resolves.toBe('refreshed-token');
  expect(refreshAccessToken).toHaveBeenCalledTimes(1);
});
