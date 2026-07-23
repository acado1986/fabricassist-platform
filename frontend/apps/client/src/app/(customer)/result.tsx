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
  change_summary?: string;
};
export default function Result(): ReactNode {
  const { scanId } = useLocalSearchParams<{ scanId: string }>();
  const { token } = useSession();
  const { locale, translate } = useTranslation();
  const [result, setResult] = useState<RichResult>();
  const [failed, setFailed] = useState(false);
  const [stage, setStage] = useState<string>();
  const [garmentId, setGarmentId] = useState<string>();
  const stageLabel = (value: string): string => {
    if (value === 'queued') return translate('analysisStageQueued');
    if (value === 'processing') return translate('analysisStageProcessing');
    if (value === 'evidence') return translate('analysisStageEvidence');
    if (value === 'completed') return translate('analysisStageCompleted');
    return translate('resultLoading');
  };
  useEffect(() => {
    if (!scanId || !token) return;
    let cancelled = false;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    const load = async (): Promise<void> => {
      try {
        const headers = { Authorization: `Bearer ${token}` };
        const scan = await fetch(`${getApiBaseUrl()}/api/v1/scans/${scanId}`, {
          headers,
        });
        if (!scan.ok) throw new Error('SCAN_UNAVAILABLE');
        const status = (await scan.json()) as {
          status: string;
          analysis_stage?: string;
          garment_id?: string;
        };
        if (cancelled) return;
        setStage(status.analysis_stage ?? status.status);
        setGarmentId(status.garment_id);
        if (status.status === 'failed') {
          setFailed(true);
          return;
        }
        const response = await fetch(
          `${getApiBaseUrl()}/api/v1/scans/${scanId}/result?language=${locale}`,
          { headers },
        );
        if (response.ok) {
          const value = (await response.json()) as { result: RichResult };
          if (!cancelled) setResult(value.result);
          return;
        }
        if (!cancelled) timeout = setTimeout(() => void load(), 1500);
      } catch {
        if (!cancelled) setFailed(true);
      }
    };
    void load();
    return () => {
      cancelled = true;
      if (timeout) clearTimeout(timeout);
    };
  }, [locale, scanId, token]);
  return (
    <FoundationShell
      title={translate('resultTitle')}
      description={translate('resultDescription')}
    >
      <ScrollView contentContainerStyle={styles.content}>
        {!result && !failed ? (
          <View accessibilityLiveRegion="polite" style={styles.loading}>
            <ActivityIndicator color={colors.primary} size="large" />
            <Text style={styles.loadingTitle}>
              {translate('resultLoading')}
            </Text>
            <View style={styles.progressTrack}>
              <View style={styles.progressValue} />
            </View>
            <Text style={styles.loadingCopy}>
              {stage
                ? translate('resultStage').replace('{stage}', stageLabel(stage))
                : translate('resultLoadingCopy')}
            </Text>
          </View>
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
            <Section
              title={translate('garmentChangeSummary')}
              values={result.change_summary ? [result.change_summary] : []}
            />
            {garmentId ? (
              <Pressable
                accessibilityRole="button"
                onPress={() => router.push(`/garments/${garmentId}`)}
                style={styles.button}
              >
                <Text>{translate('viewGarmentHistory')}</Text>
              </Pressable>
            ) : null}
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
  loading: {
    alignItems: 'center',
    gap: spacing.medium,
    paddingVertical: spacing.xxlarge,
  },
  loadingTitle: { color: colors.text, fontSize: 18, fontWeight: '800' },
  loadingCopy: { color: colors.muted, textAlign: 'center' },
  progressTrack: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radii.pill,
    height: 8,
    overflow: 'hidden',
    width: '100%',
  },
  progressValue: {
    backgroundColor: colors.primary,
    borderRadius: radii.pill,
    height: '100%',
    width: '62%',
  },
  button: {
    padding: spacing.medium,
    borderRadius: radii.medium,
    borderWidth: 1,
    borderColor: colors.primary,
  },
});
