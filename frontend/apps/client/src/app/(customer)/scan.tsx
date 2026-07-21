import type { ReactNode } from 'react';
import { useState } from 'react';
import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import {
  ActivityIndicator,
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { colors, radii, spacing } from '@fabricassist/design-tokens';

import { useSession } from '../../auth/session';
import { FoundationShell } from '../../components/FoundationShell';
import { getApiBaseUrl } from '../../config/environment';
import { useTranslation } from '../../i18n/TranslationProvider';
import { CameraCapture } from '../../platform/CameraCapture';

type UploadStatus =
  | 'idle'
  | 'uploading'
  | 'complete'
  | 'processing'
  | 'createFailed'
  | 'uploadFailed'
  | 'validationFailed'
  | 'analysisFailed'
  | 'analysisProviderFailed'
  | 'cameraPermissionFailed';

type ImageKind = 'garment' | 'care_label';
type SelectedImages = Record<ImageKind, ImagePicker.ImagePickerAsset | null>;

type UploadInstruction = {
  upload_id: string;
  kind: ImageKind;
  url: string;
  headers: Record<string, string>;
};

function contentTypeFor(
  asset: ImagePicker.ImagePickerAsset,
): 'image/jpeg' | 'image/png' | 'image/webp' {
  if (asset.mimeType === 'image/png') return 'image/png';
  if (asset.mimeType === 'image/webp') return 'image/webp';
  return 'image/jpeg';
}

export default function Scan(): ReactNode {
  const { refreshAccessToken, token, signOut } = useSession();
  const { translate } = useTranslation();
  const [images, setImages] = useState<SelectedImages>({
    garment: null,
    care_label: null,
  });
  const [status, setStatus] = useState<UploadStatus>('idle');
  const [scanId, setScanId] = useState<string | null>(null);
  const [captureKind, setCaptureKind] = useState<ImageKind | null>(null);

  async function chooseFromLibrary(kind: ImageKind): Promise<void> {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 1,
    });
    if (!result.canceled) {
      const selected = result.assets[0];
      if (selected) {
        setImages((current) => ({ ...current, [kind]: selected }));
        setStatus('idle');
        setScanId(null);
      }
    }
  }

  function captureImage(asset: ImagePicker.ImagePickerAsset): void {
    if (!captureKind) return;
    setImages((current) => ({ ...current, [captureKind]: asset }));
    setStatus('idle');
    setScanId(null);
    setCaptureKind(null);
  }

  async function upload(): Promise<void> {
    const garment = images.garment;
    const careLabel = images.care_label;
    if ((!garment && !careLabel) || !token) return;
    setStatus('uploading');
    const selected: {
      kind: ImageKind;
      asset: ImagePicker.ImagePickerAsset;
    }[] = [];
    if (careLabel) selected.push({ kind: 'care_label', asset: careLabel });
    if (garment) selected.push({ kind: 'garment', asset: garment });
    async function createScan(accessToken: string): Promise<Response> {
      return fetch(`${getApiBaseUrl()}/api/v1/scans`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          images: selected.map(({ kind, asset }) => ({
            kind,
            content_type: contentTypeFor(asset),
          })),
        }),
      });
    }

    try {
      let accessToken = token;
      let created = await createScan(accessToken);
      if (created.status === 401) {
        const refreshedToken = await refreshAccessToken();
        if (!refreshedToken) {
          setStatus('createFailed');
          return;
        }
        accessToken = refreshedToken;
        created = await createScan(accessToken);
      }
      if (!created.ok) {
        setStatus('createFailed');
        return;
      }
      const payload = (await created.json()) as {
        scan_id: string;
        uploads: UploadInstruction[];
      };
      for (const selection of selected) {
        const instruction = payload.uploads.find(
          (uploadInstruction) => uploadInstruction.kind === selection.kind,
        );
        if (!instruction) {
          setStatus('createFailed');
          return;
        }
        const image = await fetch(selection.asset.uri);
        const blob = await image.blob();
        const put = await fetch(instruction.url, {
          method: 'PUT',
          headers: instruction.headers,
          body: blob,
        });
        if (!put.ok) {
          setStatus('uploadFailed');
          return;
        }
        const complete = await fetch(
          `${getApiBaseUrl()}/api/v1/scans/${payload.scan_id}/uploads/complete`,
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${accessToken}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              upload_id: instruction.upload_id,
              content_type: contentTypeFor(selection.asset),
            }),
          },
        );
        if (!complete.ok) {
          setStatus('validationFailed');
          return;
        }
      }
      setStatus('processing');
      const analysis = await fetch(
        `${getApiBaseUrl()}/api/v1/scans/${payload.scan_id}/analyse`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${accessToken}`,
            'Idempotency-Key': `scan-${payload.scan_id}`,
          },
        },
      );
      if (!analysis.ok) {
        setStatus('validationFailed');
        return;
      }
      setScanId(payload.scan_id);
      void pollForResult(payload.scan_id, accessToken);
    } catch {
      setStatus('uploadFailed');
    }
  }

  async function pollForResult(id: string, accessToken: string): Promise<void> {
    for (let attempt = 0; attempt < 30; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      const response = await fetch(`${getApiBaseUrl()}/api/v1/scans/${id}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!response.ok) continue;
      const scan = (await response.json()) as {
        error_code?: string | null;
        status: string;
      };
      if (scan.status === 'completed' || scan.status === 'needs_review') {
        router.replace({ pathname: '/result', params: { scanId: id } });
        return;
      }
      if (scan.status === 'needs_better_image') {
        setStatus('validationFailed');
        return;
      }
      if (scan.status === 'failed') {
        setStatus(
          scan.error_code?.startsWith('VISION_')
            ? 'analysisProviderFailed'
            : 'analysisFailed',
        );
        return;
      }
    }
    setStatus('validationFailed');
  }

  const statusMessage =
    status === 'complete'
      ? translate('scanComplete')
      : status === 'processing'
        ? translate('analysisQueued')
        : status === 'createFailed'
          ? translate('scanCreateFailed')
          : status === 'uploadFailed'
            ? translate('scanUploadFailed')
            : status === 'validationFailed'
              ? translate('scanValidationFailed')
              : status === 'analysisFailed'
                ? translate('analysisFailed')
                : status === 'analysisProviderFailed'
                  ? translate('analysisProviderFailed')
                  : status === 'cameraPermissionFailed'
                    ? translate('cameraPermissionFailed')
                    : null;

  return (
    <FoundationShell
      title={translate('scanTitle')}
      description={translate('scanDescription')}
    >
      <CameraCapture
        cancelLabel={translate('cameraCancel')}
        captureLabel={translate('cameraCapture')}
        description={translate('cameraDescription')}
        onCaptured={captureImage}
        onClose={() => setCaptureKind(null)}
        onError={() => {
          setCaptureKind(null);
          setStatus('cameraPermissionFailed');
        }}
        title={translate('cameraTitle')}
        visible={captureKind !== null}
      />
      <ImageField
        accessibilityLabel={translate('selectedCareLabelImage')}
        asset={images.care_label}
        changeLabel={translate('changeCareLabelImage')}
        chooseLabel={translate('chooseCareLabelImage')}
        formats={translate('imageFormats')}
        guidance={translate('careLabelImageGuidance')}
        label={translate('careLabelPhoto')}
        onTakePhoto={() => setCaptureKind('care_label')}
        onUpload={() => void chooseFromLibrary('care_label')}
        required={translate('required')}
        takePhoto={translate('takePhoto')}
        uploadExisting={translate('uploadExistingImage')}
      />

      <ImageField
        accessibilityLabel={translate('selectedGarmentImage')}
        asset={images.garment}
        changeLabel={translate('changeGarmentImage')}
        chooseLabel={translate('chooseGarmentImage')}
        formats={translate('imageFormats')}
        guidance={translate('garmentImageGuidance')}
        label={translate('garmentPhoto')}
        onTakePhoto={() => setCaptureKind('garment')}
        onUpload={() => void chooseFromLibrary('garment')}
        required={translate('required')}
        takePhoto={translate('takePhoto')}
        uploadExisting={translate('uploadExistingImage')}
      />

      {statusMessage ? (
        <View
          style={[
            styles.statusBox,
            status === 'complete' || status === 'processing'
              ? styles.successBox
              : styles.errorBox,
          ]}
        >
          <Text
            style={
              status === 'complete' || status === 'processing'
                ? styles.successText
                : styles.errorText
            }
          >
            {statusMessage}
          </Text>
        </View>
      ) : null}

      {scanId && status === 'processing' ? (
        <Pressable
          accessibilityRole="button"
          onPress={() =>
            router.replace({ pathname: '/result', params: { scanId } })
          }
          style={styles.secondaryButton}
        >
          <Text style={styles.secondaryText}>{translate('viewResult')}</Text>
        </Pressable>
      ) : null}

      <Pressable
        accessibilityRole="button"
        disabled={
          (!images.care_label && !images.garment) || status === 'uploading'
        }
        onPress={() => void upload()}
        style={({ pressed }) => [
          styles.primaryButton,
          pressed && styles.primaryPressed,
          ((!images.care_label && !images.garment) || status === 'uploading') &&
            styles.disabled,
        ]}
      >
        {status === 'uploading' ? (
          <>
            <ActivityIndicator color={colors.background} />
            <Text style={styles.primaryText}>
              {translate('uploadingImages')}
            </Text>
          </>
        ) : (
          <Text style={styles.primaryText}>{translate('uploadImages')}</Text>
        )}
      </Pressable>

      <View style={styles.divider} />
      <Pressable
        accessibilityRole="button"
        onPress={() => void signOut()}
        style={({ pressed }) => [
          styles.secondaryButton,
          pressed && styles.secondaryPressed,
        ]}
      >
        <Text style={styles.secondaryText}>{translate('signOut')}</Text>
      </Pressable>
    </FoundationShell>
  );
}

