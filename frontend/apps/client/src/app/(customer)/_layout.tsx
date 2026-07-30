import type { ReactNode } from 'react';
import { Redirect, Stack } from 'expo-router';

import { useSession } from '../../auth/session';

export default function CustomerLayout(): ReactNode {
  const { isSessionReady, token } = useSession();

  if (!isSessionReady) return null;
  if (!token) return <Redirect href="/login" />;
  return (
    <Stack>
      <Stack.Screen name="scan" options={{ headerShown: false }} />
      <Stack.Screen name="result" options={{ headerShown: false }} />
      <Stack.Screen name="images" options={{ headerShown: false }} />
      <Stack.Screen name="chat" options={{ headerShown: false }} />
      <Stack.Screen
        name="garments/[garmentId]"
        options={{ headerShown: false }}
      />
      <Stack.Screen name="history" options={{ headerShown: false }} />
    </Stack>
  );
}
