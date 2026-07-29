import type { ReactNode } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { spacing } from '@fabricassist/design-tokens';
import {
  getGarmentApiV1GarmentsGarmentIdGet,
  type GarmentResponse,
} from '@fabricassist/api-client';
import { useQuery } from '@tanstack/react-query';
import { useLocalSearchParams } from 'expo-router';
import { useSession } from '../../../auth/session';
import { FoundationShell } from '../../../components/FoundationShell';
import { useTranslation } from '../../../i18n/TranslationProvider';

export default function GarmentHistory(): ReactNode {
  const { garmentId } = useLocalSearchParams<{ garmentId: string }>();
  const { apiClient, token } = useSession();
  const { translate } = useTranslation();
  const { data: garment } = useQuery<GarmentResponse>({
    queryKey: ['garment', garmentId],
    enabled: Boolean(garmentId && token),
    queryFn: async () => {
      const result = await getGarmentApiV1GarmentsGarmentIdGet({
        client: apiClient,
        path: { garment_id: garmentId },
      });
      if (!result.data) throw result.error;
      return result.data;
    },
  });

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
              {(garment.identifiers ?? []).join(', ')}
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
