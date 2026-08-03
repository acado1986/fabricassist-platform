import Constants from 'expo-constants';

const fallbackApiUrl = 'http://localhost:8000';

export function getApiBaseUrl(): string {
  const configuredUrl = Constants.expoConfig?.extra?.fabricassistApiPublicUrl;
  const candidate =
    typeof configuredUrl === 'string' && configuredUrl.trim().length > 0
      ? configuredUrl.trim()
      : fallbackApiUrl;
  let parsedUrl: URL;
  try {
    parsedUrl = new URL(candidate);
  } catch {
    parsedUrl = new URL(fallbackApiUrl);
  }

  if (parsedUrl.protocol !== 'http:' && parsedUrl.protocol !== 'https:') {
    throw new Error('EXPO_PUBLIC_FABRICASSIST_API_URL must use http or https.');
  }

  return parsedUrl.toString().replace(/\/$/, '');
}
