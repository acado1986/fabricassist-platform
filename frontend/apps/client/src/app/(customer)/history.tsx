import { useEffect, useState, type ReactNode } from 'react';
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
import { useMutation } from '@tanstack/react-query';
import { useQuery as useApolloQuery } from '@apollo/client';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
import {
  GarmentHistoryDocument,
  imagePreviewApiV1ScansScanIdImagesImageIdPreviewGet,
  type FabricAssistApiClient,
} from '@fabricassist/api-client';
import { useSession } from '../../auth/session';
import { FoundationShell } from '../../components/FoundationShell';
import { GarmentDeletionConfirmation } from '../../components/GarmentDeletionConfirmation';
import { useTranslation } from '../../i18n/TranslationProvider';

export default function CustomerHistory(): ReactNode {
  const { apiClient, restWrites, token } = useSession();
  const { locale, translate } = useTranslation();
  const [deletionCandidate, setDeletionCandidate] = useState<string>();
  const deleteGarment = useMutation({
    mutationFn: async (garmentId: string) => {
      const result = await restWrites.deleteGarment({
        path: { garment_id: garmentId },
      });
      if (!result.data) throw new Error('GARMENT_DELETE_FAILED');
    },
    onSuccess: () => {
      setDeletionCandidate(undefined);
    },
  });
  const { data, error, loading } = useApolloQuery(GarmentHistoryDocument, {
    skip: !token,
    variables: { first: 20, after: null },
    fetchPolicy: 'cache-and-network',
  });
  const garments = data?.garmentHistory.items;
  return (
    <FoundationShell
      title={translate('customerHistoryTitle')}
      description={translate('customerHistoryDescription')}
    >
      <ScrollView contentContainerStyle={styles.content}>
        {loading ? <Text>{translate('resultLoading')}</Text> : null}
        {error ? <Text>{translate('customerHistoryLoadFailed')}</Text> : null}
        {!loading && !error && garments?.length === 0 ? (
          <Text>{translate('customerHistoryEmpty')}</Text>
        ) : null}
        {garments?.map((garment) => {
          const identifier = garment.identifiers[0] ?? garment.id;
          return (
            <View key={garment.id} style={styles.garment}>
              <Pressable
                accessibilityLabel={translate('viewGarmentHistory')}
                accessibilityRole="button"
                onPress={() => router.push(`/garments/${garment.id}`)}
                style={({ pressed }) => [
                  styles.garmentDetails,
                  pressed && styles.pressed,
                ]}
              >
                <GarmentThumbnail
                  apiClient={apiClient}
                  fallbackUrl={garment.thumbnailUrl}
                  imageId={garment.thumbnailImageId}
                  label={translate('garmentThumbnail')}
                  scanId={garment.thumbnailScanId}
                />
                <View style={styles.garmentCopy}>
                  <Text numberOfLines={1} style={styles.identifier}>
                    {identifier}
                  </Text>
                  <Text style={styles.detail}>
                    {translate('lastAnalysis')}:{' '}
                    {formatTimestamp(
                      garment.lastAnalysisAt,
                      locale,
                      translate('notAvailable'),
                    )}
                  </Text>
                  <Text style={styles.detail}>
                    {translate('analysedBefore')}:{' '}
                    {garment.analysedBefore
                      ? translate('yes')
                      : translate('no')}{' '}
                    · {translate('cleanedBefore')}:{' '}
                    {garment.cleanedBefore ? translate('yes') : translate('no')}
                  </Text>
                </View>
                <Feather
                  color={colors.primary}
                  name="chevron-right"
                  size={20}
                />
              </Pressable>
              <Pressable
                accessibilityLabel={translate('deleteGarment')}
                accessibilityRole="button"
                disabled={deleteGarment.isPending}
                onPress={() => setDeletionCandidate(garment.id)}
                style={({ pressed }) => [
                  styles.deleteButton,
                  pressed && styles.pressed,
                ]}
              >
                <Feather color={colors.danger} name="trash-2" size={20} />
              </Pressable>
            </View>
          );
        })}
        {deleteGarment.isError ? (
          <Text accessibilityLiveRegion="polite" style={styles.deleteError}>
            {translate('deleteGarmentRequestFailed')}
          </Text>
        ) : null}
      </ScrollView>
      <GarmentDeletionConfirmation
        isDeleting={deleteGarment.isPending}
        onCancel={() => setDeletionCandidate(undefined)}
        onConfirm={() => {
          if (deletionCandidate) deleteGarment.mutate(deletionCandidate);
        }}
        visible={Boolean(deletionCandidate)}
      />
    </FoundationShell>
  );
}

function GarmentThumbnail({
  apiClient,
  fallbackUrl,
  imageId,
  label,
  scanId,
}: {
  apiClient: FabricAssistApiClient;
  fallbackUrl?: string | null;
  imageId?: string | null;
  label: string;
  scanId?: string | null;
}): ReactNode {
  const [url, setUrl] = useState<string | undefined>(fallbackUrl ?? undefined);

  useEffect(() => {
    if (!scanId || !imageId) {
      setUrl(fallbackUrl ?? undefined);
      return;
    }
    let cancelled = false;
    void imagePreviewApiV1ScansScanIdImagesImageIdPreviewGet({
      client: apiClient,
      path: { scan_id: scanId, image_id: imageId },
    })
      .then((response) => {
        if (!cancelled) setUrl(response.data?.url ?? fallbackUrl ?? undefined);
      })
      .catch(() => {
        if (!cancelled) setUrl(fallbackUrl ?? undefined);
      });
    return () => {
      cancelled = true;
    };
  }, [apiClient, fallbackUrl, imageId, scanId]);

  return url ? (
    <Image
      accessibilityLabel={label}
      source={{ uri: url }}
      style={styles.thumbnail}
    />
  ) : (
    <View style={styles.thumbnailPlaceholder}>
      <Feather color={colors.muted} name="shopping-bag" size={24} />
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
  garment: {
    alignItems: 'center',
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: radii.medium,
    borderWidth: 1,
    flexDirection: 'row',
    padding: spacing.medium,
  },
  garmentDetails: {
    alignItems: 'center',
    flex: 1,
    flexDirection: 'row',
    gap: spacing.medium,
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
  deleteButton: { padding: spacing.small },
  deleteError: { color: colors.danger },
});
