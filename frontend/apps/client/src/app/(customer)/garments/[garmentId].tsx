import {
  useEffect,
  useState,
  type ComponentProps,
  type ReactNode,
} from 'react';
import {
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import Feather from '@expo/vector-icons/Feather';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
import {
  GarmentDetailDocument,
  imagePreviewApiV1ScansScanIdImagesImageIdPreviewGet,
} from '@fabricassist/api-client';
import { useQuery as useApolloQuery } from '@apollo/client';
import { useMutation } from '@tanstack/react-query';
import { router, useLocalSearchParams } from 'expo-router';
import { useSession } from '../../../auth/session';
import { FoundationShell } from '../../../components/FoundationShell';
import { GarmentDeletionConfirmation } from '../../../components/GarmentDeletionConfirmation';
import { useTranslation } from '../../../i18n/TranslationProvider';

export default function GarmentHistory(): ReactNode {
  const { garmentId, decisionScanId } = useLocalSearchParams<{
    garmentId: string;
    decisionScanId?: string;
  }>();
  const { apiClient, restWrites, token } = useSession();
  const { locale, translate } = useTranslation();
  const [deleteConfirmationOpen, setDeleteConfirmationOpen] = useState(false);
  const { data, error, fetchMore, refetch } = useApolloQuery(
    GarmentDetailDocument,
    {
      skip: !garmentId || !token,
      variables: {
        garmentId,
        first: 20,
        after: null,
        language: locale,
      },
      fetchPolicy: 'cache-and-network',
    },
  );
  const garment = data?.garmentDetail;
  const [thumbnailUrl, setThumbnailUrl] = useState<string>();
  useEffect(() => {
    if (!garment?.thumbnailScanId || !garment.thumbnailImageId) {
      setThumbnailUrl(undefined);
      return;
    }
    let cancelled = false;
    void imagePreviewApiV1ScansScanIdImagesImageIdPreviewGet({
      client: apiClient,
      path: {
        scan_id: garment.thumbnailScanId,
        image_id: garment.thumbnailImageId,
      },
    }).then((response) => {
      if (!cancelled) setThumbnailUrl(response.data?.url);
    });
    return () => {
      cancelled = true;
    };
  }, [apiClient, garment?.thumbnailImageId, garment?.thumbnailScanId]);
  const deleteGarment = useMutation({
    mutationFn: async () => {
      const result = await restWrites.deleteGarment({
        path: { garment_id: garmentId },
      });
      if (!result.data) throw new Error('GARMENT_DELETE_FAILED');
    },
    onSuccess: async () => {
      router.replace('/history');
    },
  });
  const garmentScans = garment?.analyses.items ?? [];

  return (
    <FoundationShell
      title={translate('garmentHistoryTitle')}
      description={translate('garmentHistoryDescription')}
    >
      <ScrollView contentContainerStyle={styles.content}>
        {error ? <Text>{translate('scanHistoryLoadFailed')}</Text> : null}
        {!garment && !error ? <Text>{translate('resultLoading')}</Text> : null}
        {garment ? (
          <>
            <View style={styles.hero}>
              {thumbnailUrl ? (
                <Image
                  accessibilityLabel={translate('garmentThumbnail')}
                  source={{ uri: thumbnailUrl }}
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
                    garment.lastAnalysisAt,
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
                  garment.analysedBefore ? translate('yes') : translate('no')
                }
              />
              <StatusCard
                icon="check-circle"
                label={translate('cleanedBefore')}
                value={
                  garment.cleanedBefore ? translate('yes') : translate('no')
                }
              />
            </View>
            <View style={styles.detailLinks}>
              <DetailLink icon="clock" title={translate('previousAnalyses')} onPress={() => router.push({ pathname: '/garments/analyses', params: { garmentId } })} />
              <DetailLink icon="clipboard" title={translate('serviceHistory')} onPress={() => router.push({ pathname: '/garments/service-history', params: { garmentId } })} />
              <DetailLink icon="check-circle" title={translate('finalResultAnalysis')} onPress={() => router.push({ pathname: '/garments/final-result', params: { garmentId } })} />
              <DetailLink icon="list" title={translate('garmentObservations')} onPress={() => router.push({ pathname: '/garments/observations', params: { garmentId } })} />
            </View>
            <Pressable
              accessibilityLabel={translate('deleteGarment')}
              accessibilityRole="button"
              disabled={deleteGarment.isPending}
              onPress={() => setDeleteConfirmationOpen(true)}
              style={({ pressed }) => [
                styles.deleteButton,
                pressed && styles.analysisPressed,
              ]}
            >
              <Feather color={colors.danger} name="trash-2" size={18} />
              <Text style={styles.deleteButtonText}>
                {translate('deleteGarment')}
              </Text>
            </Pressable>
            {deleteGarment.isError ? (
              <Text accessibilityLiveRegion="polite" style={styles.deleteError}>
                {translate('deleteGarmentRequestFailed')}
              </Text>
            ) : null}
            {decisionScanId ? (
              <Pressable
                accessibilityRole="button"
                onPress={() =>
                  router.push({
                    pathname: '/result',
                    params: { scanId: decisionScanId },
                  })
                }
                style={styles.returnButton}
              >
                <Text style={styles.returnButtonText}>
                  {translate('returnToIdentityDecision')}
                </Text>
              </Pressable>
            ) : null}
          </>
        ) : null}
      </ScrollView>
      <GarmentDeletionConfirmation
        isDeleting={deleteGarment.isPending}
        onCancel={() => setDeleteConfirmationOpen(false)}
        onConfirm={() => deleteGarment.mutate()}
        visible={deleteConfirmationOpen}
      />
    </FoundationShell>
  );
}

function DetailLink({ icon, title, onPress }: { icon: ComponentProps<typeof Feather>['name']; title: string; onPress: () => void }): ReactNode {
  return <Pressable accessibilityRole="button" onPress={onPress} style={({ pressed }) => [styles.detailLink, pressed && styles.analysisPressed]}><Feather color={colors.primary} name={icon} size={20} /><Text style={styles.detailLinkText}>{title}</Text><Feather color={colors.muted} name="chevron-right" size={18} /></Pressable>;
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

function formatKnownValue(value: Record<string, unknown>): string {
  return Object.entries(value)
    .filter(([, item]) => item !== null && item !== undefined && item !== '')
    .map(([key, item]) => `${key.replaceAll('_', ' ')}: ${String(item)}`)
    .join(' · ');
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
  analyses: { gap: spacing.small, marginTop: spacing.small },
  analysis: {
    alignItems: 'center',
    backgroundColor: colors.surfaceMuted,
    borderRadius: radii.medium,
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: spacing.medium,
  },
  analysisDisabled: { opacity: 0.55 },
  analysisPressed: { opacity: 0.72 },
  analysisTitle: { color: colors.text, fontSize: 14, fontWeight: '700' },
  analysisDate: { color: colors.muted, fontSize: 12, marginTop: 2 },
  loadMore: {
    alignSelf: 'flex-start',
    borderColor: colors.primary,
    borderRadius: radii.small,
    borderWidth: 1,
    paddingHorizontal: spacing.medium,
    paddingVertical: spacing.small,
  },
  loadMoreText: { color: colors.primary, fontWeight: '800' },
  detailLinks: { gap: spacing.small, marginTop: spacing.small },
  sectionTitle: { color: colors.text, fontSize: 17, fontWeight: '700' },
  detailLink: { alignItems: 'center', backgroundColor: colors.surfaceMuted, borderColor: colors.border, borderRadius: radii.medium, borderWidth: 1, flexDirection: 'row', gap: spacing.small, padding: spacing.medium },
  detailLinkText: { color: colors.text, flex: 1, fontSize: 15, fontWeight: '700' },
  serviceEditor: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radii.small,
    gap: spacing.small,
    padding: spacing.small,
  },
  kindButton: {
    borderColor: colors.border,
    borderRadius: radii.small,
    borderWidth: 1,
    paddingHorizontal: spacing.small,
    paddingVertical: spacing.xsmall,
  },
  kindButtonActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  serviceInput: {
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: radii.small,
    borderWidth: 1,
    minHeight: 42,
    paddingHorizontal: spacing.small,
  },
  addServiceButton: {
    alignSelf: 'flex-start',
    backgroundColor: colors.primary,
    borderRadius: radii.small,
    paddingHorizontal: spacing.medium,
    paddingVertical: spacing.small,
  },
  finalFact: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radii.small,
    gap: 2,
    padding: spacing.small,
  },
  observation: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radii.small,
    gap: 2,
    padding: spacing.small,
  },
  observationTitle: { color: colors.text, fontWeight: '700' },
  returnButton: {
    alignSelf: 'flex-start',
    backgroundColor: colors.primary,
    borderRadius: radii.small,
    padding: spacing.medium,
  },
  returnButtonText: { color: colors.background, fontWeight: '800' },
  deleteButton: {
    alignItems: 'center',
    borderColor: colors.danger,
    borderRadius: radii.small,
    borderWidth: 1,
    flexDirection: 'row',
    gap: spacing.small,
    justifyContent: 'center',
    padding: spacing.medium,
  },
  deleteButtonText: { color: colors.danger, fontWeight: '800' },
  deleteError: { color: colors.danger },
});
