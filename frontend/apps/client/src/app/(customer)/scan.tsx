import type { ReactNode } from 'react';
import { useState } from 'react';
import * as ImagePicker from 'expo-image-picker';
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

type UploadStatus =
  | 'idle'
  | 'uploading'
  | 'complete'
  | 'createFailed'
  | 'uploadFailed'
  | 'validationFailed';

export default function Scan(): ReactNode {
  const { token, signOut } = useSession();
  const { translate } = useTranslation();
  const [asset, setAsset] = useState<ImagePicker.ImagePickerAsset | null>(null);
  const [status, setStatus] = useState<UploadStatus>('idle');

  async function choose(): Promise<void> {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 1,
    });
    if (!result.canceled) {
      const selected = result.assets[0];
      if (selected) {
        setAsset(selected);
        setStatus('idle');
      }
    }
  }

  async function upload(): Promise<void> {
    if (!asset || !token) return;
    setStatus('uploading');
    const contentType =
      asset.mimeType === 'image/png'
        ? 'image/png'
        : asset.mimeType === 'image/webp'
          ? 'image/webp'
          : 'image/jpeg';
    const created = await fetch(`${getApiBaseUrl()}/api/v1/scans`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ kind: 'care_label', content_type: contentType }),
    });
    if (!created.ok) {
      setStatus('createFailed');
      return;
    }
    const payload = (await created.json()) as {
      scan_id: string;
      upload: {
        upload_id: string;
        url: string;
        headers: Record<string, string>;
      };
    };
    const image = await fetch(asset.uri);
    const blob = await image.blob();
    const put = await fetch(payload.upload.url, {
      method: 'PUT',
      headers: payload.upload.headers,
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
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          upload_id: payload.upload.upload_id,
          content_type: contentType,
        }),
      },
    );
    setStatus(complete.ok ? 'complete' : 'validationFailed');
  }

  const statusMessage =
    status === 'complete'
      ? translate('scanComplete')
      : status === 'createFailed'
        ? translate('scanCreateFailed')
        : status === 'uploadFailed'
          ? translate('scanUploadFailed')
          : status === 'validationFailed'
            ? translate('scanValidationFailed')
            : null;

  return (
    <FoundationShell
      title={translate('scanTitle')}
      description={translate('scanDescription')}
    >
      <View style={styles.stepRow}>
        <Text style={styles.stepLabel}>{translate('scanStep')}</Text>
        <View style={styles.requiredBadge}>
          <Text style={styles.requiredText}>{translate('required')}</Text>
        </View>
      </View>

      <Pressable
        accessibilityRole="button"
        onPress={() => void choose()}
        style={({ pressed }) => [
          styles.dropZone,
          pressed && styles.dropZonePressed,
        ]}
      >
        {asset ? (
          <Image
            accessibilityLabel={translate('selectedImage')}
            source={{ uri: asset.uri }}
            style={styles.preview}
          />
        ) : (
          <View style={styles.uploadIcon}>
            <Text style={styles.uploadIconText}>↑</Text>
          </View>
        )}
        <Text style={styles.dropTitle}>
          {translate(asset ? 'changeImage' : 'chooseImage')}
        </Text>
        <Text style={styles.dropDescription}>
          {asset?.fileName ?? translate('imageGuidance')}
        </Text>
        <Text style={styles.formats}>{translate('imageFormats')}</Text>
      </Pressable>

      {statusMessage ? (
        <View
          style={[
            styles.statusBox,
            status === 'complete' ? styles.successBox : styles.errorBox,
          ]}
        >
          <Text
            style={
              status === 'complete' ? styles.successText : styles.errorText
            }
          >
            {statusMessage}
          </Text>
        </View>
      ) : null}

      {asset ? (
        <Pressable
          accessibilityRole="button"
          disabled={status === 'uploading'}
          onPress={() => void upload()}
          style={({ pressed }) => [
            styles.primaryButton,
            pressed && styles.primaryPressed,
            status === 'uploading' && styles.disabled,
          ]}
        >
          {status === 'uploading' ? (
            <>
              <ActivityIndicator color={colors.background} />
              <Text style={styles.primaryText}>
                {translate('uploadingImage')}
              </Text>
            </>
          ) : (
            <Text style={styles.primaryText}>{translate('uploadImage')}</Text>
          )}
        </Pressable>
      ) : null}

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

const styles = StyleSheet.create({
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
    minHeight: 250,
    padding: spacing.large,
  },
  dropZonePressed: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
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
