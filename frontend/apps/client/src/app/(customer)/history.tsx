import type { ReactNode } from 'react';
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
import { useTranslation } from '../../i18n/TranslationProvider';

export default function CustomerHistory(): ReactNode {
  const { apiClient, token } = useSession();
  const { locale, translate } = useTranslation();
  const queryClient = useQueryClient();
  const deleteGarment = useMutation({
    mutationFn: async (garmentId: string) => {
      const result = await deleteGarmentApiV1GarmentsGarmentIdDelete({
        client: apiClient,
        path: { garment_id: garmentId },
      });
      if (!result.data) throw result.error;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['customer-history'] });
      await queryClient.invalidateQueries({ queryKey: ['scan-history'] });
    },
  });
  const confirmDeletion = (garmentId: string): void => {
    Alert.alert(
      translate('deleteGarmentConfirmTitle'),
      translate('deleteGarmentConfirmDescription'),
      [
        { style: 'cancel', text: translate('cameraCancel') },
        {
          style: 'destructive',
          text: translate('deleteGarmentConfirmAction'),
          onPress: () => deleteGarment.mutate(garmentId),
        },
      ],
    );
  };
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
                  color={colors.primary}
                  name="chevron-right"
                  size={20}
                />
              </Pressable>
              <Pressable
                accessibilityLabel={translate('deleteGarment')}
                accessibilityRole="button"
                disabled={deleteGarment.isPending}
                onPress={() => confirmDeletion(garment.id)}
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
