import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useState } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { TranslationProvider } from '../i18n/TranslationProvider';

export function AppProviders({ children }: { children: ReactNode }): ReactNode {
  const [queryClient] = useState(() => new QueryClient());

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <TranslationProvider>{children}</TranslationProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
