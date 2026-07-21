import { createContext, useContext, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { catalogs } from '@fabricassist/translations';
import type {
  SupportedLocale,
  TranslationKey,
} from '@fabricassist/translations';

type TranslationContextValue = {
  locale: SupportedLocale;
  setLocale: (locale: SupportedLocale) => void;
  translate: (key: TranslationKey) => string;
};

const TranslationContext = createContext<TranslationContextValue | null>(null);

export function TranslationProvider({
  children,
}: {
  children: ReactNode;
}): ReactNode {
  const [locale, setLocale] = useState<SupportedLocale>('en');
  const value = useMemo<TranslationContextValue>(
    () => ({
      locale,
      setLocale,
      translate: (key) => catalogs[locale].shell[key],
    }),
    [locale],
  );

  return (
    <TranslationContext.Provider value={value}>
      {children}
    </TranslationContext.Provider>
  );
}

export function useTranslation(): TranslationContextValue {
  const context = useContext(TranslationContext);
  if (context === null) {
    throw new Error('useTranslation must be used within TranslationProvider.');
  }
  return context;
}
