import type { ComponentProps, ReactNode } from 'react';
import {
  Alert,
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
  getGarmentApiV1GarmentsGarmentIdGet,
  deleteGarmentApiV1GarmentsGarmentIdDelete,
  scanHistoryApiV1ScansHistoryGet,
  type GarmentResponse,
  type ScanHistoryResponse,
} from '@fabricassist/api-client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { router, useLocalSearchParams } from 'expo-router';
import { useSession } from '../../../auth/session';
import { FoundationShell } from '../../../components/FoundationShell';
import { useTranslation } from '../../../i18n/TranslationProvider';

export default function GarmentHistory(): ReactNode {
  const { garmentId, decisionScanId } = useLocalSearchParams<{
    garmentId: string;
    decisionScanId?: string;
  }>();
  const { apiClient, token } = useSession();
  const { locale, translate } = useTranslation();
  const queryClient = useQueryClient();
  const deleteGarment = useMutation({
    mutationFn: async () => {
      const result = await deleteGarmentApiV1GarmentsGarmentIdDelete({
        client: apiClient,
        path: { garment_id: garmentId },
      });
      if (!result.data) throw result.error;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['customer-history'] });
      await queryClient.invalidateQueries({ queryKey: ['scan-history'] });
      router.replace('/history');
    },
  });
  const confirmDeletion = (): void => {
    Alert.alert(
      translate('deleteGarmentConfirmTitle'),
      translate('deleteGarmentConfirmDescription'),
      [
        { style: 'cancel', text: translate('cameraCancel') },
        {
          style: 'destructive',
          text: translate('deleteGarmentConfirmAction'),
          onPress: () => deleteGarment.mutate(),
        },
      ],
    );
  };
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
  const { data: scans, isError: scansError } = useQuery<ScanHistoryResponse[]>({
    queryKey: ['scan-history', garmentId],
    enabled: Boolean(garmentId && token),
    queryFn: async () => {
      const result = await scanHistoryApiV1ScansHistoryGet({
        client: apiClient,
      });
      if (!result.data) throw result.error;
      return result.data;
    },
  });
  const garmentScans = scans?.filter((scan) => scan.garment_id === garmentId);

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
            <View style={styles.analyses}>
              <Text style={styles.sectionTitle}>
                {translate('previousAnalyses')}
              </Text>
              {scansError ? (
                <Text>{translate('scanHistoryLoadFailed')}</Text>
              ) : null}
              {!scansError && garmentScans?.length === 0 ? (
                <Text>{translate('previousAnalysesEmpty')}</Text>
              ) : null}
              {garmentScans?.map((scan) => (
                <Pressable
                  accessibilityLabel={translate('viewPreviousResult')}
                  accessibilityRole="button"
                  accessibilityState={{ disabled: !scan.result_available }}
                  disabled={!scan.result_available}
                  key={scan.scan_id}
                  onPress={() =>
                    router.push({
                      pathname: '/result',
                      params: { scanId: scan.scan_id },
                    })
                  }
                  style={({ pressed }) => [
                    styles.analysis,
                    !scan.result_available && styles.analysisDisabled,
                    pressed && scan.result_available && styles.analysisPressed,
                  ]}
                >
                  <View>
                    <Text style={styles.analysisTitle}>
                      {translate('previousAnalysis')}
                    </Text>
                    <Text style={styles.analysisDate}>
                      {formatTimestamp(
                        scan.created_at,
                        locale,
                        translate('notAvailable'),
                      )}
                    </Text>
                  </View>
                  <Feather
                    color={colors.primary}
                    name="chevron-right"
                    size={20}
                  />
                </Pressable>
              ))}
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
            <Pressable
              accessibilityLabel={translate('deleteGarment')}
              accessibilityRole="button"
              disabled={deleteGarment.isPending}
              onPress={confirmDeletion}
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
  events: { gap: spacing.small, marginTop: spacing.small },
  sectionTitle: { color: colors.text, fontSize: 17, fontWeight: '700' },
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
