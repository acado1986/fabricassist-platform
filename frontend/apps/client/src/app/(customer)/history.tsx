import type { ReactNode } from 'react';
import {
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import Feather from '@expo/vector-icons/Feather';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
import {
  listGarmentsApiV1GarmentsGet,
  type GarmentResponse,
} from '@fabricassist/api-client';
import { useSession } from '../../auth/session';
import { FoundationShell } from '../../components/FoundationShell';
import { useTranslation } from '../../i18n/TranslationProvider';

export default function CustomerHistory(): ReactNode {
  const { apiClient, token } = useSession();
  const { locale, translate } = useTranslation();
  const {
    data: garments,
    isError,
    isLoading,
  } = useQuery<GarmentResponse[]>({
    queryKey: ['customer-history'],
    enabled: Boolean(token),
    queryFn: async () => {
      const result = await listGarmentsApiV1GarmentsGet({ client: apiClient });
      if (!result.data) throw result.error;
      return result.data;
    },
  });
  return (
    <FoundationShell
      title={translate('customerHistoryTitle')}
      description={translate('customerHistoryDescription')}
    >
      <ScrollView contentContainerStyle={styles.content}>
        {isLoading ? <Text>{translate('resultLoading')}</Text> : null}
        {isError ? <Text>{translate('customerHistoryLoadFailed')}</Text> : null}
        {!isLoading && !isError && garments?.length === 0 ? (
          <Text>{translate('customerHistoryEmpty')}</Text>
        ) : null}
        {garments?.map((garment) => {
          const identifier = garment.identifiers?.[0] ?? garment.id;
          return (
            <Pressable
              accessibilityLabel={translate('viewGarmentHistory')}
              accessibilityRole="button"
              key={garment.id}
              onPress={() => router.push(`/garments/${garment.id}`)}
              style={({ pressed }) => [
                styles.garment,
                pressed && styles.pressed,
              ]}
            >
              {garment.thumbnail_url ? (
                <Image
                  accessibilityLabel={translate('garmentThumbnail')}
                  source={{ uri: garment.thumbnail_url }}
                  style={styles.thumbnail}
                />
              ) : (
                <View style={styles.thumbnailPlaceholder}>
                  <Feather color={colors.muted} name="shopping-bag" size={24} />
                </View>
              )}
              <View style={styles.garmentCopy}>
                <Text numberOfLines={1} style={styles.identifier}>
                  {identifier}
                </Text>
                <Text style={styles.detail}>
                  {translate('lastAnalysis')}:{' '}
                  {formatTimestamp(
                    garment.last_analysis_at,
                    locale,
                    translate('notAvailable'),
                  )}
                </Text>
                <Text style={styles.detail}>
                  {translate('analysedBefore')}:{' '}
                  {garment.analysed_before ? translate('yes') : translate('no')}{' '}
                  · {translate('cleanedBefore')}:{' '}
                  {garment.cleaned_before ? translate('yes') : translate('no')}
                </Text>
              </View>
              <Feather color={colors.primary} name="chevron-right" size={20} />
            </Pressable>
          );
        })}
      </ScrollView>
    </FoundationShell>
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
  garment: {
    alignItems: 'center',
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: radii.medium,
    borderWidth: 1,
    flexDirection: 'row',
    gap: spacing.medium,
    justifyContent: 'space-between',
    padding: spacing.medium,
  },
  garmentCopy: { flex: 1, gap: spacing.xsmall },
  thumbnail: { borderRadius: radii.small, height: 72, width: 72 },
  thumbnailPlaceholder: {
    alignItems: 'center',
    backgroundColor: colors.background,
    borderRadius: radii.small,
    height: 72,
    justifyContent: 'center',
    width: 72,
  },
  identifier: { color: colors.text, fontSize: 15, fontWeight: '700' },
  detail: { color: colors.muted, fontSize: 13, lineHeight: 18 },
  pressed: { opacity: 0.72 },
});
