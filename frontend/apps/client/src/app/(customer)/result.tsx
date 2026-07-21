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

type Answer = {
  title: string;
  summary: string;
  actions: string[];
  prohibitions: string[];
  professional_only?: string[];
  detergent?: string;
  uncertainties: string[];
};

export default function Result(): ReactNode {
  const { scanId } = useLocalSearchParams<{ scanId: string }>();
  const { token } = useSession();
  const { locale, translate } = useTranslation();
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!scanId || !token) return;
    void fetch(
      `${getApiBaseUrl()}/api/v1/scans/${scanId}/result?language=${locale}`,
      {
        headers: { Authorization: `Bearer ${token}` },
      },
    )
      .then(async (response) => {
        if (!response.ok) throw new Error('RESULT_UNAVAILABLE');
        return response.json() as Promise<{ answer: Answer }>;
      })
      .then((payload) => setAnswer(payload.answer))
      .catch(() => setFailed(true));
  }, [locale, scanId, token]);

  return (
    <FoundationShell
      title={translate('resultTitle')}
      description={translate('resultDescription')}
    >
      <ScrollView contentContainerStyle={styles.content}>
        {!answer && !failed ? (
          <ActivityIndicator color={colors.primary} />
        ) : null}
        {!answer && !failed ? (
          <Text style={styles.muted}>{translate('resultLoading')}</Text>
        ) : null}
        {failed ? (
          <Text style={styles.error}>{translate('resultUnavailable')}</Text>
        ) : null}
        {answer ? (
          <>
            <Text style={styles.answerTitle}>{answer.title}</Text>
            <Text style={styles.summary}>{answer.summary}</Text>
            <Section
              title={translate('resultActions')}
              values={answer.actions}
            />
            <Section
              title={translate('resultProhibitions')}
              values={answer.prohibitions}
              warning
            />
            <Section
              title={translate('resultProfessional')}
              values={answer.professional_only ?? []}
            />
            <Section
              title={translate('resultDetergent')}
              values={answer.detergent ? [answer.detergent] : []}
            />
            <Section
              title={translate('resultUncertainties')}
              values={answer.uncertainties}
            />
          </>
        ) : null}
        <Pressable
          accessibilityRole="button"
          onPress={() => router.replace('/scan')}
          style={styles.button}
        >
          <Text style={styles.buttonText}>{translate('backToScan')}</Text>
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
  if (values.length === 0) return null;
  return (
    <View style={[styles.section, warning && styles.warning]}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {values.map((value) => (
        <Text key={value} style={styles.value}>
          • {value}
        </Text>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing.medium },
  muted: { color: colors.muted, textAlign: 'center' },
  error: { color: colors.danger, textAlign: 'center' },
  answerTitle: { color: colors.text, fontSize: 20, fontWeight: '800' },
  summary: { color: colors.muted, lineHeight: 21 },
  section: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radii.medium,
    gap: 6,
    padding: spacing.medium,
  },
  warning: { backgroundColor: '#FFF5F3' },
  sectionTitle: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '800',
    textTransform: 'uppercase',
  },
  value: { color: colors.text, lineHeight: 21 },
  button: {
    alignItems: 'center',
    borderColor: colors.primary,
    borderRadius: radii.medium,
    borderWidth: 1,
    minHeight: 50,
    justifyContent: 'center',
  },
  buttonText: { color: colors.primary, fontWeight: '800' },
});
