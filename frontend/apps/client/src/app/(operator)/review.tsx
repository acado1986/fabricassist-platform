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
  type GarmentEvidenceDossier,
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
  const [dossier, setDossier] = useState('');
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
    setDossier(JSON.stringify(value.dossier, null, 2));
    setReason('');
  };
  const correct = async (): Promise<void> => {
    if (!selected) return;
    try {
      const corrected = JSON.parse(dossier) as GarmentEvidenceDossier;
      const response = await restWrites.correctReview({
        path: { review_id: selected.id },
        body: { dossier: corrected, reason },
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
