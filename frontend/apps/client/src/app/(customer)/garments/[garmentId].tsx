import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { spacing } from '@fabricassist/design-tokens';
import { useLocalSearchParams } from 'expo-router';
import { useSession } from '../../../auth/session';
import { FoundationShell } from '../../../components/FoundationShell';
import { getApiBaseUrl } from '../../../config/environment';
import { useTranslation } from '../../../i18n/TranslationProvider';

type ServiceEvent = { id: string; kind: string; note: string | null };
type Garment = {
  analysed_before: boolean;
  cleaned_before: boolean;
  identifiers: string[];
  last_analysis_at: string | null;
  service_events: ServiceEvent[];
};

export default function GarmentHistory(): ReactNode {
  const { garmentId } = useLocalSearchParams<{ garmentId: string }>();
  const { token } = useSession();
  const { translate } = useTranslation();
  const [garment, setGarment] = useState<Garment>();

  useEffect(() => {
    if (!garmentId || !token) return;
    void fetch(`${getApiBaseUrl()}/api/v1/garments/${garmentId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) =>
        response.ok ? (response.json() as Promise<Garment>) : Promise.reject(),
      )
      .then(setGarment)
      .catch(() => setGarment(undefined));
  }, [garmentId, token]);

  return (
    <FoundationShell
      title={translate('garmentHistoryTitle')}
      description={translate('garmentHistoryDescription')}
    >
      <ScrollView contentContainerStyle={styles.content}>
        {!garment ? <Text>{translate('resultLoading')}</Text> : null}
        {garment ? (
          <>
            <Text>
              {translate('analysedBefore')}:{' '}
              {garment.analysed_before ? translate('yes') : translate('no')}
            </Text>
            <Text>
              {translate('cleanedBefore')}:{' '}
              {garment.cleaned_before ? translate('yes') : translate('no')}
            </Text>
            <Text>
              {translate('garmentIdentifiers')}:{' '}
              {garment.identifiers.join(', ')}
            </Text>
            <Text>
              {translate('lastAnalysis')}:{' '}
              {garment.last_analysis_at ?? translate('notAvailable')}
            </Text>
            <View style={styles.events}>
              <Text>{translate('serviceHistory')}</Text>
              {garment.service_events.length === 0 ? (
                <Text>{translate('noServiceEvents')}</Text>
              ) : null}
              {garment.service_events.map((event) => (
                <Text key={event.id}>
                  • {event.kind}
                  {event.note ? `: ${event.note}` : ''}
                </Text>
              ))}
            </View>
          </>
        ) : null}
      </ScrollView>
    </FoundationShell>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing.medium },
  events: { gap: spacing.small },
});
