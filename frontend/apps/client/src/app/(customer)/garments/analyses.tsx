import { type ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useQuery } from '@apollo/client';
import { router, useLocalSearchParams } from 'expo-router';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
import { GarmentDetailDocument } from '@fabricassist/api-client';
import { useSession } from '../../../auth/session';
import { FoundationShell } from '../../../components/FoundationShell';
import { useTranslation } from '../../../i18n/TranslationProvider';

export default function AnalysesPage(): ReactNode {
  const { garmentId } = useLocalSearchParams<{ garmentId: string }>();
  const { token } = useSession();
  const { locale, translate } = useTranslation();
  const { data, fetchMore } = useQuery(GarmentDetailDocument, {
    skip: !token,
    variables: { garmentId, first: 20, after: null, language: locale },
  });
  const analyses = data?.garmentDetail?.analyses;
  return (
    <FoundationShell
      title={translate('previousAnalyses')}
      description={translate('garmentHistoryDescription')}
    >
      <ScrollView contentContainerStyle={styles.content}>
        <Pressable onPress={() => router.back()}>
          <Text style={styles.back}>‹ {translate('garmentHistoryTitle')}</Text>
        </Pressable>
        {!analyses?.items.length ? (
          <Text>{translate('previousAnalysesEmpty')}</Text>
        ) : null}
        {analyses?.items.map((scan) => (
          <Pressable
            key={scan.scanId}
            disabled={!scan.resultAvailable}
            onPress={() =>
              router.push({
                pathname: '/result',
                params: { scanId: scan.scanId },
              })
            }
            style={[styles.card, !scan.resultAvailable && styles.disabled]}
          >
            <View>
              <Text style={styles.title}>{translate('previousAnalysis')}</Text>
              <Text style={styles.date}>
                {formatDate(scan.createdAt, locale, translate('notAvailable'))}
              </Text>
            </View>
            <Text style={styles.chevron}>›</Text>
          </Pressable>
        ))}
        {analyses?.pageInfo.nextCursor ? (
          <Pressable
            onPress={() =>
              void fetchMore({
                variables: { after: analyses.pageInfo.nextCursor },
              })
            }
            style={styles.more}
          >
            <Text style={styles.moreText}>{translate('loadMoreAnalyses')}</Text>
          </Pressable>
        ) : null}
      </ScrollView>
    </FoundationShell>
  );
}
function formatDate(
  value: string,
  locale: 'en' | 'es',
  fallback: string,
): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? fallback
    : new Intl.DateTimeFormat(locale === 'es' ? 'es-ES' : 'en-US', {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(date);
}
const styles = StyleSheet.create({
  content: { gap: spacing.medium },
  back: { color: colors.primary, fontWeight: '700' },
  card: {
    alignItems: 'center',
    backgroundColor: colors.surfaceMuted,
    borderRadius: radii.medium,
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: spacing.medium,
  },
  disabled: { opacity: 0.55 },
  title: { color: colors.text, fontWeight: '800' },
  date: { color: colors.muted, fontSize: 12, marginTop: 3 },
  chevron: { color: colors.primary, fontSize: 28 },
  more: {
    alignSelf: 'flex-start',
    borderColor: colors.primary,
    borderRadius: radii.small,
    borderWidth: 1,
    padding: spacing.small,
  },
  moreText: { color: colors.primary, fontWeight: '800' },
});
