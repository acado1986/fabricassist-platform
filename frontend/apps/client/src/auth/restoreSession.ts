export async function restoreAccessToken(
  getStoredAccessToken: () => Promise<string | null>,
  refreshAccessToken: () => Promise<string | null>,
): Promise<string | null> {
  const storedAccessToken = await getStoredAccessToken();
  return storedAccessToken ?? refreshAccessToken();
}
