import type { ReactNode } from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { spacing } from '@fabricassist/design-tokens';
import { useSession } from '../../auth/session';
import { FoundationShell } from '../../components/FoundationShell';
import { getApiBaseUrl } from '../../config/environment';
import { useTranslation } from '../../i18n/TranslationProvider';

type Review = { id: string; status: string };
type ReviewDetail = Review & {
  dossier: Record<string, unknown>;
  proposal: Record<string, unknown>;
  validation: Record<string, unknown>;
};

export default function ReviewQueue(): ReactNode {
  const { token } = useSession();
  const { translate } = useTranslation();
  const [items, setItems] = useState<Review[]>([]);
  const [selected, setSelected] = useState<ReviewDetail>();
  const [reason, setReason] = useState('');
  const [dossier, setDossier] = useState('');
  const [failed, setFailed] = useState(false);
  const headers = useMemo(
    () => ({
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    }),
    [token],
  );
  const load = useCallback(async (): Promise<void> => {
    if (!token) return;
    const response = await fetch(`${getApiBaseUrl()}/api/v1/reviews`, {
      headers,
    });
    if (!response.ok) {
      setFailed(true);
      return;
    }
    setItems((await response.json()) as Review[]);
  }, [headers, token]);
  useEffect(() => {
    void load();
  }, [load]);
  const selectCase = async (id: string): Promise<void> => {
    const claim = await fetch(
      `${getApiBaseUrl()}/api/v1/reviews/${id}/assign`,
      { method: 'POST', headers },
    );
    const detail = await fetch(`${getApiBaseUrl()}/api/v1/reviews/${id}`, {
      headers,
    });
    if (!claim.ok || !detail.ok) {
      setFailed(true);
      return;
    }
    const value = (await detail.json()) as ReviewDetail;
    setSelected(value);
    setDossier(JSON.stringify(value.dossier, null, 2));
    setReason('');
  };
  const correct = async (): Promise<void> => {
    if (!selected) return;
    try {
      const corrected = JSON.parse(dossier) as Record<string, unknown>;
      const response = await fetch(
        `${getApiBaseUrl()}/api/v1/reviews/${selected.id}/corrections`,
        {
          method: 'POST',
          headers,
          body: JSON.stringify({ dossier: corrected, reason }),
        },
      );
      if (!response.ok) throw new Error();
      await load();
    } catch {
      setFailed(true);
    }
  };
  const approve = async (): Promise<void> => {
    if (!selected) return;
    const response = await fetch(
      `${getApiBaseUrl()}/api/v1/reviews/${selected.id}/approve`,
      { method: 'POST', headers, body: '{}' },
    );
    if (!response.ok) {
      setFailed(true);
      return;
    }
    await load();
  };
  const confirmCompleted = async (): Promise<void> => {
    if (!selected) return;
    const response = await fetch(
      `${getApiBaseUrl()}/api/v1/reviews/${selected.id}/service-events`,
      { method: 'POST', headers, body: JSON.stringify({ kind: 'completed' }) },
    );
    if (!response.ok) setFailed(true);
  };
  return (
    <FoundationShell
      title={translate('reviewQueueTitle')}
      description={translate('reviewQueueDescription')}
    >
      <ScrollView contentContainerStyle={styles.content}>
        {failed ? (
          <Text accessibilityLiveRegion="polite">
            {translate('reviewActionFailed')}
          </Text>
        ) : null}
        {items.length === 0 ? <Text>{translate('reviewEmpty')}</Text> : null}
        {items.map((item) => (
          <Pressable
            key={item.id}
            accessibilityRole="button"
            onPress={() => void selectCase(item.id)}
            style={styles.button}
          >
            <Text>
              {translate('reviewAssign')} · {item.status}
            </Text>
          </Pressable>
        ))}
        {selected ? (
          <View style={styles.detail}>
            <Text>{JSON.stringify(selected.validation)}</Text>
            <Text>{JSON.stringify(selected.proposal)}</Text>
            <Text>{translate('reviewCorrection')}</Text>
            <TextInput
              accessibilityLabel={translate('reviewCorrection')}
              multiline
              value={dossier}
              onChangeText={setDossier}
              style={styles.input}
            />
            <TextInput
              accessibilityLabel={translate('reviewReason')}
              value={reason}
              onChangeText={setReason}
              style={styles.input}
            />
            <Pressable
              accessibilityRole="button"
              onPress={() => void correct()}
              style={styles.button}
            >
              <Text>{translate('reviewSubmitCorrection')}</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => void approve()}
              style={styles.button}
            >
              <Text>{translate('reviewApprove')}</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => void confirmCompleted()}
              style={styles.button}
            >
              <Text>{translate('reviewServiceComplete')}</Text>
            </Pressable>
          </View>
        ) : null}
      </ScrollView>
    </FoundationShell>
  );
}
const styles = StyleSheet.create({
  content: { gap: spacing.medium },
  detail: { gap: spacing.small },
  button: { padding: spacing.medium },
  input: { borderWidth: 1, minHeight: 48, padding: spacing.small },
});
