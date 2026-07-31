import { useState, type ReactNode } from 'react';
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
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
import {
  deleteGarmentApiV1GarmentsGarmentIdDelete,
  listGarmentsApiV1GarmentsGet,
  type GarmentResponse,
} from '@fabricassist/api-client';
import { useSession } from '../../auth/session';
import { FoundationShell } from '../../components/FoundationShell';
import { GarmentDeletionConfirmation } from '../../components/GarmentDeletionConfirmation';
import { useTranslation } from '../../i18n/TranslationProvider';

export default function CustomerHistory(): ReactNode {
  const { apiClient, token } = useSession();
  const { locale, translate } = useTranslation();
  const [deletionCandidates, setDeletionCandidates] = useState<string[]>([]);
  const [isSelecting, setIsSelecting] = useState(false);
  const [selectedGarmentIds, setSelectedGarmentIds] = useState<string[]>([]);
  const queryClient = useQueryClient();
  const deleteGarment = useMutation({
    mutationFn: async (garmentIds: string[]) => {
      for (const garmentId of garmentIds) {
        const result = await deleteGarmentApiV1GarmentsGarmentIdDelete({
          client: apiClient,
          path: { garment_id: garmentId },
        });
        if (!result.data) throw result.error;
      }
    },
    onSuccess: async () => {
      setDeletionCandidates([]);
      setSelectedGarmentIds([]);
      setIsSelecting(false);
      await queryClient.invalidateQueries({ queryKey: ['customer-history'] });
      await queryClient.invalidateQueries({ queryKey: ['scan-history'] });
    },
  });
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
        {!isLoading && !isError && garments?.length ? (
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
        {isLoading ? <Text>{translate('resultLoading')}</Text> : null}
        {isError ? <Text>{translate('customerHistoryLoadFailed')}</Text> : null}
        {!isLoading && !isError && garments?.length === 0 ? (
          <Text>{translate('customerHistoryEmpty')}</Text>
        ) : null}
        {garments?.map((garment) => {
          const identifier = garment.identifiers?.[0] ?? garment.id;
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
                {garment.thumbnail_url ? (
                  <Image
                    accessibilityLabel={translate('garmentThumbnail')}
                    source={{ uri: garment.thumbnail_url }}
                    style={styles.thumbnail}
                  />
                ) : (
                  <View style={styles.thumbnailPlaceholder}>
                    <Feather
                      color={colors.muted}
                      name="shopping-bag"
                      size={24}
                    />
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
                    {garment.analysed_before
                      ? translate('yes')
                      : translate('no')}{' '}
                    · {translate('cleanedBefore')}:{' '}
                    {garment.cleaned_before
                      ? translate('yes')
                      : translate('no')}
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
