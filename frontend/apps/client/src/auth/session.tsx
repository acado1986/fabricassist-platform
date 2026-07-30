import {
  createAuthenticatedApiClient,
  createClient,
  bootstrapApiV1BootstrapGet,
  loginApiV1AuthLoginPost,
  logoutApiV1AuthLogoutPost,
  refreshApiV1AuthRefreshPost,
  registerApiV1AuthRegisterPost,
  type FabricAssistApiClient,
} from '@fabricassist/api-client';
import type { ReactNode } from 'react';
import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { router } from 'expo-router';
import { getApiBaseUrl } from '../config/environment';
import { secureSession } from '../platform/SecureSession';

type SessionContextValue = {
  refreshAccessToken: () => Promise<string | null>;
  apiClient: FabricAssistApiClient;
  token: string | null;
  bootstrapLogin: () => Promise<void>;
  signIn: (email: string, password: string, register: boolean) => Promise<void>;
  signOut: () => Promise<void>;
};
const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({
  children,
}: {
  children: ReactNode;
}): ReactNode {
  const [token, setToken] = useState<string | null>(null);
  const tokenRef = useRef<string | null>(null);
  const anonymousClient = useRef(createClient({ baseUrl: getApiBaseUrl() }));
  const [apiClient] = useState(() =>
    createAuthenticatedApiClient({
      baseUrl: getApiBaseUrl(),
      getAccessToken: () => tokenRef.current,
      refreshAccessToken: performRefresh,
    }),
  );
  useEffect(() => {
    void secureSession.getAccessToken().then((storedToken) => {
      tokenRef.current = storedToken;
      setToken(storedToken);
    });
  }, []);
  async function storeToken(accessToken: string): Promise<string> {
    tokenRef.current = accessToken;
    await secureSession.setAccessToken(accessToken);
    setToken(accessToken);
    return accessToken;
  }
  async function performRefresh(): Promise<string | null> {
    try {
      const result = await refreshApiV1AuthRefreshPost({
        client: anonymousClient.current,
        credentials: 'include',
        headers: { 'X-CSRF-Token': '1' },
      });
      return result.data ? storeToken(result.data.access_token) : null;
    } catch {
      return null;
    }
  }
  async function signIn(
    email: string,
    password: string,
    register: boolean,
  ): Promise<void> {
    const operation = register
      ? registerApiV1AuthRegisterPost
      : loginApiV1AuthLoginPost;
    const result = await operation({
      client: anonymousClient.current,
      body: { email, password },
      credentials: 'include',
    });
    if (!result.data) throw new Error('AUTH_FAILED');
    await storeToken(result.data.access_token);
    router.replace('/scan');
  }
  async function bootstrapLogin(): Promise<void> {
    try {
      await bootstrapApiV1BootstrapGet({
        client: anonymousClient.current,
      });
    } catch {
      // This is an opportunistic latency optimization. Sign-in remains the
      // authoritative request and retains its normal visible error handling.
    }
  }
  async function refreshAccessToken(): Promise<string | null> {
    return performRefresh();
  }
  async function signOut(): Promise<void> {
    try {
      if (token) await logoutApiV1AuthLogoutPost({ client: apiClient });
    } finally {
      // A local logout must still succeed if the access token has expired or
      // the network is unavailable. The server-side refresh token is revoked
      // whenever the request reaches the API.
      await secureSession.clear();
      tokenRef.current = null;
      setToken(null);
      router.replace('/login');
    }
  }
  return (
    <SessionContext.Provider
      value={{
        apiClient,
        token,
        signIn,
        signOut,
        refreshAccessToken,
        bootstrapLogin,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}
export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error('SessionProvider is required.');
  return value;
}
