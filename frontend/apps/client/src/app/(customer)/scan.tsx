import type { ReactNode } from 'react';
import { useCallback, useState } from 'react';
import Feather from '@expo/vector-icons/Feather';
import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import {
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
import {
  addImageApiV1ScansScanIdImagesPost,
  completeUploadApiV1ScansScanIdUploadsCompletePost,
  createScanApiV1ScansPost,
  productLookupApiV1ScansScanIdProductLookupPost,
  requestAnalysisApiV1ScansScanIdAnalysePost,
} from '@fabricassist/api-client';
import { useSession } from '../../auth/session';
import { FoundationShell } from '../../components/FoundationShell';
import { useTranslation } from '../../i18n/TranslationProvider';
import { uploadBinaryFile } from '../../platform/BinaryUpload';
import { CameraCapture } from '../../platform/CameraCapture';

type Role =
  | 'garment_overview'
  | 'care_label'
  | 'composition_label'
  | 'barcode_brand_label'
  | 'stain_closeup'
  | 'damage_closeup'
  | 'construction_detail'
  | 'other';
type Selected = { role: Role; asset: ImagePicker.ImagePickerAsset };
const maximumImages = 8;
const roles: Role[] = [
  'garment_overview',
  'care_label',
  'composition_label',
  'barcode_brand_label',
  'stain_closeup',
  'damage_closeup',
  'construction_detail',
  'other',
];

export default function Scan(): ReactNode {
  const { apiClient, token } = useSession();
  const { locale, translate } = useTranslation();
  const [items, setItems] = useState<Selected[]>([]);
  const [role, setRole] = useState<Role>('garment_overview');
  const [busy, setBusy] = useState(false);
  const [cameraVisible, setCameraVisible] = useState(false);
  const [error, setError] = useState<string>();
  const [barcode, setBarcode] = useState('');
  const roleCopy = (value: Role): { label: string; guidance: string } => {
    const key = value.replace(/_([a-z])/g, (_, character: string) =>
      character.toUpperCase(),
    );
    const names: Record<
      string,
      {
        label: ReturnType<typeof translate>;
        guidance: ReturnType<typeof translate>;
      }
    > = {
      garmentOverview: {
        label: translate('garmentOverviewRole'),
        guidance: translate('garmentOverviewGuidance'),
      },
      careLabel: {
        label: translate('careLabelRole'),
        guidance: translate('careLabelGuidance'),
      },
      compositionLabel: {
        label: translate('compositionLabelRole'),
        guidance: translate('compositionLabelGuidance'),
      },
      barcodeBrandLabel: {
        label: translate('barcodeBrandLabelRole'),
        guidance: translate('barcodeBrandLabelGuidance'),
      },
      stainCloseup: {
        label: translate('stainCloseupRole'),
        guidance: translate('stainCloseupGuidance'),
      },
      damageCloseup: {
        label: translate('damageCloseupRole'),
        guidance: translate('damageCloseupGuidance'),
      },
      constructionDetail: {
        label: translate('constructionDetailRole'),
        guidance: translate('constructionDetailGuidance'),
      },
      other: {
        label: translate('otherRole'),
        guidance: translate('otherGuidance'),
      },
    };
    return names[key] ?? names.other!;
  };
  const addAsset = useCallback(
    (asset: ImagePicker.ImagePickerAsset): void => {
      setItems((current) =>
        current.length < maximumImages
          ? [...current, { role, asset }]
          : current,
      );
      setCameraVisible(false);
    },
    [role],
  );
  const addFromLibrary = useCallback(async (): Promise<void> => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 1,
    });
    const asset = result.assets?.[0];
    if (asset) addAsset(asset);
  }, [addAsset]);
  const move = (index: number, offset: number): void => {
    setItems((current) => {
      const target = index + offset;
      if (target < 0 || target >= current.length) return current;
      const next = [...current];
      const [item] = next.splice(index, 1);
      if (!item) return current;
      next.splice(target, 0, item);
      return next;
    });
  };
  async function submit(): Promise<void> {
    if (!token || !items.length) return;
    setBusy(true);
    setError(undefined);
    try {
      const scanResult = await createScanApiV1ScansPost({
        client: apiClient,
        body: { requested_language: locale },
      });
      if (!scanResult.data) throw new Error('create');
      const scan = scanResult.data;
      for (const [index, item] of items.entries()) {
        const contentType =
          item.asset.mimeType === 'image/png' ? 'image/png' : 'image/jpeg';
        const instructionResult = await addImageApiV1ScansScanIdImagesPost({
          client: apiClient,
          path: { scan_id: scan.scan_id },
          body: {
            role: item.role,
            content_type: contentType,
            display_order: index,
          },
        });
        if (!instructionResult.data) throw new Error('instruction');
        const upload = instructionResult.data;
        const binaryResult = await uploadBinaryFile({
          fileUri: item.asset.uri,
          headers: upload.headers,
          url: upload.url,
        });
        if (!binaryResult.ok) throw new Error('upload');
        const completion =
          await completeUploadApiV1ScansScanIdUploadsCompletePost({
            client: apiClient,
            path: { scan_id: scan.scan_id },
            body: {
              image_id: upload.image_id,
              content_type: contentType,
            },
          });
        if (!completion.data) throw new Error('complete');
      }
      if (barcode.trim()) {
        const lookup = await productLookupApiV1ScansScanIdProductLookupPost({
          client: apiClient,
          path: { scan_id: scan.scan_id },
          body: { barcode: barcode.trim() },
        });
        if (!lookup.data) throw new Error('barcode');
      }
      const analysis = await requestAnalysisApiV1ScansScanIdAnalysePost({
        client: apiClient,
        path: { scan_id: scan.scan_id },
      });
      if (!analysis.data) throw new Error('analyse');
      router.replace({ pathname: '/result', params: { scanId: scan.scan_id } });
    } catch {
      setError(translate('scanUploadFailed'));
    } finally {
      setBusy(false);
    }
  }
  const selectedRole = roleCopy(role);
  return (
    <FoundationShell
      title={translate('scanTitle')}
      description={translate('scanDescription')}
    >
      <ScrollView contentContainerStyle={styles.content}>
        <TextInput
          accessibilityLabel={translate('barcodeInputLabel')}
          keyboardType="number-pad"
          onChangeText={setBarcode}
          placeholder={translate('barcodeInputPlaceholder')}
          style={styles.barcodeInput}
          value={barcode}
        />
        <Text accessibilityRole="header">
          {translate('imageCount')
            .replace('{count}', String(items.length))
            .replace('{maximum}', String(maximumImages))}
        </Text>
        <Text style={styles.guidance}>{selectedRole.guidance}</Text>
        <View accessibilityLabel={translate('photoRole')} style={styles.roles}>
          {roles.map((value) => (
            <Pressable
              accessibilityRole="button"
              key={value}
              onPress={() => setRole(value)}
              style={({ pressed }) => [
                styles.roleButton,
                role === value && styles.roleButtonSelected,
                pressed && styles.roleButtonPressed,
              ]}
            >
              <Text
                numberOfLines={2}
                style={role === value ? styles.selected : styles.role}
              >
                {roleCopy(value).label}
              </Text>
            </Pressable>
          ))}
        </View>
        {items.map((item, index) => (
          <View key={`${item.asset.uri}-${index}`} style={styles.item}>
            <Image
              accessibilityLabel={translate('photoPreview').replace(
                '{number}',
                String(index + 1),
              )}
              source={{ uri: item.asset.uri }}
              style={styles.preview}
            />
            <View style={styles.itemCopy}>
              <Text>{roleCopy(item.role).label}</Text>
              <Text numberOfLines={1}>
                {item.asset.fileName ??
                  translate('photoPreview').replace(
                    '{number}',
                    String(index + 1),
                  )}
              </Text>
            </View>
            <Pressable
              accessibilityLabel={translate('movePhotoEarlier').replace(
                '{number}',
                String(index + 1),
              )}
              disabled={index === 0}
              onPress={() => move(index, -1)}
            >
              <Text>↑</Text>
            </Pressable>
            <Pressable
              accessibilityLabel={translate('movePhotoLater').replace(
                '{number}',
                String(index + 1),
              )}
              disabled={index === items.length - 1}
              onPress={() => move(index, 1)}
            >
              <Text>↓</Text>
            </Pressable>
            <Pressable
              accessibilityLabel={translate('removePhoto').replace(
                '{number}',
                String(index + 1),
              )}
              onPress={() =>
                setItems((current) =>
                  current.filter((_, itemIndex) => itemIndex !== index),
                )
              }
            >
              <Text>×</Text>
            </Pressable>
          </View>
        ))}
        {items.length >= maximumImages ? (
          <Text>{translate('imageLimitReached')}</Text>
        ) : null}
        {error ? (
          <Text accessibilityLiveRegion="polite" style={styles.error}>
            {error}
          </Text>
        ) : null}
        <Pressable
          accessibilityRole="button"
          disabled={items.length >= maximumImages || busy}
          onPress={() => setCameraVisible(true)}
          style={({ pressed }) => [
            styles.cameraButton,
            (items.length >= maximumImages || busy) && styles.buttonDisabled,
            pressed && styles.buttonPressed,
          ]}
        >
          <View style={styles.buttonContent}>
            <Feather color={colors.background} name="camera" size={19} />
            <Text style={styles.cameraButtonText}>{translate('addPhoto')}</Text>
          </View>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          disabled={items.length >= maximumImages || busy}
          onPress={() => void addFromLibrary()}
          style={({ pressed }) => [
            styles.secondaryButton,
            (items.length >= maximumImages || busy) &&
              styles.secondaryButtonDisabled,
            pressed && styles.buttonPressed,
          ]}
        >
          <View style={styles.buttonContent}>
            <Feather color={colors.primary} name="image" size={19} />
            <Text style={styles.secondaryButtonText}>
              {translate('addFromLibrary')}
            </Text>
          </View>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          disabled={!items.length || busy}
          onPress={() => void submit()}
          style={({ pressed }) => [
            styles.analyseButton,
            (!items.length || busy) && styles.buttonDisabled,
            pressed && styles.buttonPressed,
          ]}
        >
          <View style={styles.buttonContent}>
            <Feather color={colors.text} name="search" size={19} />
            <Text style={styles.buttonText}>
              {busy ? translate('uploadingImages') : translate('uploadImages')}
            </Text>
          </View>
        </Pressable>
      </ScrollView>
      <CameraCapture
        captureLabel={translate('cameraCapture')}
        cancelLabel={translate('cameraCancel')}
        description={selectedRole.guidance}
        onCaptured={addAsset}
        onClose={() => setCameraVisible(false)}
        onError={() => {
          setCameraVisible(false);
          setError(translate('cameraPermissionFailed'));
        }}
        title={translate('cameraTitle')}
        visible={cameraVisible}
      />
    </FoundationShell>
  );
}
const styles = StyleSheet.create({
  barcodeInput: {
    borderColor: colors.border,
    borderRadius: radii.medium,
    borderWidth: 1,
    padding: spacing.medium,
  },
  content: { gap: spacing.medium },
  guidance: {
    backgroundColor: colors.primarySoft,
    borderRadius: radii.medium,
    color: colors.text,
    lineHeight: 21,
    padding: spacing.medium,
  },
  roles: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.small,
    justifyContent: 'space-between',
  },
  roleButton: {
    alignItems: 'flex-start',
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: radii.pill,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 58,
    paddingHorizontal: spacing.medium,
    paddingVertical: spacing.small,
    width: '48%',
  },
  roleButtonSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.2,
    shadowRadius: 6,
    elevation: 2,
  },
  roleButtonPressed: { opacity: 0.84, transform: [{ scale: 0.98 }] },
  role: { color: colors.text, fontSize: 13, fontWeight: '700', lineHeight: 18 },
  selected: {
    color: colors.background,
    fontSize: 13,
    fontWeight: '800',
    lineHeight: 18,
  },
  item: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.small,
    padding: spacing.small,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radii.small,
  },
  preview: { width: 56, height: 56, borderRadius: radii.small },
  itemCopy: { flex: 1 },
  error: {
    backgroundColor: colors.dangerSoft,
    borderRadius: radii.small,
    color: colors.danger,
    padding: spacing.medium,
  },
  analyseButton: {
    alignItems: 'center',
    backgroundColor: colors.accent,
    borderRadius: radii.medium,
    justifyContent: 'center',
    minHeight: 52,
    padding: spacing.medium,
    shadowColor: colors.accent,
    shadowOffset: { height: 5, width: 0 },
    shadowOpacity: 0.2,
    shadowRadius: 9,
    elevation: 3,
  },
  buttonDisabled: {
    backgroundColor: colors.borderStrong,
    elevation: 0,
    shadowOpacity: 0,
  },
  buttonContent: {
    alignItems: 'center',
    flexDirection: 'column',
    gap: spacing.xsmall,
  },
  cameraButton: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: radii.medium,
    justifyContent: 'center',
    minHeight: 52,
    padding: spacing.medium,
    shadowColor: colors.primary,
    shadowOffset: { height: 5, width: 0 },
    shadowOpacity: 0.2,
    shadowRadius: 9,
    elevation: 3,
  },
  cameraButtonText: {
    color: colors.background,
    fontSize: 16,
    fontWeight: '800',
  },
  secondaryButton: {
    alignItems: 'center',
    backgroundColor: colors.background,
    borderColor: colors.primary,
    borderRadius: radii.medium,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 44,
    padding: spacing.medium,
  },
  secondaryButtonDisabled: { borderColor: colors.border, opacity: 0.55 },
  buttonPressed: { opacity: 0.86, transform: [{ translateY: 1 }] },
  buttonText: { color: colors.text, fontSize: 16, fontWeight: '800' },
  secondaryButtonText: {
    color: colors.primary,
    fontSize: 16,
    fontWeight: '800',
  },
});
