import type { ReactNode } from 'react';
import { useCallback, useEffect, useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { spacing } from '@fabricassist/design-tokens';
import {
  listReviewsApiV1ReviewsGet,
  reviewDetailApiV1ReviewsReviewIdGet,
  type ReviewDetail,
  type ReviewResponse,
} from '@fabricassist/api-client';
import { useSession } from '../../auth/session';
import { FoundationShell } from '../../components/FoundationShell';
import { useTranslation } from '../../i18n/TranslationProvider';

export default function ReviewQueue(): ReactNode {
  const { apiClient, restWrites, token } = useSession();
  const { translate } = useTranslation();
  const [items, setItems] = useState<ReviewResponse[]>([]);
  const [selected, setSelected] = useState<ReviewDetail>();
  const [reason, setReason] = useState('');
  const [fieldPath, setFieldPath] = useState('');
  const [correctedValue, setCorrectedValue] = useState('');
  const [failed, setFailed] = useState(false);
  const load = useCallback(async (): Promise<void> => {
    if (!token) return;
    const response = await listReviewsApiV1ReviewsGet({
      client: apiClient,
    });
    if (!response.data) {
      setFailed(true);
      return;
    }
    setItems(response.data);
  }, [apiClient, token]);
  useEffect(() => {
    void load();
  }, [load]);
  const selectCase = async (id: string): Promise<void> => {
    const claim = await restWrites.assignReview({
      path: { review_id: id },
    });
    const detail = await reviewDetailApiV1ReviewsReviewIdGet({
      client: apiClient,
      path: { review_id: id },
    });
    if (!claim.data || !detail.data) {
      setFailed(true);
      return;
    }
    const value = detail.data;
    setSelected(value);
    setFieldPath('');
    setCorrectedValue('');
    setReason('');
  };
  const correct = async (): Promise<void> => {
    if (!selected) return;
    try {
      const response = await restWrites.correctReview({
        path: { review_id: selected.id },
        body: {
          field_path: fieldPath,
          corrected_value: JSON.parse(correctedValue),
          reason,
        },
      });
      if (!response.data) throw new Error();
      await load();
    } catch {
      setFailed(true);
    }
  };
  const approve = async (): Promise<void> => {
    if (!selected) return;
    const response = await restWrites.approveReview({
      path: { review_id: selected.id },
      body: {},
    });
    if (!response.data) {
      setFailed(true);
      return;
    }
    await load();
  };
  const confirmCompleted = async (): Promise<void> => {
    if (!selected) return;
    const response = await restWrites.confirmServiceEvent({
      path: { review_id: selected.id },
      body: { kind: 'completed' },
    });
    if (!response.data) setFailed(true);
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
              value={fieldPath}
              onChangeText={setFieldPath}
              placeholder="care.wash.permission"
              style={styles.input}
            />
            <TextInput
              accessibilityLabel="Corrected JSON value"
              value={correctedValue}
              onChangeText={setCorrectedValue}
              placeholder='"prohibited"'
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
