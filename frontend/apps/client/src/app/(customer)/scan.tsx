import type { ReactNode } from 'react';
import { useState } from 'react';
import * as ImagePicker from 'expo-image-picker';
import { Button, Image, Text, View } from 'react-native';
import { useSession } from '../../auth/session';
import { FoundationShell } from '../../components/FoundationShell';
import { getApiBaseUrl } from '../../config/environment';
export default function Scan(): ReactNode {
  const { token, signOut } = useSession();
  const [asset, setAsset] = useState<ImagePicker.ImagePickerAsset | null>(null);
  const [status, setStatus] = useState('');
  async function choose(): Promise<void> {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 1,
    });
    if (!result.canceled) {
      const selected = result.assets[0];
      if (selected) setAsset(selected);
    }
  }
  async function upload(): Promise<void> {
    if (!asset || !token) return;
    setStatus('Uploading…');
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
      setStatus('Could not create scan.');
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
      setStatus('Upload failed.');
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
    setStatus(
      complete.ok
        ? 'Upload complete. Analysis is not implemented yet.'
        : 'Image validation failed. Retake a clear image.',
    );
  }
  return (
    <FoundationShell>
      <Text accessibilityRole="header">New care-label scan</Text>
      <Text>
        Choose a clear, well-lit care-label image. Analysis is not available
        yet.
      </Text>
      <Button title="Choose image" onPress={() => void choose()} />
      {asset ? (
        <View>
          <Image
            source={{ uri: asset.uri }}
            style={{ width: 200, height: 200 }}
          />
          <Button title="Upload image" onPress={() => void upload()} />
        </View>
      ) : null}
      <Text>{status}</Text>
      <Button title="Sign out" onPress={() => void signOut()} />
    </FoundationShell>
  );
}
