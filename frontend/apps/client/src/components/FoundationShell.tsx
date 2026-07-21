import type { ReactNode } from 'react';
import { Text, View } from 'react-native';
import { colors, spacing } from '@fabricassist/design-tokens';

import { LanguageSelector } from './LanguageSelector';
import { useTranslation } from '../i18n/TranslationProvider';

export function FoundationShell({
  children,
}: {
  children: ReactNode;
}): ReactNode {
  const { translate } = useTranslation();

  return (
    <View
      style={{
        backgroundColor: colors.background,
        flex: 1,
        gap: spacing.medium,
        padding: spacing.large,
      }}
    >
      <Text
        accessibilityRole="header"
        style={{ color: colors.text, fontSize: 28, fontWeight: '700' }}
      >
        {translate('title')}
      </Text>
      <Text style={{ color: colors.muted, fontSize: 18 }}>
        {translate('foundation')}
      </Text>
      <LanguageSelector />
      {children}
    </View>
  );
}
