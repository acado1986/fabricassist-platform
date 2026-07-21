import * as SecureStore from 'expo-secure-store';
const key = 'fabricassist_access_token';
export const secureSession = {
  async getAccessToken(): Promise<string | null> {
    return SecureStore.getItemAsync(key);
  },
  async setAccessToken(token: string): Promise<void> {
    await SecureStore.setItemAsync(key, token);
  },
  async clear(): Promise<void> {
    await SecureStore.deleteItemAsync(key);
  },
};
