export const secureSession = {
  async getAccessToken(): Promise<string | null> {
    return sessionStorage.getItem('fabricassist_access_token');
  },
  async setAccessToken(token: string): Promise<void> {
    sessionStorage.setItem('fabricassist_access_token', token);
  },
  async clear(): Promise<void> {
    sessionStorage.removeItem('fabricassist_access_token');
  },
};
