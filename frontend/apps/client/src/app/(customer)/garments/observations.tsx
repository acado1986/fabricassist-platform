import { type ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useQuery } from '@apollo/client';
import { router, useLocalSearchParams } from 'expo-router';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
import { GarmentDetailDocument } from '@fabricassist/api-client';
import { useSession } from '../../../auth/session';
import { FoundationShell } from '../../../components/FoundationShell';
import { useTranslation } from '../../../i18n/TranslationProvider';
import { friendlyCode } from '../../../features/garment-analysis/friendlyCodes';

const labels: Record<string, [string, string]> = {
  iron: ['Iron', 'Planchado'],
  professional_wet_clean: [
    'Professional wet cleaning',
    'Limpieza profesional en húmedo',
  ],
  professional_dry_clean: [
    'Professional dry cleaning',
    'Limpieza en seco profesional',
  ],
  tumble_dry: ['Tumble dry', 'Secado en secadora'],
  natural_dry: ['Air dry', 'Secado al aire'],
  water_wash: ['Water wash', 'Lavado con agua'],
  domestic_detergent: ['Domestic detergent', 'Detergente doméstico'],
  bleach: ['Bleach', 'Lejía'],
};

export default function ObservationsPage(): ReactNode {
  const { garmentId } = useLocalSearchParams<{ garmentId: string }>();
  const { token } = useSession();
  const { locale, translate } = useTranslation();
  const { data } = useQuery(GarmentDetailDocument, {
    skip: !token,
    variables: { garmentId, first: 20, after: null, language: locale },
  });
  const raw = data?.garmentDetail?.observations ?? [];
  const grouped = raw.reduce(
    (groups, observation) => {
      const key = observation.observationType;
      const value = formatValue(
        (observation.value ?? {}) as Record<string, unknown>,
        locale,
      );
      if (!groups[key])
        groups[key] = { authority: observation.authority, values: [] };
      if (value && !groups[key].values.includes(value))
        groups[key].values.push(value);
      return groups;
    },
    {} as Record<string, { authority: string; values: string[] }>,
  );
  return (
    <FoundationShell
      title={translate('garmentObservations')}
      description={translate('garmentHistoryDescription')}
    >
      <ScrollView contentContainerStyle={styles.content}>
        <Pressable onPress={() => router.back()}>
          <Text style={styles.back}>‹ {translate('garmentHistoryTitle')}</Text>
        </Pressable>
        {Object.entries(grouped).map(([type, item]) => (
          <View key={type} style={styles.card}>
            <Text style={styles.title}>
              {type === 'care' ? translate('observationCare') : friendly(type)}
            </Text>
            <Text style={styles.source}>
              {translate('observationSourceLabel')}: {friendly(item.authority)}
            </Text>
            {item.values.map((value) => (
              <Text key={value} style={styles.value}>
                • {value}
              </Text>
            ))}
          </View>
        ))}
      </ScrollView>
    </FoundationShell>
  );
}
function formatValue(
  value: Record<string, unknown>,
  locale: 'en' | 'es',
): string {
  const code = typeof value.code === 'string' ? value.code : '';
  const action =
    labels[code]?.[locale === 'es' ? 1 : 0] ?? (code ? friendly(code) : '');
  const permission =
    typeof value.permission === 'string' && value.permission !== 'unknown'
      ? ` · ${locale === 'es' ? 'permiso' : 'permission'}: ${friendlyCode(value.permission, (key) => (key === 'permissionProhibited' ? (locale === 'es' ? 'No permitido' : 'Not allowed') : locale === 'es' ? 'No confirmado' : 'Not confirmed'))}`
      : '';
  const temperature =
    typeof value.maximum_temperature_c === 'number'
      ? ` · ${value.maximum_temperature_c} °C`
      : '';
  return `${action}${permission}${temperature}`.trim();
}
function friendly(value: string): string {
  return value
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
const styles = StyleSheet.create({
  content: { gap: spacing.medium },
  back: { color: colors.primary, fontWeight: '700' },
  card: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radii.medium,
    gap: spacing.xsmall,
    padding: spacing.medium,
  },
  title: { color: colors.text, fontWeight: '800' },
  source: { color: colors.muted, fontSize: 12 },
  value: { color: colors.text, lineHeight: 20 },
});
