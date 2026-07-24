import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import Feather from '@expo/vector-icons/Feather';
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
  product_information?: {
    barcode: string;
    status: string;
    provider: string;
    source_name: string | null;
    source_reference: string | null;
    license_name: string | null;
    retrieved_at: string | null;
    product: Record<string, unknown> | null;
  } | null;
};
export default function Result(): ReactNode {
  const { scanId } = useLocalSearchParams<{ scanId: string }>();
  const { token } = useSession();
  const { locale, translate } = useTranslation();
  const [result, setResult] = useState<RichResult>();
  const [failed, setFailed] = useState(false);
  const [stage, setStage] = useState<string>();
  const [garmentId, setGarmentId] = useState<string>();
  const [lifecycleMessage, setLifecycleMessage] = useState<string>();
  const requestReview = async (): Promise<void> => {
    if (!scanId || !token) return;
    const response = await fetch(
      `${getApiBaseUrl()}/api/v1/scans/${scanId}/feedback`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ request_review: true }),
      },
    );
    setLifecycleMessage(
      response.ok
        ? translate('reviewRequested')
        : translate('reviewRequestFailed'),
    );
  };
  const deleteAnalysis = async (): Promise<void> => {
    if (!scanId || !token) return;
    const response = await fetch(`${getApiBaseUrl()}/api/v1/scans/${scanId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    if (response.ok) {
      setLifecycleMessage(translate('deletionRequested'));
      router.replace('/scan');
      return;
    }
    setLifecycleMessage(translate('deletionRequestFailed'));
  };
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
            {result.product_information ? (
              <Section
                title={translate('productInformation')}
                values={[
                  `${translate('productBarcode')}: ${result.product_information.barcode}`,
                  `${translate('productMatchStatus')}: ${result.product_information.status}`,
                  `${translate('productSource')}: ${result.product_information.source_name ?? result.product_information.provider}`,
                  ...(result.product_information.retrieved_at
                    ? [
                        `${translate('productRetrievedAt')}: ${result.product_information.retrieved_at}`,
                      ]
                    : []),
                  ...(result.product_information.product
                    ? Object.entries(result.product_information.product).map(
                        ([key, value]) =>
                          `${key}: ${Array.isArray(value) ? value.join(', ') : String(value)}`,
                      )
                    : []),
                ]}
              />
            ) : null}
            <Section
              title={translate('richUncertainty')}
              values={[...result.uncertainties, ...result.follow_up_questions]}
            />
            <Section
              title={translate('garmentChangeSummary')}
              values={result.change_summary ? [result.change_summary] : []}
            />
            <Pressable
              accessibilityRole="button"
              onPress={() =>
                router.push({ pathname: '/chat', params: { scanId } })
              }
              style={({ pressed }) => [
                styles.chatButton,
                pressed && styles.buttonPressed,
              ]}
            >
              <View style={styles.buttonContent}>
                <Feather
                  color={colors.background}
                  name="message-circle"
                  size={19}
                />
                <Text style={styles.chatButtonText}>
                  {translate('chatTitle')}
                </Text>
              </View>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ disabled: !garmentId }}
              disabled={!garmentId}
              onPress={() => {
                if (garmentId) router.push(`/garments/${garmentId}`);
              }}
              style={({ pressed }) => [
                styles.historyButton,
                !garmentId && styles.historyButtonDisabled,
                pressed && garmentId && styles.buttonPressed,
              ]}
            >
              <View style={styles.buttonContent}>
                <Feather
                  color={garmentId ? colors.text : colors.muted}
                  name="rotate-ccw"
                  size={18}
                />
                <Text
                  style={[
                    styles.neutralButtonText,
                    !garmentId && styles.neutralButtonTextDisabled,
                  ]}
                >
                  {translate('viewGarmentHistory')}
                </Text>
              </View>
              {!garmentId ? (
                <Text style={styles.historyHint}>
                  {translate('historyUnavailable')}
                </Text>
              ) : null}
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => void requestReview()}
              style={({ pressed }) => [
                styles.reviewButton,
                pressed && styles.buttonPressed,
              ]}
            >
              <View style={styles.buttonContent}>
                <Feather color={colors.text} name="alert-circle" size={18} />
                <Text style={styles.reviewButtonText}>
                  {translate('requestReview')}
                </Text>
              </View>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => void deleteAnalysis()}
              style={({ pressed }) => [
                styles.deleteButton,
                pressed && styles.buttonPressed,
              ]}
            >
              <View style={styles.buttonContent}>
                <Feather color={colors.danger} name="trash-2" size={18} />
                <Text style={styles.deleteButtonText}>
                  {translate('deleteScan')}
                </Text>
              </View>
            </Pressable>
            {lifecycleMessage ? (
              <Text accessibilityLiveRegion="polite">{lifecycleMessage}</Text>
            ) : null}
          </>
        ) : null}
        <Pressable
          accessibilityRole="button"
          onPress={() => router.replace('/scan')}
          style={({ pressed }) => [
            styles.backButton,
            pressed && styles.buttonPressed,
          ]}
        >
          <View style={styles.buttonContent}>
            <Feather color={colors.text} name="arrow-left" size={18} />
            <Text style={styles.neutralButtonText}>
              {translate('backToScan')}
            </Text>
          </View>
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
  backButton: {
    alignItems: 'center',
    backgroundColor: colors.background,
    borderColor: colors.borderStrong,
    borderRadius: radii.medium,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 48,
    padding: spacing.medium,
  },
  buttonPressed: { opacity: 0.86, transform: [{ translateY: 1 }] },
  buttonContent: {
    alignItems: 'center',
    flexDirection: 'column',
    gap: spacing.xsmall,
  },
  chatButton: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: radii.medium,
    justifyContent: 'center',
    minHeight: 52,
    padding: spacing.medium,
  },
  chatButtonText: { color: colors.background, fontSize: 16, fontWeight: '800' },
  deleteButton: {
    alignItems: 'center',
    backgroundColor: colors.dangerSoft,
    borderColor: colors.danger,
    borderRadius: radii.medium,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 48,
    padding: spacing.medium,
  },
  deleteButtonText: { color: colors.danger, fontWeight: '800' },
  historyButton: {
    alignItems: 'center',
    backgroundColor: colors.background,
    borderColor: colors.borderStrong,
    borderRadius: radii.medium,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 48,
    padding: spacing.medium,
  },
  historyButtonDisabled: { borderColor: colors.border, opacity: 0.7 },
  neutralButtonText: { color: colors.text, fontWeight: '800' },
  neutralButtonTextDisabled: { color: colors.muted },
  historyHint: {
    color: colors.muted,
    fontSize: 12,
    marginTop: spacing.xsmall,
    textAlign: 'center',
  },
  reviewButton: {
    alignItems: 'center',
    backgroundColor: colors.accent,
    borderRadius: radii.medium,
    justifyContent: 'center',
    minHeight: 48,
    padding: spacing.medium,
  },
  reviewButtonText: { color: colors.text, fontWeight: '800' },
});
