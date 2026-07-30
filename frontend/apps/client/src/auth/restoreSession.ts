export function isAccessTokenUsable(accessToken: string): boolean {
  const encodedPayload = accessToken.split('.')[1];
  if (!encodedPayload) return false;

  try {
    const payload = JSON.parse(
      globalThis.atob(encodedPayload.replace(/-/g, '+').replace(/_/g, '/')),
    ) as { exp?: unknown };
    return typeof payload.exp === 'number' && payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

export async function restoreAccessToken(
  getStoredAccessToken: () => Promise<string | null>,
  refreshAccessToken: () => Promise<string | null>,
): Promise<string | null> {
  const storedAccessToken = await getStoredAccessToken();
  return storedAccessToken && isAccessTokenUsable(storedAccessToken)
    ? storedAccessToken
    : refreshAccessToken();
}
