import { type ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import Feather from '@expo/vector-icons/Feather';
import { useQuery } from '@apollo/client';
import { router, useLocalSearchParams } from 'expo-router';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
import { GarmentDetailDocument } from '@fabricassist/api-client';
import { useSession } from '../../../auth/session';
import { FoundationShell } from '../../../components/FoundationShell';
import { useTranslation } from '../../../i18n/TranslationProvider';
import { friendlyCode } from '../../../features/garment-analysis/friendlyCodes';

type Group = { authority: string; values: string[]; title: string; icon: keyof typeof Feather.glyphMap };

export default function FinalResultPage(): ReactNode {
  const { garmentId } = useLocalSearchParams<{ garmentId: string }>();
  const { token } = useSession();
  const { locale, translate } = useTranslation();
  const { data, loading, error } = useQuery(GarmentDetailDocument, {
    skip: !token || !garmentId,
    variables: { garmentId, first: 20, after: null, language: locale },
  });
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
    addGroup(groups, 'validation', translate('richValidation'), [friendlyCode(active.outcome, translate)], 'check-circle');
    addGroup(groups, 'prohibited', translate('resultProhibitions'), active.prohibitedActions.map(action => actionText(action, (key) => translate(key as never))), 'slash');
    addGroup(groups, 'allowed', translate('richCleaning'), active.allowedActions.map(action => actionText(action, (key) => translate(key as never))), 'check');
    addGroup(groups, 'unknown', translate('richDrying'), active.unknownActions.map(action => actionText(action, (key) => translate(key as never))), 'help-circle');
    addGroup(groups, 'professional', translate('richProfessional'), active.professionalOnlyActions.map(action => actionText(action, (key) => translate(key as never))), 'briefcase');
    addGroup(groups, 'warnings', translate('richWarnings'), active.warnings.map(value => friendlyCode(value, translate)), 'alert-triangle');
    addGroup(groups, 'clearerImage', translate('richUncertainty'), active.clearerImageRequests.map(value => friendlyCode(value, translate)), 'image');
    addGroup(groups, 'uncertainty', translate('richUncertainty'), active.uncertainties.map(value => friendlyCode(value, translate)), 'help-circle');
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

function careGroup(code: string): string { if (code.includes('wash')) return 'washing'; if (code.includes('dry')) return 'drying'; if (code.includes('iron')) return 'ironing'; if (code.includes('bleach')) return 'bleaching'; if (code.includes('clean')) return 'professionalCleaning'; return 'otherCare'; }
function careTitle(code: string): string { const group = careGroup(code); return ({ washing: 'finalResultWashing', drying: 'finalResultDrying', ironing: 'finalResultIroning', bleaching: 'finalResultBleaching', professionalCleaning: 'finalResultProfessionalCleaning', otherCare: 'finalResultOtherCare' } as Record<string, string>)[group] ?? 'finalResultOtherCare'; }
function careIcon(group: string): keyof typeof Feather.glyphMap { return ({ washing: 'droplet', drying: 'wind', ironing: 'square', bleaching: 'alert-triangle', professionalCleaning: 'briefcase', otherCare: 'info' } as Record<string, keyof typeof Feather.glyphMap>)[group] ?? 'info'; }
function groupOrder(group: string): number { return ({ validation: 1, warnings: 2, washing: 3, allowed: 4, bleaching: 5, drying: 6, ironing: 7, unknown: 8, professional: 9, professionalCleaning: 10, prohibited: 11, uncertainty: 12, clearerImage: 13, otherCare: 14 } as Record<string, number>)[group] ?? 15; }

const styles = StyleSheet.create({ content: { gap: spacing.medium }, back: { color: colors.primary, fontWeight: '700' }, intro: { alignItems: 'center', backgroundColor: colors.primary, borderRadius: radii.large, flexDirection: 'row', gap: spacing.medium, padding: spacing.large }, badge: { color: colors.background, fontSize: 28, fontWeight: '800' }, introCopy: { flex: 1, gap: spacing.xsmall }, heading: { color: colors.background, fontSize: 20, fontWeight: '800' }, introText: { color: colors.background, lineHeight: 20 }, card: { backgroundColor: colors.surfaceMuted, borderRadius: radii.medium, gap: spacing.small, padding: spacing.medium }, cardHeader: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between', gap: spacing.small }, titleRow: { alignItems: 'center', flex: 1, flexDirection: 'row', gap: spacing.small }, icon: { alignItems: 'center', backgroundColor: colors.background, borderRadius: radii.small, height: 34, justifyContent: 'center', width: 34 }, title: { color: colors.text, flex: 1, fontWeight: '800' }, source: { color: colors.muted, fontSize: 12 }, valueRow: { alignItems: 'flex-start', flexDirection: 'row', gap: spacing.small }, value: { color: colors.text, flex: 1, lineHeight: 21 }, muted: { color: colors.muted }, error: { color: colors.danger } });
