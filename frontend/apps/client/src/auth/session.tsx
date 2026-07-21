import type { ReactNode } from 'react';
import { createContext, useContext, useEffect, useState } from 'react';
import { router } from 'expo-router';
import { getApiBaseUrl } from '../config/environment';
import { secureSession } from '../platform/SecureSession';

type SessionContextValue = {
  refreshAccessToken: () => Promise<string | null>;
  token: string | null;
  signIn: (email: string, password: string, register: boolean) => Promise<void>;
  signOut: () => Promise<void>;
};
const SessionContext = createContext<SessionContextValue | null>(null);

type SessionResponse = { access_token: string };

export function SessionProvider({
  children,
}: {
  children: ReactNode;
}): ReactNode {
  const [token, setToken] = useState<string | null>(null);
  useEffect(() => {
    void secureSession.getAccessToken().then(setToken);
  }, []);
  async function signIn(
    email: string,
    password: string,
    register: boolean,
  ): Promise<void> {
    const response = await fetch(
      `${getApiBaseUrl()}/api/v1/auth/${register ? 'register' : 'login'}`,
      {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      },
    );
    if (!response.ok) throw new Error('AUTH_FAILED');
    const payload = (await response.json()) as SessionResponse;
    await secureSession.setAccessToken(payload.access_token);
    setToken(payload.access_token);
    router.replace('/scan');
  }
  async function refreshAccessToken(): Promise<string | null> {
    try {
      const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRF-Token': '1' },
      });
      if (!response.ok) return null;
      const payload = (await response.json()) as SessionResponse;
      await secureSession.setAccessToken(payload.access_token);
      setToken(payload.access_token);
      return payload.access_token;
    } catch {
      return null;
    }
  }
  async function signOut(): Promise<void> {
    if (token)
      await fetch(`${getApiBaseUrl()}/api/v1/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
    await secureSession.clear();
    setToken(null);
    router.replace('/login');
  }
  return (
    <SessionContext.Provider
      value={{ token, signIn, signOut, refreshAccessToken }}
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
