import {
  useCallback,
  useEffect,
  useRef,
  useState,
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
import { router, useFocusEffect } from 'expo-router';
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
  const [deletionCandidates, setDeletionCandidates] = useState<string[]>([]);
  const [isSelecting, setIsSelecting] = useState(false);
  const [selectedGarmentIds, setSelectedGarmentIds] = useState<string[]>([]);
  const deleteGarment = useMutation({
    mutationFn: async (garmentIds: string[]) => {
      for (const garmentId of garmentIds) {
        const result = await restWrites.deleteGarment({
          path: { garment_id: garmentId },
        });
        if (!result.data) throw new Error('GARMENT_DELETE_FAILED');
      }
    },
    onSuccess: () => {
      setDeletionCandidates([]);
      setSelectedGarmentIds([]);
      setIsSelecting(false);
    },
  });
  const {
    data,
    error,
    loading,
    refetch: refreshHistory,
  } = useApolloQuery(GarmentHistoryDocument, {
    skip: !token,
    variables: { first: 20, after: null },
    // A garment can be created or deleted while this route is unmounted. The
    // history screen therefore always starts from the canonical server read
    // instead of briefly rendering a stale memory-cache snapshot.
    fetchPolicy: 'network-only',
  });
  const hasFocused = useRef(false);
  useFocusEffect(
    useCallback(() => {
      if (hasFocused.current && token) {
        void refreshHistory({ first: 20, after: null });
      }
      hasFocused.current = true;
    }, [refreshHistory, token]),
  );
  const garments = data?.garmentHistory.items;
  return (
    <FoundationShell
      title={translate('customerHistoryTitle')}
      description={translate('customerHistoryDescription')}
    >
      <ScrollView contentContainerStyle={styles.content}>
        {loading ? <Text>{translate('resultLoading')}</Text> : null}
        {error ? <Text>{translate('customerHistoryLoadFailed')}</Text> : null}
        {!loading && !error && garments?.length ? (
          <View style={styles.selectionToolbar}>
            <Pressable
              accessibilityLabel={translate(
                isSelecting ? 'finishGarmentSelection' : 'selectGarments',
              )}
              accessibilityRole="button"
              disabled={deleteGarment.isPending}
              onPress={() => {
                setIsSelecting((current) => !current);
                setSelectedGarmentIds([]);
              }}
              style={({ pressed }) => [
                styles.selectionButton,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.selectionButtonText}>
                {translate(
                  isSelecting ? 'finishGarmentSelection' : 'selectGarments',
                )}
              </Text>
            </Pressable>
            {isSelecting ? (
              <>
                <Text
                  accessibilityLiveRegion="polite"
                  style={styles.selectionCount}
                >
                  {translate('selectedGarmentsCount').replace(
                    '{count}',
                    String(selectedGarmentIds.length),
                  )}
                </Text>
                <Pressable
                  accessibilityLabel={translate('deleteSelectedGarments')}
                  accessibilityRole="button"
                  disabled={
                    deleteGarment.isPending || selectedGarmentIds.length === 0
                  }
                  onPress={() => setDeletionCandidates(selectedGarmentIds)}
                  style={({ pressed }) => [
                    styles.deleteSelectedButton,
                    pressed && styles.pressed,
                    selectedGarmentIds.length === 0 && styles.disabled,
                  ]}
                >
                  <Feather color={colors.background} name="trash-2" size={18} />
                </Pressable>
              </>
            ) : null}
          </View>
        ) : null}
        {!loading && !error && garments?.length === 0 ? (
          <Text>{translate('customerHistoryEmpty')}</Text>
        ) : null}
        {garments?.map((garment) => {
          const identifier = garment.identifiers[0] ?? garment.id;
          const isSelected = selectedGarmentIds.includes(garment.id);
          return (
            <View key={garment.id} style={styles.garment}>
              <Pressable
                accessibilityLabel={translate(
                  isSelecting
                    ? 'selectGarmentForDeletion'
                    : 'viewGarmentHistory',
                )}
                accessibilityRole="button"
                accessibilityState={{ selected: isSelected }}
                onPress={() => {
                  if (isSelecting) {
                    setSelectedGarmentIds((current) =>
                      current.includes(garment.id)
                        ? current.filter((id) => id !== garment.id)
                        : [...current, garment.id],
                    );
                    return;
                  }
                  router.push(`/garments/${garment.id}`);
                }}
                style={({ pressed }) => [
                  styles.garmentDetails,
                  isSelected && styles.garmentSelected,
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
                  color={isSelected ? colors.primary : colors.muted}
                  name={
                    isSelecting
                      ? isSelected
                        ? 'check-square'
                        : 'square'
                      : 'chevron-right'
                  }
                  size={20}
                />
              </Pressable>
              {!isSelecting ? (
                <Pressable
                  accessibilityLabel={translate('deleteGarment')}
                  accessibilityRole="button"
                  disabled={deleteGarment.isPending}
                  onPress={() => setDeletionCandidates([garment.id])}
                  style={({ pressed }) => [
                    styles.deleteButton,
                    pressed && styles.pressed,
                  ]}
                >
                  <Feather color={colors.danger} name="trash-2" size={20} />
                </Pressable>
              ) : null}
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
        garmentCount={deletionCandidates.length}
        isDeleting={deleteGarment.isPending}
        onCancel={() => setDeletionCandidates([])}
        onConfirm={() => {
          if (deletionCandidates.length > 0) {
            deleteGarment.mutate(deletionCandidates);
          }
        }}
        visible={deletionCandidates.length > 0}
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
  selectionToolbar: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.small,
  },
  selectionButton: {
    borderColor: colors.primary,
    borderRadius: radii.small,
    borderWidth: 1,
    paddingHorizontal: spacing.medium,
    paddingVertical: spacing.small,
  },
  selectionButtonText: { color: colors.primary, fontWeight: '700' },
  selectionCount: { color: colors.muted, flex: 1 },
  deleteSelectedButton: {
    alignItems: 'center',
    backgroundColor: colors.danger,
    borderRadius: radii.small,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  garmentDetails: {
    alignItems: 'center',
    flex: 1,
    flexDirection: 'row',
    gap: spacing.medium,
  },
  garmentSelected: {
    backgroundColor: colors.background,
    borderRadius: radii.small,
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
  disabled: { opacity: 0.55 },
});
