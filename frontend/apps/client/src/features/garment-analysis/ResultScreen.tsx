import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import { useQuery as useApolloQuery } from '@apollo/client';
import { fetch as expoFetch } from 'expo/fetch';
import Feather from '@expo/vector-icons/Feather';
import { router, useLocalSearchParams } from 'expo-router';
import {
  ActivityIndicator,
  AppState,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
import {
  ResultCompositeDocument,
  RunStreamLifecycle,
  imagePreviewApiV1ScansScanIdImagesImageIdPreviewGet,
  streamRunEvents,
  type FabricAssistApiClient,
  type RunEvent,
} from '@fabricassist/api-client';
import { useSession } from '../../auth/session';
import { FoundationShell } from '../../components/FoundationShell';
import { BackBreadcrumb } from '../../components/BackBreadcrumb';
import { useTranslation } from '../../i18n/TranslationProvider';
import { getApiBaseUrl } from '../../config/environment';
import { friendlyCode } from './friendlyCodes';

function actionText(action: { code: string; maximumTemperatureC?: number | null }, locale: 'en' | 'es'): string {
  const labels: Record<string, [string, string]> = { water_wash: ['Water wash', 'Lavado con agua'], professional_dry_clean: ['Professional dry cleaning', 'Limpieza en seco profesional'], tumble_dry: ['Tumble dry', 'Secado en secadora'], natural_dry: ['Air dry', 'Secado al aire'], iron: ['Iron', 'Planchado'], domestic_detergent: ['Domestic detergent', 'Detergente doméstico'], bleach: ['Bleach', 'Lejía'] };
  const label = labels[action.code]?.[locale === 'es' ? 1 : 0] ?? action.code.replaceAll('_', ' ');
  return action.maximumTemperatureC ? `${label} · ${action.maximumTemperatureC} °C` : label;
}

export default function Result(): ReactNode {
  const { scanId, runId } = useLocalSearchParams<{
    scanId: string;
    runId?: string;
  }>();
  const { apiClient, restWrites, token } = useSession();
  const { locale, translate } = useTranslation();
  const [failed, setFailed] = useState(false);
  const [failureCode, setFailureCode] = useState<string>();
  const [stage, setStage] = useState<string>();
  const [progressPercent, setProgressPercent] = useState(0);
  const [garmentId, setGarmentId] = useState<string>();
  const [lifecycleMessage, setLifecycleMessage] = useState<string>();
  const [streamUnavailable, setStreamUnavailable] = useState(false);
  const [isForeground, setIsForeground] = useState(
    AppState.currentState === 'active',
  );
  const { data, refetch: refetchCanonicalResult } = useApolloQuery(
    ResultCompositeDocument,
    {
      skip: !scanId || !token,
      variables: { scanId, language: locale },
      fetchPolicy: 'network-only',
      notifyOnNetworkStatusChange: true,
      pollInterval: streamUnavailable && runId && isForeground ? 5_000 : 0,
    },
  );
  const composite = data?.scanResult;
  const result = composite?.result?.result;
  const identityCandidates = composite?.identityCandidates ?? [];
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextState) => {
      setIsForeground(nextState === 'active');
    });
    return () => subscription.remove();
  }, []);
  useEffect(() => {
    if (!composite) return;
    setStage(composite.scan.analysisStage ?? composite.scan.status);
    setProgressPercent(composite.scan.progressPercent);
    setGarmentId(composite.scan.garmentId ?? undefined);
    setFailureCode(composite.scan.errorCode ?? undefined);
    setFailed(composite.scan.status === 'failed');
  }, [composite]);
  const confirmIdentityCandidate = async (
    candidateId: string,
  ): Promise<void> => {
    if (!scanId || !token) return;
    const response = await restWrites.confirmIdentity({
      path: { scan_id: scanId },
      body: { candidate_id: candidateId },
    });
    if (response.data) {
      setLifecycleMessage(translate('identityCandidateConfirmed'));
    }
  };
  const rejectIdentityCandidate = async (
    candidateId: string,
  ): Promise<void> => {
    if (!scanId || !token) return;
    const response = await restWrites.rejectIdentity({
      path: { scan_id: scanId },
      body: { candidate_id: candidateId },
    });
    if (response.data) {
      setLifecycleMessage(translate('identityCandidateRejected'));
    }
  };
  const requestReview = async (): Promise<void> => {
    if (!scanId || !token) return;
    const response = await restWrites.submitFeedback({
      path: { scan_id: scanId },
      body: { request_review: true },
    });
    setLifecycleMessage(
      response.data
        ? translate('reviewRequested')
        : translate('reviewRequestFailed'),
    );
  };
  const deleteAnalysis = async (): Promise<void> => {
    if (!scanId || !token) return;
    const response = await restWrites.deleteScan({
      path: { scan_id: scanId },
    });
    if (response.data) {
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
    if (!runId || !token || !scanId) return;
    let lastSequence = 0;
    const lifecycle = new RunStreamLifecycle({
      recover: async () => {
        await refetchCanonicalResult({ scanId, language: locale });
      },
      open: async (signal, lastEventId) => {
        await streamRunEvents(
          `${getApiBaseUrl()}/api/v1/runs/${runId}/events`,
          token,
          (frame) => {
            if (!frame.data || frame.event === 'heartbeat') return;
            try {
              const event = JSON.parse(frame.data) as RunEvent;
              if (event.sequence <= lastSequence) return;
              lastSequence = event.sequence;
              lifecycle.markEventId(frame.id ?? String(event.sequence));
              if (typeof event.data.progress_percent === 'number') {
                setProgressPercent(event.data.progress_percent);
              }
              if (typeof event.data.stage === 'string')
                setStage(event.data.stage);
              if (
                frame.event === 'run.completed' ||
                frame.event === 'run.failed' ||
                frame.event === 'run.cancelled'
              ) {
                lifecycle.stop();
                void refetchCanonicalResult({ scanId, language: locale }).then(
                  () => {
                    if (frame.event === 'run.failed') {
                      setFailureCode(
                        typeof event.data.error_code === 'string'
                          ? event.data.error_code
                          : undefined,
                      );
                      setFailed(true);
                    }
                  },
                );
              }
            } catch {
              // Canonical GraphQL polling remains the recovery path for malformed events.
            }
          },
          signal,
          lastEventId,
          expoFetch,
        );
      },
      onReconnectFailure: (attempt) => {
        if (attempt >= 3) setStreamUnavailable(true);
      },
    });
    const subscription = AppState.addEventListener('change', (nextState) => {
      if (nextState === 'active') lifecycle.resume();
      else lifecycle.pause();
    });
    lifecycle.start();
    return () => {
      lifecycle.stop();
      subscription.remove();
    };
  }, [locale, refetchCanonicalResult, runId, scanId, token]);

  return (
    <FoundationShell
      title={translate('resultTitle')}
      description={translate('resultDescription')}
    >
      <ScrollView contentContainerStyle={styles.content}>
        <BackBreadcrumb label={translate('garmentHistoryTitle')} />
        {!result && !failed ? (
          <View accessibilityLiveRegion="polite" style={styles.loading}>
            <ActivityIndicator color={colors.primary} size="large" />
            <Text style={styles.loadingTitle}>
              {translate('resultLoading')}
            </Text>
            <View style={styles.progressTrack}>
              <View
                style={[styles.progressValue, { width: `${progressPercent}%` }]}
              />
            </View>
            <Text style={styles.loadingCopy}>
              {stage
                ? translate('resultStage').replace('{stage}', stageLabel(stage))
                : translate('resultLoadingCopy')}
            </Text>
          </View>
        ) : null}
        {failed ? (
          <View accessibilityLiveRegion="assertive" style={styles.failure}>
            <Feather color={colors.danger} name="alert-triangle" size={24} />
            <Text style={styles.failureTitle}>
              {translate('analysisFailedTitle')}
            </Text>
            <Text style={styles.failureCopy}>
              {failureCode?.startsWith('PROVIDER_')
                ? translate('analysisProviderFailed')
                : translate('analysisFailed')}
            </Text>
          </View>
        ) : null}
        {result ? (
          <>
            <Text accessibilityRole="header" style={styles.title}>
              {result.category && result.category.toLowerCase() !== 'unknown'
                ? result.category
                : translate('careAnalysis')}
            </Text>
            <Section
              title={translate('richValidation')}
              values={[friendlyCode(result.outcome, translate)]}
            />
            <Section
              title={translate('richWarnings')}
              values={result.warnings.map((value) => friendlyCode(value, translate))}
            />
            <Section
              title={translate('richPreparation')}
              values={result.allowedActions.map((action) => actionText(action, locale))}
            />
            <Section
              title={translate('richStain')}
              values={result.stainSteps.flatMap((step) =>
                step.status === 'accepted' && step.text ? [step.text] : [],
              )}
            />
            <Section
              title={translate('richCleaning')}
              values={result.allowedActions.map((action) => actionText(action, locale))}
            />
            <Section
              title={translate('resultProhibitions')}
              values={result.prohibitedActions.map((action) => actionText(action, locale))}
              warning
            />
            <Section
              title={translate('richDrying')}
              values={result.unknownActions.map((action) => actionText(action, locale))}
            />
            <Section
              title={translate('richIroning')}
              values={result.professionalOnlyActions.map((action) => actionText(action, locale))}
            />
            <Section
              title={translate('richProfessional')}
              values={result.professionalOnlyActions.map((action) => actionText(action, locale))}
            />
            <Section
              title={translate('richSources')}
              values={result.visibleLabelText.map((text) => text.text)}
            />
            <Section
              title={translate('productEvidence')}
              values={[
                result.productBarcode
                  ? `${translate('productBarcode')}: ${result.productBarcode}`
                  : '',
                result.productLookupStatus !== 'not_attempted'
                  ? `${translate('productLookupStatus')}: ${friendlyCode(result.productLookupStatus, translate)}`
                  : '',
                result.productSource
                  ? `${translate('productSource')}: ${result.productSource}`
                  : '',
              ].filter((value): value is string => Boolean(value))}
            />
            <Section
              title={translate('richUncertainty')}
              values={[...result.uncertainties, ...result.clearerImageRequests].map((value) => friendlyCode(value, translate))}
            />
            <Section
              title={translate('garmentChangeSummary')}
              values={result.conflicts.map(
                (conflict) =>
                  `${friendlyCode(conflict.fieldPath, translate)}: ${friendlyCode(conflict.explanationKey, translate)}`,
              )}
            />
            {identityCandidates
              .filter((candidate) => candidate.status === 'pending')
              .map((candidate) => (
                <View key={candidate.id} style={styles.identityCandidate}>
                  <IdentityCandidateThumbnail
                    apiClient={apiClient}
                    imageId={candidate.thumbnailImageId}
                    scanId={candidate.thumbnailScanId}
                    thumbnailLabel={translate('identityCandidateThumbnail')}
                  />
                  <Text style={styles.heading}>
                    {translate(
                      candidate.classification === 'probable_instance'
                        ? 'likelySameGarment'
                        : 'likelySameModel',
                    )}
                  </Text>
                  <Text>
                    {translate(
                      candidate.classification === 'probable_instance'
                        ? 'likelySameGarmentDescription'
                        : 'likelySameModelDescription',
                    )}
                  </Text>
                  <Text style={styles.identityHistory}>
                    {translate(
                      candidate.classification === 'probable_instance'
                        ? 'sameGarmentAnalysedBefore'
                        : 'sameModelAnalysedBefore',
                    )}
                  </Text>
                  <Pressable
                    accessibilityRole="button"
                    onPress={() =>
                      router.push({
                        pathname: `/garments/${candidate.garmentId}`,
                        params: { decisionScanId: scanId },
                      })
                    }
                    style={({ pressed }) => [
                      styles.identityReviewButton,
                      pressed && styles.buttonPressed,
                    ]}
                  >
                    <Text style={styles.neutralButtonText}>
                      {translate('reviewCandidateGarment')}
                    </Text>
                  </Pressable>
                  <Pressable
                    accessibilityRole="button"
                    onPress={() => void confirmIdentityCandidate(candidate.id)}
                    style={({ pressed }) => [
                      styles.identityButton,
                      pressed && styles.buttonPressed,
                    ]}
                  >
                    <Text style={styles.identityButtonText}>
                      {translate('confirmSameGarment')}
                    </Text>
                  </Pressable>
                  <Pressable
                    accessibilityRole="button"
                    onPress={() => void rejectIdentityCandidate(candidate.id)}
                    style={({ pressed }) => [
                      styles.identityRejectButton,
                      pressed && styles.buttonPressed,
                    ]}
                  >
                    <Text style={styles.identityRejectText}>
                      {translate('rejectSameGarment')}
                    </Text>
                  </Pressable>
                </View>
              ))}
            <Pressable
              accessibilityRole="button"
              onPress={() =>
                router.push({ pathname: '/images', params: { scanId } })
              }
              style={({ pressed }) => [
                styles.historyButton,
                pressed && styles.buttonPressed,
              ]}
            >
              <View style={styles.buttonContent}>
                <Feather color={colors.text} name="image" size={18} />
                <Text style={styles.neutralButtonText}>
                  {translate('viewUploadedImages')}
                </Text>
              </View>
            </Pressable>
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

function IdentityCandidateThumbnail({
  apiClient,
  imageId,
  scanId,
  thumbnailLabel,
}: {
  apiClient: FabricAssistApiClient;
  imageId?: string | null;
  scanId?: string | null;
  thumbnailLabel: string;
}): ReactNode {
  const [url, setUrl] = useState<string>();

  useEffect(() => {
    if (!scanId || !imageId) {
      setUrl(undefined);
      return;
    }
    let cancelled = false;
    void imagePreviewApiV1ScansScanIdImagesImageIdPreviewGet({
      client: apiClient,
      path: { scan_id: scanId, image_id: imageId },
    }).then((response) => {
      if (!cancelled) setUrl(response.data?.url);
    });
    return () => {
      cancelled = true;
    };
  }, [apiClient, imageId, scanId]);

  if (!url) return null;
  return (
    <Image
      accessibilityLabel={thumbnailLabel}
      resizeMode="cover"
      source={{ uri: url }}
      style={styles.identityThumbnail}
    />
  );
}

const styles = StyleSheet.create({
  breadcrumb: { alignSelf: 'flex-start', paddingVertical: spacing.xsmall },
  breadcrumbText: { color: colors.primary, fontWeight: '800' },
  content: { gap: spacing.medium },
  title: { fontSize: 22, fontWeight: '800', color: colors.text },
  section: {
    gap: spacing.small,
    padding: spacing.medium,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radii.medium,
  },
  identityCandidate: {
    backgroundColor: colors.primarySoft,
    borderRadius: radii.medium,
    gap: spacing.small,
    padding: spacing.medium,
  },
  identityThumbnail: {
    backgroundColor: colors.background,
    borderRadius: radii.small,
    height: 150,
    width: '100%',
  },
  identityButton: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: radii.small,
    minHeight: 46,
    paddingVertical: spacing.small,
    width: '100%',
  },
  identityReviewButton: {
    alignItems: 'center',
    borderColor: colors.borderStrong,
    borderRadius: radii.small,
    borderWidth: 1,
    minHeight: 44,
    paddingVertical: spacing.small,
    width: '100%',
  },
  identityRejectButton: {
    alignItems: 'center',
    backgroundColor: colors.background,
    borderColor: colors.danger,
    borderRadius: radii.small,
    borderWidth: 1,
    minHeight: 44,
    paddingVertical: spacing.small,
    width: '100%',
  },
  identityRejectText: { color: colors.danger, fontWeight: '800' },
  identityButtonText: { color: colors.background, fontWeight: '800' },
  identityHistory: { color: colors.muted, fontWeight: '700' },
  warning: { backgroundColor: colors.dangerSoft },
  failure: {
    alignItems: 'center',
    backgroundColor: colors.dangerSoft,
    borderRadius: radii.medium,
    gap: spacing.small,
    padding: spacing.large,
  },
  failureTitle: { color: colors.danger, fontSize: 18, fontWeight: '800' },
  failureCopy: { color: colors.text, textAlign: 'center' },
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
