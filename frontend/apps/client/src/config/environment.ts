import Constants from 'expo-constants';

const fallbackApiUrl = 'http://localhost:8000';

export function getApiBaseUrl(): string {
  const configuredUrl = Constants.expoConfig?.extra?.fabricassistApiPublicUrl;
  const candidate =
    typeof configuredUrl === 'string' ? configuredUrl : fallbackApiUrl;
  const parsedUrl = new URL(candidate);

  if (parsedUrl.protocol !== 'http:' && parsedUrl.protocol !== 'https:') {
    throw new Error('EXPO_PUBLIC_FABRICASSIST_API_URL must use http or https.');
  }

  return parsedUrl.toString().replace(/\/$/, '');
}
