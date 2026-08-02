import {
  createAuthenticatedApiClient,
  createClient,
  createApolloClient,
  createRestWriteClient,
  applyRestWriteCacheEffect,
  bootstrapApiV1BootstrapGet,
  type FabricAssistApiClient,
} from '@fabricassist/api-client';
import type { ApolloClient } from '@apollo/client';
import { useQueryClient } from '@tanstack/react-query';
import { ApolloProvider } from '@apollo/client';
import type { ReactNode } from 'react';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { router } from 'expo-router';
import { getApiBaseUrl } from '../config/environment';
import { secureSession } from '../platform/SecureSession';
import { restoreAccessToken } from './restoreSession';
import { useTranslation } from '../i18n/TranslationProvider';

type SessionContextValue = {
  refreshAccessToken: () => Promise<string | null>;
  apiClient: FabricAssistApiClient;
  apolloClient: ApolloClient<unknown>;
  restWrites: ReturnType<typeof createRestWriteClient>;
  isSessionReady: boolean;
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
  const queryClient = useQueryClient();
  const { locale } = useTranslation();
  const localeRef = useRef(locale);
  localeRef.current = locale;
  const [isSessionReady, setIsSessionReady] = useState(false);
  const tokenRef = useRef<string | null>(null);
  const refreshInFlight = useRef<Promise<string | null> | null>(null);
  const apolloClientRef = useRef<ApolloClient<unknown> | null>(null);
  const anonymousClient = useRef(createClient({ baseUrl: getApiBaseUrl() }));
  const [anonymousWrites] = useState(() =>
    createRestWriteClient({
      client: anonymousClient.current,
      applyEffect: async (_operation, effect) => {
        if (effect.kind === 'clear-authenticated-cache') {
          await apolloClientRef.current?.clearStore();
        }
      },
    }),
  );
  const storeToken = useCallback(
    async (accessToken: string): Promise<string> => {
      tokenRef.current = accessToken;
      await secureSession.setAccessToken(accessToken);
      setToken(accessToken);
      return accessToken;
    },
    [],
  );
  const performRefresh = useCallback((): Promise<string | null> => {
    if (refreshInFlight.current) return refreshInFlight.current;
    const request = (async (): Promise<string | null> => {
      try {
        const result = await anonymousWrites.refresh({
          credentials: 'include',
          headers: { 'X-CSRF-Token': '1' },
        });
        return result.data ? storeToken(result.data.access_token) : null;
      } catch {
        return null;
      } finally {
        refreshInFlight.current = null;
      }
    })();
    refreshInFlight.current = request;
    return request;
  }, [anonymousWrites, storeToken]);
  const [apiClient] = useState(() =>
    createAuthenticatedApiClient({
      baseUrl: getApiBaseUrl(),
      getAccessToken: () => tokenRef.current,
      refreshAccessToken: performRefresh,
    }),
  );
  const [apolloClient] = useState(() => {
    const client = createApolloClient({
      endpoint: `${getApiBaseUrl()}/api/v1/graphql`,
      getAccessToken: () => tokenRef.current,
      refreshAccessToken: performRefresh,
      onAuthenticationFailure: () => {
        tokenRef.current = null;
        setToken(null);
        void apolloClientRef.current?.clearStore();
        queryClient.clear();
      },
    });
    apolloClientRef.current = client;
    return client;
  });
  const [restWrites] = useState(() =>
    createRestWriteClient({
      client: apiClient,
      getLanguage: () => localeRef.current,
      applyEffect: async (operation, effect, context) => {
        await applyRestWriteCacheEffect(operation, effect, {
          ...context,
          apolloClient,
        });
      },
    }),
  );
  useEffect(() => {
    let active = true;

    void restoreAccessToken(secureSession.getAccessToken, performRefresh)
      .then((accessToken) => {
        if (!active || !accessToken) return;
        tokenRef.current = accessToken;
        setToken(accessToken);
      })
      .finally(() => {
        if (active) setIsSessionReady(true);
      });

    return () => {
      active = false;
    };
  }, [performRefresh]);
  async function signIn(
    email: string,
    password: string,
    register: boolean,
  ): Promise<void> {
    await apolloClient.clearStore();
    queryClient.clear();
    const operation = register
      ? anonymousWrites.register
      : anonymousWrites.login;
    const result = await operation({
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
      if (token) await restWrites.logout();
    } finally {
      // A local logout must still succeed if the access token has expired or
      // the network is unavailable. The server-side refresh token is revoked
      // whenever the request reaches the API.
      await secureSession.clear();
      await apolloClient.clearStore();
      queryClient.clear();
      tokenRef.current = null;
      setToken(null);
      router.replace('/login');
    }
  }
  return (
    <ApolloProvider client={apolloClient}>
      <SessionContext.Provider
        value={{
          apiClient,
          apolloClient,
          restWrites,
          isSessionReady,
          token,
          signIn,
          signOut,
          refreshAccessToken,
          bootstrapLogin,
        }}
      >
        {children}
      </SessionContext.Provider>
    </ApolloProvider>
  );
}
export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error('SessionProvider is required.');
  return value;
}
