import type { ReactNode } from 'react';
import { Stack } from 'expo-router';
import { AppProviders } from '../providers/AppProviders';
import { SessionProvider } from '../auth/session';
export default function RootLayout(): ReactNode {
  return (
    <AppProviders>
      <SessionProvider>
        <Stack>
          <Stack.Screen name="index" options={{ headerShown: false }} />
          <Stack.Screen name="(auth)/login" options={{ headerShown: false }} />
          <Stack.Screen
            name="(auth)/register"
            options={{ headerShown: false }}
          />
          <Stack.Screen
            name="(customer)/scan"
            options={{ headerShown: false }}
          />
          <Stack.Screen
            name="(customer)/result"
            options={{ headerShown: false }}
          />
          <Stack.Screen
            name="(customer)/chat"
            options={{ headerShown: false }}
          />
          <Stack.Screen
            name="(customer)/garments/[garmentId]"
            options={{ headerShown: false }}
          />
          <Stack.Screen
            name="(customer)/history"
            options={{ headerShown: false }}
          />
          <Stack.Screen
            name="(operator)/review"
            options={{ headerShown: false }}
          />
        </Stack>
      </SessionProvider>
    </AppProviders>
  );
}
