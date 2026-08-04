import { useEffect, useState, type ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import Feather from '@expo/vector-icons/Feather';
import { useQuery } from '@apollo/client';
import { router, useLocalSearchParams } from 'expo-router';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
import { GarmentDetailDocument, scanResultApiV1ScansScanIdResultGet } from '@fabricassist/api-client';
import { useSession } from '../../../auth/session';
import { FoundationShell } from '../../../components/FoundationShell';
import { useTranslation } from '../../../i18n/TranslationProvider';
import { friendlyCode } from '../../../features/garment-analysis/friendlyCodes';
import type { TranslationKey } from '@fabricassist/translations';

type Group = { authority: string; values: string[]; title: string; icon: keyof typeof Feather.glyphMap };

export default function FinalResultPage(): ReactNode {
  const { garmentId } = useLocalSearchParams<{ garmentId: string }>();
  const { token } = useSession();
  const { apiClient } = useSession();
  const { locale, translate } = useTranslation();
  const { data, loading, error } = useQuery(GarmentDetailDocument, {
    skip: !token || !garmentId,
    variables: { garmentId, first: 20, after: null, language: locale },
  });
  const [historicalResults, setHistoricalResults] = useState<Record<string, unknown>[]>([]);
  const analyses = data?.garmentDetail?.analyses?.items ?? [];
  const analysisIds = analyses.filter(item => item.resultAvailable).map(item => item.scanId).join(',');
  useEffect(() => {
    let cancelled = false;
    void Promise.all(analyses.filter(item => item.resultAvailable).map(async item => {
      const response = await scanResultApiV1ScansScanIdResultGet({ client: apiClient, path: { scan_id: item.scanId } });
      return (response.data?.result ?? null) as Record<string, unknown> | null;
    })).then(results => { if (!cancelled) setHistoricalResults(results.filter((result): result is Record<string, unknown> => result !== null)); });
    return () => { cancelled = true; };
  }, [analysisIds, apiClient]);
  const groups = (data?.garmentDetail?.observations ?? []).reduce<Record<string, Group>>((result, item) => {
    const rawValue = (item.value ?? {}) as Record<string, unknown>;
    const value = formatValue(rawValue, (key) => translate(key as never));
    if (!value) return result;
    const groupKey = item.observationType === 'care' ? careGroup(String(rawValue.code ?? '')) : item.observationType;
    const group = result[groupKey] ?? { authority: item.authority, values: [], title: item.observationType === 'care' ? translate(careTitle(rawValue.code as string) as never) : friendlyCode(item.observationType, translate), icon: careIcon(groupKey) };
    if (!group.values.includes(value)) group.values.push(value);
    result[item.observationType] = group;
    return result;
  }, {});
  // The active validated result is the complete merged analysis. Observations alone
  // only contain extracted evidence, so they cannot represent all care actions.
  const active = data?.garmentDetail?.activeResult?.result;
  if (active) {
    addGroup(groups, 'overview', translate('finalResultOverview'), [
      active.category && active.category.toLowerCase() !== 'unknown' ? friendlyCode(active.category, translate) : '',
      active.overallCondition && active.overallCondition.toLowerCase() !== 'unknown' ? friendlyCode(active.overallCondition, translate) : '',
    ], 'clipboard');
    addGroup(groups, 'validation', translate('richValidation'), [friendlyCode(active.outcome, translate)], 'check-circle');
    addGroup(groups, 'prohibited', translate('resultProhibitions'), (active.prohibitedActions ?? []).map(action => actionText(action, (key) => translate(key as never))), 'slash');
    addGroup(groups, 'allowed', translate('richCleaning'), (active.allowedActions ?? []).map(action => actionText(action, (key) => translate(key as never))), 'check');
    addGroup(groups, 'unknown', translate('richDrying'), (active.unknownActions ?? []).map(action => actionText(action, (key) => translate(key as never))), 'help-circle');
    addGroup(groups, 'professional', translate('richProfessional'), (active.professionalOnlyActions ?? []).map(action => actionText(action, (key) => translate(key as never))), 'briefcase');
    addGroup(groups, 'warnings', translate('richWarnings'), (active.warnings ?? []).map(value => friendlyCode(value, translate)), 'alert-triangle');
    addGroup(groups, 'clearerImage', translate('richUncertainty'), (active.clearerImageRequests ?? []).map(value => friendlyCode(value, translate)), 'image');
    addGroup(groups, 'uncertainty', translate('richUncertainty'), (active.uncertainties ?? []).map(value => friendlyCode(value, translate)), 'help-circle');
  }
  for (const result of historicalResults) {
    addActionGroup(groups, result, 'warnings', 'richWarnings', 'alert-triangle', translate);
    addActionGroup(groups, result, 'allowedActions', 'richCleaning', 'check', translate);
    addActionGroup(groups, result, 'prohibitedActions', 'resultProhibitions', 'slash', translate);
    addActionGroup(groups, result, 'unknownActions', 'richDrying', 'help-circle', translate);
    addActionGroup(groups, result, 'professionalOnlyActions', 'richProfessional', 'briefcase', translate);
    addStringGroup(groups, result, 'uncertainties', 'uncertainty', 'richUncertainty', 'help-circle', translate);
  }

  return <FoundationShell title={translate('finalResultAnalysis')} description={translate('finalResultAnalysisDescription')}>
    <ScrollView contentContainerStyle={styles.content}>
      <Pressable onPress={() => router.back()}><Text style={styles.back}>‹ {translate('garmentHistoryTitle')}</Text></Pressable>
      <View style={styles.intro}><Text style={styles.badge}>✓</Text><View style={styles.introCopy}><Text style={styles.heading}>{translate('verifiedCareSummary')}</Text><Text style={styles.introText}>{translate('verifiedCareSummaryDescription')}</Text></View></View>
      {loading ? <Text style={styles.muted}>{translate('resultLoading')}</Text> : null}
      {error ? <Text style={styles.error}>{translate('scanHistoryLoadFailed')}</Text> : null}
      {!loading && !error && Object.keys(groups).length === 0 ? <Text style={styles.muted}>{translate('finalResultEmpty')}</Text> : null}
      {Object.entries(groups).sort(([a], [b]) => groupOrder(a) - groupOrder(b)).map(([type, group]) => <View key={type} style={styles.card}><View style={styles.cardHeader}><View style={styles.titleRow}><View style={styles.icon}><Feather color={colors.primary} name={group.icon} size={18} /></View><Text style={styles.title}>{group.title}</Text></View><Text style={styles.source}>{friendlyCode(group.authority, translate)}</Text></View>{group.values.map(value => <View key={value} style={styles.valueRow}><Feather color={colors.success} name="check" size={16} /><Text style={styles.value}>{value}</Text></View>)}</View>)}
    </ScrollView>
  </FoundationShell>;
}

function formatValue(value: Record<string, unknown>, translate: (key: string) => string): string {
  return Object.entries(value).filter(([key, item]) => !['code', 'reason_key', 'evidence_paths', 'professional_only'].includes(key) && item !== null && item !== undefined && item !== '' && item !== 'unknown')
    .map(([key, item]) => `${friendlyCode(key, translate)}: ${typeof item === 'string' ? friendlyCode(item, translate) : String(item)}`).join(' · ');
}

function actionText(action: { code: string; permission: string; maximumTemperatureC?: number | null }, translate: (key: string) => string): string {
  const parts = [friendlyCode(action.code, translate)];
  if (action.permission && action.permission !== 'unknown') parts.push(friendlyCode(action.permission, translate));
  if (action.maximumTemperatureC !== null && action.maximumTemperatureC !== undefined) parts.push(`${action.maximumTemperatureC} °C`);
  return parts.join(' · ');
}

function addGroup(groups: Record<string, Group>, key: string, title: string, values: string[], icon: keyof typeof Feather.glyphMap): void {
  const clean = values.filter(Boolean);
  if (!clean.length) return;
  const group = groups[key] ?? { authority: '', title, values: [], icon };
  group.values = [...new Set([...group.values, ...clean])];
  groups[key] = group;
}
function addActionGroup(groups: Record<string, Group>, result: Record<string, unknown>, field: string, titleKey: string, icon: keyof typeof Feather.glyphMap, translate: (key: TranslationKey) => string): void {
  const actions = Array.isArray(result[field]) ? result[field] as Array<Record<string, unknown>> : [];
  addGroup(groups, field, translate(titleKey as never), actions.map(action => actionText({ code: String(action.code ?? ''), permission: String(action.permission ?? ''), maximumTemperatureC: typeof action.maximumTemperatureC === 'number' ? action.maximumTemperatureC : null }, key => translate(key as never))), icon);
}
function addStringGroup(groups: Record<string, Group>, result: Record<string, unknown>, field: string, key: string, titleKey: string, icon: keyof typeof Feather.glyphMap, translate: (key: TranslationKey) => string): void {
  const values = Array.isArray(result[field]) ? result[field].filter((value): value is string => typeof value === 'string').map(value => friendlyCode(value, translate)) : [];
  addGroup(groups, key, translate(titleKey as never), values, icon);
}

function careGroup(code: string): string { if (code.includes('wash')) return 'washing'; if (code.includes('dry')) return 'drying'; if (code.includes('iron')) return 'ironing'; if (code.includes('bleach')) return 'bleaching'; if (code.includes('clean')) return 'professionalCleaning'; return 'otherCare'; }
function careTitle(code: string): string { const group = careGroup(code); return ({ washing: 'finalResultWashing', drying: 'finalResultDrying', ironing: 'finalResultIroning', bleaching: 'finalResultBleaching', professionalCleaning: 'finalResultProfessionalCleaning', otherCare: 'finalResultOtherCare' } as Record<string, string>)[group] ?? 'finalResultOtherCare'; }
function careIcon(group: string): keyof typeof Feather.glyphMap { return ({ washing: 'droplet', drying: 'wind', ironing: 'square', bleaching: 'alert-triangle', professionalCleaning: 'briefcase', otherCare: 'info' } as Record<string, keyof typeof Feather.glyphMap>)[group] ?? 'info'; }
function groupOrder(group: string): number { return ({ overview: 1, validation: 2, warnings: 3, washing: 4, allowed: 5, bleaching: 6, drying: 7, ironing: 8, unknown: 9, professional: 10, professionalCleaning: 11, prohibited: 12, uncertainty: 13, clearerImage: 14, otherCare: 15 } as Record<string, number>)[group] ?? 16; }

const styles = StyleSheet.create({ content: { gap: spacing.medium }, back: { color: colors.primary, fontWeight: '700' }, intro: { alignItems: 'center', backgroundColor: colors.primary, borderRadius: radii.large, flexDirection: 'row', gap: spacing.medium, padding: spacing.large }, badge: { color: colors.background, fontSize: 28, fontWeight: '800' }, introCopy: { flex: 1, gap: spacing.xsmall }, heading: { color: colors.background, fontSize: 20, fontWeight: '800' }, introText: { color: colors.background, lineHeight: 20 }, card: { backgroundColor: colors.surfaceMuted, borderRadius: radii.medium, gap: spacing.small, padding: spacing.medium }, cardHeader: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between', gap: spacing.small }, titleRow: { alignItems: 'center', flex: 1, flexDirection: 'row', gap: spacing.small }, icon: { alignItems: 'center', backgroundColor: colors.background, borderRadius: radii.small, height: 34, justifyContent: 'center', width: 34 }, title: { color: colors.text, flex: 1, fontWeight: '800' }, source: { color: colors.muted, fontSize: 12 }, valueRow: { alignItems: 'flex-start', flexDirection: 'row', gap: spacing.small }, value: { color: colors.text, flex: 1, lineHeight: 21 }, muted: { color: colors.muted }, error: { color: colors.danger } });
