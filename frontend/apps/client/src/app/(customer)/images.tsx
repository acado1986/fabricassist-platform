import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import Feather from '@expo/vector-icons/Feather';
import { useQuery as useApolloQuery } from '@apollo/client';
import { useLocalSearchParams } from 'expo-router';
import {
  ActivityIndicator,
  Image,
  Linking,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
import {
  ScanImageMetadataDocument,
  imagePreviewApiV1ScansScanIdImagesImageIdPreviewGet,
  type ScanImageMetadataQuery,
} from '@fabricassist/api-client';
import type { TranslationKey } from '@fabricassist/translations';
import { useSession } from '../../auth/session';
import { FoundationShell } from '../../components/FoundationShell';
import { useTranslation } from '../../i18n/TranslationProvider';

type GalleryImage = NonNullable<
  ScanImageMetadataQuery['imageMetadata']
>[number] & { url: string };

const imageRoleKeys = {
  garment_overview: 'garmentOverviewRole',
  care_label: 'careLabelRole',
  composition_label: 'compositionLabelRole',
  barcode_brand_label: 'barcodeBrandLabelRole',
  stain_closeup: 'stainCloseupRole',
  damage_closeup: 'damageCloseupRole',
  construction_detail: 'constructionDetailRole',
  other: 'otherRole',
} as const satisfies Record<string, TranslationKey>;
const viewpointKeys: Record<string, TranslationKey> = {
  front: 'viewpointFront',
  back: 'viewpointBack',
  side: 'viewpointSide',
  detail: 'viewpointDetail',
  unknown: 'viewpointUnknown',
};
const labelScopeKeys: Record<string, TranslationKey> = {
  care: 'labelScopeCare',
  composition: 'labelScopeComposition',
  combined: 'labelScopeCombined',
  unknown: 'labelScopeUnknown',
};

function roleTranslationKey(role: string): TranslationKey {
  return role in imageRoleKeys
    ? imageRoleKeys[role as keyof typeof imageRoleKeys]
    : imageRoleKeys.other;
}

function viewpointTranslationKey(viewpoint: string): TranslationKey {
  return viewpointKeys[viewpoint] ?? 'viewpointUnknown';
}

function labelScopeTranslationKey(scope: string): TranslationKey {
  return labelScopeKeys[scope] ?? 'labelScopeUnknown';
}

export default function UploadedImages(): ReactNode {
  const { scanId } = useLocalSearchParams<{ scanId: string }>();
  const { apiClient, token } = useSession();
  const { translate } = useTranslation();
  const { data, error } = useApolloQuery(ScanImageMetadataDocument, {
    skip: !scanId || !token,
    variables: { scanId },
    fetchPolicy: 'cache-and-network',
  });
  const [images, setImages] = useState<GalleryImage[]>([]);
  const [selected, setSelected] = useState<GalleryImage>();
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!scanId || !token || !data) return;
    let cancelled = false;
    const load = async (): Promise<void> => {
      setLoading(true);
      setFailed(false);
      try {
        const previews = await Promise.all(
          data.imageMetadata.map(async (image) => {
            const preview =
              await imagePreviewApiV1ScansScanIdImagesImageIdPreviewGet({
                client: apiClient,
                path: { scan_id: scanId, image_id: image.id },
              });
            if (!preview.data) throw preview.error;
            return { ...image, url: preview.data.url };
          }),
        );
        if (!cancelled) setImages(previews);
      } catch {
        if (!cancelled) setFailed(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [apiClient, data, scanId, token]);

  const download = async (image: GalleryImage): Promise<void> => {
    if (!scanId) return;
    const response = await imagePreviewApiV1ScansScanIdImagesImageIdPreviewGet({
      client: apiClient,
      path: { scan_id: scanId, image_id: image.id },
      query: { download: true },
    });
    if (response.data) await Linking.openURL(response.data.url);
  };

  return (
    <FoundationShell
      title={translate('uploadedImagesTitle')}
      description={translate('uploadedImagesDescription')}
    >
      <ScrollView contentContainerStyle={styles.content}>
        {loading ? (
          <ActivityIndicator color={colors.primary} size="large" />
        ) : null}
        {error || failed ? (
          <Text>{translate('uploadedImagesLoadFailed')}</Text>
        ) : null}
        {!loading && !failed && images.length === 0 ? (
          <Text>{translate('uploadedImagesEmpty')}</Text>
        ) : null}
        <View style={styles.grid}>
          {images.map((image, index) => (
            <Pressable
              accessibilityLabel={translate('openUploadedImage').replace(
                '{number}',
                String(index + 1),
              )}
              accessibilityRole="button"
              key={image.id}
              onPress={() => setSelected(image)}
              style={({ pressed }) => [styles.card, pressed && styles.pressed]}
            >
              <Image source={{ uri: image.url }} style={styles.thumbnail} />
              <View style={styles.cardFooter}>
                <View style={styles.cardMetadata}>
                  <Text numberOfLines={1} style={styles.role}>
                    {translate(roleTranslationKey(image.role))}
                  </Text>
                  {image.viewpoint && image.viewpoint !== 'unknown' ? (
                    <Text style={styles.metadata}>
                      {translate(viewpointTranslationKey(image.viewpoint))}
                    </Text>
                  ) : null}
                  {image.labelScope && image.labelScope !== 'unknown' ? (
                    <Text style={styles.metadata}>
                      {translate(labelScopeTranslationKey(image.labelScope))}
                    </Text>
                  ) : null}
                  {image.qualityState === 'borderline' ? (
                    <Text style={styles.metadata}>
                      {translate('imageQualityBorderline')}
                    </Text>
                  ) : null}
                  {image.qualityState === 'unusable' ? (
                    <Text style={styles.metadata}>
                      {translate('imageQualityUnusable')}
                    </Text>
                  ) : null}
                </View>
                <Feather color={colors.primary} name="maximize-2" size={17} />
              </View>
            </Pressable>
          ))}
        </View>
      </ScrollView>
      <Modal
        animationType="fade"
        onRequestClose={() => setSelected(undefined)}
        transparent
        visible={Boolean(selected)}
      >
        <View style={styles.modal}>
          <Pressable
            accessibilityLabel={translate('closeImageZoom')}
            accessibilityRole="button"
            onPress={() => setSelected(undefined)}
            style={styles.close}
          >
            <Feather color={colors.background} name="x" size={26} />
          </Pressable>
          {selected ? (
            <ScrollView
              contentContainerStyle={styles.zoomContent}
              maximumZoomScale={4}
              minimumZoomScale={1}
              showsHorizontalScrollIndicator={false}
              showsVerticalScrollIndicator={false}
              style={styles.zoomScroll}
            >
              <Image
                accessibilityLabel={translate('zoomedUploadedImage')}
                resizeMode="contain"
                source={{ uri: selected.url }}
                style={styles.zoomedImage}
              />
            </ScrollView>
          ) : null}
          {selected ? (
            <Pressable
              accessibilityLabel={translate('downloadUploadedImage')}
              accessibilityRole="button"
              onPress={() => void download(selected)}
              style={styles.download}
            >
              <Feather color={colors.background} name="download" size={20} />
              <Text style={styles.downloadText}>
                {translate('downloadUploadedImage')}
              </Text>
            </Pressable>
          ) : null}
        </View>
      </Modal>
    </FoundationShell>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing.medium },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.medium },
  card: {
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderRadius: radii.medium,
    borderWidth: 1,
    overflow: 'hidden',
    width: '47%',
  },
  thumbnail: { aspectRatio: 1, width: '100%' },
  cardFooter: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.xsmall,
    justifyContent: 'space-between',
    padding: spacing.small,
  },
  cardMetadata: { flex: 1, gap: spacing.xsmall },
  role: { color: colors.text, flex: 1, fontSize: 13, fontWeight: '700' },
  metadata: { color: colors.muted, fontSize: 11 },
  pressed: { opacity: 0.72 },
  modal: { backgroundColor: 'rgba(0, 0, 0, 0.94)', flex: 1 },
  close: {
    padding: spacing.medium,
    position: 'absolute',
    right: 0,
    top: 34,
    zIndex: 2,
  },
  zoomScroll: { flex: 1 },
  zoomContent: {
    alignItems: 'center',
    flexGrow: 1,
    justifyContent: 'center',
    padding: spacing.large,
  },
  zoomedImage: { height: '100%', width: '100%' },
  download: {
    alignItems: 'center',
    alignSelf: 'center',
    backgroundColor: colors.primary,
    borderRadius: radii.pill,
    bottom: spacing.xlarge,
    flexDirection: 'row',
    gap: spacing.small,
    paddingHorizontal: spacing.large,
    paddingVertical: spacing.medium,
    position: 'absolute',
  },
  downloadText: { color: colors.background, fontWeight: '800' },
});
