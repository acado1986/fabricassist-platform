import type { ReactNode } from 'react';
import { Link } from 'expo-router';
import { Text } from 'react-native';

import { FoundationShell } from '../components/FoundationShell';
import { useTranslation } from '../i18n/TranslationProvider';

export default function NotFoundScreen(): ReactNode {
  const { translate } = useTranslation();
  return (
    <FoundationShell>
      <Text accessibilityRole="header">{translate('notFoundTitle')}</Text>
      <Text>{translate('notFoundDescription')}</Text>
      <Link href="/">{translate('goHome')}</Link>
    </FoundationShell>
  );
}
