import type { ComponentProps, ReactNode } from 'react';
import { Image, ScrollView, StyleSheet, Text, View } from 'react-native';
import Feather from '@expo/vector-icons/Feather';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
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
  const { locale, translate } = useTranslation();
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
            <View style={styles.hero}>
              {garment.thumbnail_url ? (
                <Image
                  accessibilityLabel={translate('garmentThumbnail')}
                  source={{ uri: garment.thumbnail_url }}
                  style={styles.heroImage}
                />
              ) : (
                <View style={styles.heroPlaceholder}>
                  <Feather color={colors.muted} name="shopping-bag" size={38} />
                </View>
              )}
              <View style={styles.heroCopy}>
                <Text style={styles.identifier}>
                  {(garment.identifiers ?? [garment.id]).join(', ')}
                </Text>
                <Text style={styles.lastAnalysis}>
                  {translate('lastAnalysis')}:{' '}
                  {formatTimestamp(
                    garment.last_analysis_at,
                    locale,
                    translate('notAvailable'),
                  )}
                </Text>
              </View>
            </View>
            <View style={styles.statuses}>
              <StatusCard
                icon="search"
                label={translate('analysedBefore')}
                value={
                  garment.analysed_before ? translate('yes') : translate('no')
                }
              />
              <StatusCard
                icon="check-circle"
                label={translate('cleanedBefore')}
                value={
                  garment.cleaned_before ? translate('yes') : translate('no')
                }
              />
            </View>
            <View style={styles.events}>
              <Text style={styles.sectionTitle}>
                {translate('serviceHistory')}
              </Text>
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

function StatusCard({
  icon,
  label,
  value,
}: {
  icon: ComponentProps<typeof Feather>['name'];
  label: string;
  value: string;
}): ReactNode {
  return (
    <View style={styles.statusCard}>
      <Feather color={colors.primary} name={icon} size={18} />
      <View>
        <Text style={styles.statusLabel}>{label}</Text>
        <Text style={styles.statusValue}>{value}</Text>
      </View>
    </View>
  );
}

function formatTimestamp(
  value: string | null | undefined,
  locale: 'en' | 'es',
  fallback: string,
): string {
  if (!value) return fallback;
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return fallback;
  return new Intl.DateTimeFormat(locale === 'es' ? 'es-ES' : 'en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(timestamp);
}

const styles = StyleSheet.create({
  content: { gap: spacing.medium },
  hero: {
    alignItems: 'center',
    backgroundColor: colors.surfaceMuted,
    borderRadius: radii.medium,
    flexDirection: 'row',
    gap: spacing.medium,
    padding: spacing.medium,
  },
  heroImage: { borderRadius: radii.small, height: 112, width: 112 },
  heroPlaceholder: {
    alignItems: 'center',
    backgroundColor: colors.background,
    borderRadius: radii.small,
    height: 112,
    justifyContent: 'center',
    width: 112,
  },
  heroCopy: { flex: 1, gap: spacing.small },
  identifier: { color: colors.text, fontSize: 15, fontWeight: '700' },
  lastAnalysis: { color: colors.muted, fontSize: 13, lineHeight: 19 },
  statuses: { flexDirection: 'row', gap: spacing.small },
  statusCard: {
    alignItems: 'center',
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: radii.medium,
    borderWidth: 1,
    flex: 1,
    flexDirection: 'row',
    gap: spacing.small,
    padding: spacing.medium,
  },
  statusLabel: { color: colors.muted, fontSize: 12 },
  statusValue: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
    marginTop: 2,
  },
  events: { gap: spacing.small, marginTop: spacing.small },
  sectionTitle: { color: colors.text, fontSize: 17, fontWeight: '700' },
});
