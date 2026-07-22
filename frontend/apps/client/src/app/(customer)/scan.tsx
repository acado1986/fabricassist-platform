import type { ReactNode } from 'react';
import { useState } from 'react';
import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
import { useSession } from '../../auth/session';
import { FoundationShell } from '../../components/FoundationShell';
import { getApiBaseUrl } from '../../config/environment';
import { useTranslation } from '../../i18n/TranslationProvider';

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
  const { token } = useSession();
  const { translate } = useTranslation();
  const [items, setItems] = useState<Selected[]>([]);
  const [role, setRole] = useState<Role>('garment_overview');
  const [busy, setBusy] = useState(false);
  async function add(): Promise<void> {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 1,
    });
    const asset = result.assets?.[0];
    if (asset && items.length < 8) setItems([...items, { role, asset }]);
  }
  async function submit(): Promise<void> {
    if (!token || !items.length) return;
    setBusy(true);
    try {
      const scan = await fetch(`${getApiBaseUrl()}/api/v1/scans`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ requested_language: 'en' }),
      }).then((r) => r.json() as Promise<{ scan_id: string }>);
      for (const [i, item] of items.entries()) {
        const contentType =
          item.asset.mimeType === 'image/png' ? 'image/png' : 'image/jpeg';
        const upload = await fetch(
          `${getApiBaseUrl()}/api/v1/scans/${scan.scan_id}/images`,
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              role: item.role,
              content_type: contentType,
              display_order: i,
            }),
          },
        ).then(
          (r) =>
            r.json() as Promise<{
              image_id: string;
              url: string;
              headers: Record<string, string>;
            }>,
        );
        await fetch(upload.url, {
          method: 'PUT',
          headers: upload.headers,
          body: await (await fetch(item.asset.uri)).blob(),
        });
        await fetch(
          `${getApiBaseUrl()}/api/v1/scans/${scan.scan_id}/uploads/complete`,
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              image_id: upload.image_id,
              content_type: contentType,
            }),
          },
        );
      }
      await fetch(`${getApiBaseUrl()}/api/v1/scans/${scan.scan_id}/analyse`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      router.replace({ pathname: '/result', params: { scanId: scan.scan_id } });
    } finally {
      setBusy(false);
    }
  }
  return (
    <FoundationShell
      title={translate('scanTitle')}
      description={translate('scanDescription')}
    >
      <ScrollView contentContainerStyle={styles.content}>
        <Text accessibilityRole="header">{items.length}/8</Text>
        <View style={styles.roles}>
          {roles.map((value) => (
            <Pressable
              key={value}
              accessibilityRole="button"
              onPress={() => setRole(value)}
            >
              <Text style={role === value ? styles.selected : styles.role}>
                {value}
              </Text>
            </Pressable>
          ))}
        </View>
        {items.map((item, index) => (
          <View key={`${item.asset.uri}-${index}`} style={styles.item}>
            <Text>
              {item.role}: {item.asset.fileName ?? 'image'}
            </Text>
            <Pressable
              accessibilityLabel={`Remove image ${index + 1}`}
              onPress={() => setItems(items.filter((_, i) => i !== index))}
            >
              <Text>Remove</Text>
            </Pressable>
          </View>
        ))}
        <Pressable
          accessibilityRole="button"
          disabled={items.length >= 8}
          onPress={() => void add()}
          style={styles.button}
        >
          <Text>Add photo</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          disabled={!items.length || busy}
          onPress={() => void submit()}
          style={styles.button}
        >
          <Text>{busy ? 'Uploading…' : translate('uploadImages')}</Text>
        </Pressable>
      </ScrollView>
    </FoundationShell>
  );
}
const styles = StyleSheet.create({
  content: { gap: spacing.medium },
  roles: { gap: spacing.small },
  role: { color: colors.text },
  selected: { color: colors.primary, fontWeight: '800' },
  item: {
    padding: spacing.small,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radii.small,
  },
  button: {
    padding: spacing.medium,
    backgroundColor: colors.primarySoft,
    borderRadius: radii.medium,
  },
});
