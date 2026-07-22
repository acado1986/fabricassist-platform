import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
import { useSession } from '../../auth/session';
import { FoundationShell } from '../../components/FoundationShell';
import { getApiBaseUrl } from '../../config/environment';
import { useTranslation } from '../../i18n/TranslationProvider';

type Source = {
  kind: string;
  image_id: string;
  fact: string;
  permission: string;
  temperature_c: number | null;
};
type RichResult = {
  title: string;
  validation_state: string;
  warnings: string[];
  violations: string[];
  sources: Source[];
  preparation: string[];
  stain_guidance: string[];
  cleaning: { method: string; maximum_temperature_c: number | null };
  detergent: string;
  drying: string[];
  ironing: string[];
  professional_care: string[];
  prohibitions: string[];
  uncertainties: string[];
  follow_up_questions: string[];
  actionable: boolean;
};
export default function Result(): ReactNode {
  const { scanId } = useLocalSearchParams<{ scanId: string }>();
  const { token } = useSession();
  const { locale, translate } = useTranslation();
  const [result, setResult] = useState<RichResult>();
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!scanId || !token) return;
    void fetch(
      `${getApiBaseUrl()}/api/v1/scans/${scanId}/result?language=${locale}`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
      .then((r) =>
        r.ok ? (r.json() as Promise<{ result: RichResult }>) : Promise.reject(),
      )
      .then((v) => setResult(v.result))
      .catch(() => setFailed(true));
  }, [locale, scanId, token]);
  return (
    <FoundationShell
      title={translate('resultTitle')}
      description={translate('resultDescription')}
    >
      <ScrollView contentContainerStyle={styles.content}>
        {!result && !failed ? (
          <ActivityIndicator color={colors.primary} />
        ) : null}
        {failed ? <Text>{translate('resultUnavailable')}</Text> : null}
        {result ? (
          <>
            <Text accessibilityRole="header" style={styles.title}>
              {result.title}
            </Text>
            <Section
              title={translate('richValidation')}
              values={[result.validation_state]}
            />
            <Section
              title={translate('richWarnings')}
              values={[...result.warnings, ...result.violations]}
            />
            <Section
              title={translate('richPreparation')}
              values={result.preparation}
            />
            <Section
              title={translate('richStain')}
              values={result.stain_guidance}
            />
            <Section
              title={translate('richCleaning')}
              values={[
                `${result.cleaning.method}${result.cleaning.maximum_temperature_c ? ` · ${result.cleaning.maximum_temperature_c} °C` : ''}`,
                result.detergent,
              ]}
            />
            <Section
              title={translate('resultProhibitions')}
              values={result.prohibitions}
              warning
            />
            <Section title={translate('richDrying')} values={result.drying} />
            <Section title={translate('richIroning')} values={result.ironing} />
            <Section
              title={translate('richProfessional')}
              values={result.professional_care}
            />
            <Section
              title={translate('richSources')}
              values={result.sources.map(
                (s) =>
                  `${s.kind}: ${s.fact} · ${s.permission}${s.temperature_c ? ` · ${s.temperature_c} °C` : ''}`,
              )}
            />
            <Section
              title={translate('richUncertainty')}
              values={[...result.uncertainties, ...result.follow_up_questions]}
            />
          </>
        ) : null}
        <Pressable
          accessibilityRole="button"
          onPress={() => router.replace('/scan')}
          style={styles.button}
        >
          <Text>{translate('backToScan')}</Text>
        </Pressable>
      </ScrollView>
    </FoundationShell>
  );
}
function Section({
  title,
  values,
  warning = false,
}: {
  title: string;
  values: string[];
  warning?: boolean;
}): ReactNode {
  if (!values.length) return null;
  return (
    <View style={[styles.section, warning && styles.warning]}>
      <Text style={styles.heading}>{title}</Text>
      {values.map((value, i) => (
        <Text key={`${title}-${i}`}>• {value}</Text>
      ))}
    </View>
  );
}
const styles = StyleSheet.create({
  content: { gap: spacing.medium },
  title: { fontSize: 22, fontWeight: '800', color: colors.text },
  section: {
    gap: spacing.small,
    padding: spacing.medium,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radii.medium,
  },
  warning: { backgroundColor: colors.dangerSoft },
  heading: { fontWeight: '800', color: colors.primary },
  button: {
    padding: spacing.medium,
    borderRadius: radii.medium,
    borderWidth: 1,
    borderColor: colors.primary,
  },
});
