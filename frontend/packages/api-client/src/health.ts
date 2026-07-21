import { client } from './generated/client.gen';
import { liveApiV1HealthLiveGet } from './generated';

export async function checkHealth(apiBaseUrl: string): Promise<boolean> {
  client.setConfig({ baseUrl: apiBaseUrl });
  const result = await liveApiV1HealthLiveGet({ throwOnError: false });
  return result.data?.status === 'ok';
}