function ImageField({
  accessibilityLabel,
  asset,
  changeLabel,
  chooseLabel,
  formats,
  guidance,
  label,
  onTakePhoto,
  onUpload,
  required,
  takePhoto,
  uploadExisting,
}: {
  accessibilityLabel: string;
  asset: ImagePicker.ImagePickerAsset | null;
  changeLabel: string;
  chooseLabel: string;
  formats: string;
  guidance: string;
  label: string;
  onTakePhoto: () => void;
  onUpload: () => void;
  required: string;
  takePhoto: string;
  uploadExisting: string;
}): ReactNode {
  return (
    <View style={styles.imageField}>
      <View style={styles.stepRow}>
        <Text style={styles.stepLabel}>{label}</Text>
        <View style={styles.requiredBadge}>
          <Text style={styles.requiredText}>{required}</Text>
        </View>
      </View>
      <View style={styles.dropZone}>
        {asset ? (
          <Image
            accessibilityLabel={accessibilityLabel}
            source={{ uri: asset.uri }}
            style={styles.preview}
          />
        ) : (
          <View style={styles.uploadIcon}>
            <Text style={styles.uploadIconText}>↑</Text>
          </View>
        )}
        <Text style={styles.dropTitle}>
          {asset ? changeLabel : chooseLabel}
        </Text>
        <Text style={styles.dropDescription}>
          {asset?.fileName ?? guidance}
        </Text>
        <Text style={styles.formats}>{formats}</Text>
      </View>
      <View style={styles.sourceActions}>
        <Pressable
          accessibilityRole="button"
          onPress={onTakePhoto}
          style={({ pressed }) => [
            styles.sourcePrimary,
            pressed && styles.primaryPressed,
          ]}
        >
          <Text style={styles.sourcePrimaryText}>{takePhoto}</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          onPress={onUpload}
          style={({ pressed }) => [
            styles.sourceSecondary,
            pressed && styles.secondaryPressed,
          ]}
        >
          <Text style={styles.secondaryText}>{uploadExisting}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  imageField: { gap: spacing.small },
  stepRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  stepLabel: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 0.8,
  },
  requiredBadge: {
    backgroundColor: colors.primarySoft,
    borderRadius: radii.pill,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  requiredText: { color: colors.primary, fontSize: 11, fontWeight: '700' },
  dropZone: {
    alignItems: 'center',
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.borderStrong,
    borderRadius: radii.medium,
    borderStyle: 'dashed',
    borderWidth: 1.5,
    gap: spacing.small,
    justifyContent: 'center',
    minHeight: 210,
    padding: spacing.large,
  },
  sourceActions: { flexDirection: 'row', gap: spacing.small },
  sourcePrimary: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: radii.medium,
    flex: 1,
    justifyContent: 'center',
    minHeight: 46,
    paddingHorizontal: spacing.medium,
  },
  sourcePrimaryText: {
    color: colors.background,
    fontSize: 14,
    fontWeight: '800',
  },
  sourceSecondary: {
    alignItems: 'center',
    borderColor: colors.border,
    borderRadius: radii.medium,
    borderWidth: 1,
    flex: 1,
    justifyContent: 'center',
    minHeight: 46,
    paddingHorizontal: spacing.medium,
  },
  uploadIcon: {
    alignItems: 'center',
    backgroundColor: colors.background,
    borderRadius: radii.pill,
    height: 54,
    justifyContent: 'center',
    marginBottom: spacing.small,
    width: 54,
  },
  uploadIconText: { color: colors.primary, fontSize: 28, fontWeight: '500' },
  preview: {
    borderRadius: radii.medium,
    height: 160,
    marginBottom: spacing.small,
    resizeMode: 'cover',
    width: '100%',
  },
  dropTitle: {
    color: colors.text,
    fontSize: 17,
    fontWeight: '800',
    textAlign: 'center',
  },
  dropDescription: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
    textAlign: 'center',
  },
  formats: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: '600',
    marginTop: spacing.xsmall,
    textAlign: 'center',
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: radii.medium,
    flexDirection: 'row',
    gap: spacing.small,
    justifyContent: 'center',
    minHeight: 52,
    paddingHorizontal: spacing.large,
  },
  primaryPressed: { backgroundColor: colors.primaryPressed },
  primaryText: { color: colors.background, fontSize: 16, fontWeight: '800' },
  disabled: { opacity: 0.65 },
  divider: {
    backgroundColor: colors.border,
    height: 1,
    marginVertical: spacing.xsmall,
  },
  secondaryButton: {
    alignItems: 'center',
    borderColor: colors.border,
    borderRadius: radii.medium,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 48,
  },
  secondaryPressed: { backgroundColor: colors.surfaceMuted },
  secondaryText: { color: colors.text, fontSize: 14, fontWeight: '700' },
  statusBox: { borderRadius: radii.small, padding: 12 },
  successBox: { backgroundColor: colors.successSoft },
  errorBox: { backgroundColor: colors.dangerSoft },
  successText: {
    color: colors.success,
    fontSize: 13,
    fontWeight: '700',
    lineHeight: 19,
  },
  errorText: {
    color: colors.danger,
    fontSize: 13,
    fontWeight: '700',
    lineHeight: 19,
  },
});
