import type { ReactNode } from 'react';
import { Stack } from 'expo-router';

import { AppProviders } from '../providers/AppProviders';

export default function RootLayout(): ReactNode {
  return (
    <AppProviders>
      <Stack screenOptions={{ headerShown: false }} />
    </AppProviders>
  );
}
