import type { ReactNode } from 'react';
import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { checkHealth } from '@fabricassist/api-client';

import { FoundationShell } from '../components/FoundationShell';
import { getApiBaseUrl } from '../config/environment';
import { useTranslation } from '../i18n/TranslationProvider';

type HealthState = 'idle' | 'available' | 'unavailable';

export default function FoundationHome(): ReactNode {
  const { translate } = useTranslation();
  const [healthState, setHealthState] = useState<HealthState>('idle');

  async function checkApiHealth(): Promise<void> {
    const isAvailable = await checkHealth(getApiBaseUrl()).catch(() => false);
    setHealthState(isAvailable ? 'available' : 'unavailable');
  }

  return (
    <FoundationShell>
      <Text>{translate('status')}</Text>
      <View accessibilityLabel={translate('diagnostics')} style={{ gap: 8 }}>
        <Text accessibilityRole="header">{translate('diagnostics')}</Text>
        <Text>{translate('diagnosticsDescription')}</Text>
        <Pressable accessibilityRole="button" onPress={checkApiHealth}>
          <Text>{translate('checkHealth')}</Text>
        </Pressable>
        {healthState === 'available' ? (
          <Text>{translate('healthReady')}</Text>
        ) : null}
        {healthState === 'unavailable' ? (
          <Text>{translate('healthUnavailable')}</Text>
        ) : null}
      </View>
    </FoundationShell>
  );
}
