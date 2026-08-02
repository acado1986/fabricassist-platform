import type { ReactNode } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { fetch as expoFetch } from 'expo/fetch';
import Feather from '@expo/vector-icons/Feather';
import { useLocalSearchParams } from 'expo-router';
import {
  AppState,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
import {
  RunStreamLifecycle,
  ScanMessagesDocument,
  parseRunEvent,
  streamRunEvents,
} from '@fabricassist/api-client';
import { useMutation } from '@tanstack/react-query';
import { useQuery as useApolloQuery } from '@apollo/client';
import { useSession } from '../../auth/session';
import { FoundationShell } from '../../components/FoundationShell';
import { useTranslation } from '../../i18n/TranslationProvider';
import { getApiBaseUrl } from '../../config/environment';

type StreamedMessage = {
  text: string;
  createdAt: string;
};

type DisplayMessage = {
  id: string;
  role: string;
  status: string;
  text: string;
  createdAt: string;
};

function newIdempotencyKey(): string {
  // `crypto.randomUUID()` is not available in every Android/Hermes runtime.
  // This only de-duplicates an accidental resend; it is not a security token.
  return `chat-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

export default function Chat(): ReactNode {
  const { scanId } = useLocalSearchParams<{ scanId: string }>();
  const { restWrites, token } = useSession();
  const { translate } = useTranslation();
  const [text, setText] = useState('');
  const [sendError, setSendError] = useState<string | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [activeRunIds, setActiveRunIds] = useState<string[]>([]);
  const [streamedMessages, setStreamedMessages] = useState<
    Record<string, StreamedMessage>
  >({});
  const lifecycles = useRef(new Map<string, RunStreamLifecycle>());
  const lifecycleScanId = useRef(scanId);
  const {
    data,
    error: messagesError,
    refetch: refreshMessages,
  } = useApolloQuery(ScanMessagesDocument, {
    skip: !scanId || !token,
    variables: { scanId, first: 100, after: null },
    fetchPolicy: 'cache-and-network',
    notifyOnNetworkStatusChange: true,
  });
  const messageItems = data?.messages.items;
  const messages = useMemo(() => messageItems ?? [], [messageItems]);

  useEffect(() => {
    if (lifecycleScanId.current === scanId) return;
    for (const lifecycle of lifecycles.current.values()) lifecycle.stop();
    lifecycles.current.clear();
    setActiveRunIds([]);
    setStreamedMessages({});
    setStreamError(null);
    setSendError(null);
  }, [scanId]);

  useEffect(() => {
    const discoveredRunIds = messages
      .filter(
        (message) =>
          Boolean(message.runId) &&
          (message.status === 'queued' || message.status === 'processing'),
      )
      .map((message) => message.runId as string);
    if (discoveredRunIds.length === 0) return;
    setActiveRunIds((current) => {
      const additions = discoveredRunIds.filter((id) => !current.includes(id));
      return additions.length === 0 ? current : [...current, ...additions];
    });
  }, [messages]);

  useEffect(() => {
    if (!scanId || !token) return;
    if (lifecycleScanId.current !== scanId) {
      lifecycleScanId.current = scanId;
      return;
    }
    const wanted = new Set(activeRunIds);
    for (const runId of wanted) {
      if (lifecycles.current.has(runId)) continue;
      let lastSequence = 0;
      let lifecycle: RunStreamLifecycle;
      lifecycle = new RunStreamLifecycle({
        recover: async () => {
          await refreshMessages();
        },
        onTerminal: async () => {
          try {
            await refreshMessages();
          } catch {
            setStreamError(translate('chatResponseFailed'));
          } finally {
            setActiveRunIds((current) => current.filter((id) => id !== runId));
          }
        },
        open: async (signal, lastEventId) => {
          await streamRunEvents(
            `${getApiBaseUrl()}/api/v1/runs/${runId}/events`,
            token,
            (frame) => {
              if (lifecycleScanId.current !== scanId) return;
              if (!frame.data || frame.event === 'heartbeat') return;
              const event = parseRunEvent(frame.data);
              if (!event || event.run_id !== runId) return;
              if (event.sequence <= lastSequence) return;
              lastSequence = event.sequence;
              lifecycle.markEventId(frame.id ?? String(event.sequence));

              if (frame.event === 'message.delta') {
                const messageId = event.data.message_id;
                const delta = event.data.delta;
                if (typeof messageId !== 'string' || typeof delta !== 'string')
                  return;
                setStreamedMessages((current) => ({
                  ...current,
                  [messageId]: {
                    createdAt: current[messageId]?.createdAt ?? event.timestamp,
                    text: `${current[messageId]?.text ?? ''}${delta}`,
                  },
                }));
              }
              if (
                frame.event === 'run.failed' ||
                frame.event === 'run.cancelled'
              ) {
                setStreamError(translate('chatResponseFailed'));
              }
              if (
                frame.event === 'run.completed' ||
                frame.event === 'run.failed' ||
                frame.event === 'run.cancelled'
              ) {
                void lifecycle.handleTerminal();
              }
            },
            signal,
            lastEventId,
            expoFetch,
          );
        },
        onReconnectFailure: (attempt) => {
          if (attempt >= 3) setStreamError(translate('chatResponseFailed'));
        },
      });
      lifecycles.current.set(runId, lifecycle);
      lifecycle.start();
    }
    for (const [runId, lifecycle] of lifecycles.current) {
      if (wanted.has(runId)) continue;
      lifecycle.stop();
      lifecycles.current.delete(runId);
    }
  }, [activeRunIds, refreshMessages, scanId, token, translate]);

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (state) => {
      for (const lifecycle of lifecycles.current.values()) {
        if (state === 'active') lifecycle.resume();
        else lifecycle.pause();
      }
    });
    return () => subscription.remove();
  }, []);

  useEffect(
    () => () => {
      for (const lifecycle of lifecycles.current.values()) lifecycle.stop();
      lifecycles.current.clear();
    },
    [scanId, token],
  );

  const canonicalIds = new Set(messages.map((message) => message.id));
  const displayMessages: DisplayMessage[] = [
    ...messages.map((message) => ({
      id: message.id,
      role: message.role,
      status: message.status,
      text: message.text,
      createdAt: message.createdAt,
    })),
    ...Object.entries(streamedMessages)
      .filter(([messageId]) => !canonicalIds.has(messageId))
      .map(([id, message]) => ({
        id,
        role: 'assistant',
        status: 'processing',
        text: message.text,
        createdAt: message.createdAt,
      })),
  ].sort(
    (left, right) =>
      left.createdAt.localeCompare(right.createdAt) ||
      left.id.localeCompare(right.id),
  );

  const postMessage = useMutation({
    mutationFn: async (messageText: string) => {
      const result = await restWrites.postMessage({
        path: { scan_id: scanId },
        headers: { 'Idempotency-Key': newIdempotencyKey() },
        body: { text: messageText },
      });
      if (!result.data) throw new Error('CHAT_MESSAGE_FAILED');
      return result.data;
    },
    onSuccess: async (result) => {
      setSendError(null);
      setStreamError(null);
      setText('');
      if (result.run_id) {
        setActiveRunIds((current) =>
          current.includes(result.run_id as string)
            ? current
            : [...current, result.run_id as string],
        );
      }
      // Refresh immediately so the accepted user message appears while the
      // durable run stream delivers the assistant response.
      await refreshMessages();
    },
    onError: () => setSendError(translate('chatSendFailed')),
  });
  const canSend = Boolean(text.trim() && token && !postMessage.isPending);
  const send = async (): Promise<void> => {
    if (!text.trim() || !token) return;
    try {
      await postMessage.mutateAsync(text.trim());
    } catch {
      // The mutation's shared error handler renders localized feedback.
    }
  };
  return (
    <FoundationShell
      title={translate('chatTitle')}
      description={translate('chatQueued')}
    >
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.messageList}>
          {displayMessages.map((message) => (
            <View
              key={message.id}
              style={[
                styles.messageRow,
                message.role === 'user' ? styles.userRow : styles.assistantRow,
              ]}
            >
              <View
                style={[
                  styles.messageBubble,
                  message.role === 'user'
                    ? styles.userBubble
                    : styles.assistantBubble,
                ]}
              >
                <Text
                  style={[
                    styles.messageAuthor,
                    message.role === 'user'
                      ? styles.userText
                      : styles.assistantAuthor,
                  ]}
                >
                  {message.role === 'user'
                    ? translate('chatUser')
                    : translate('chatAssistant')}
                </Text>
                <Text
                  style={[
                    styles.messageText,
                    message.role === 'user'
                      ? styles.userText
                      : styles.assistantText,
                  ]}
                >
                  {message.text}
                </Text>
                {message.status === 'queued' ||
                message.status === 'processing' ? (
                  <Text style={styles.pendingText}>
                    {translate('chatQueued')}
                  </Text>
                ) : null}
              </View>
            </View>
          ))}
        </View>
        {messagesError ? (
          <Text accessibilityRole="alert" style={styles.errorText}>
            {translate('chatMessagesUnavailable')}
          </Text>
        ) : null}
        {sendError ? (
          <Text accessibilityRole="alert" style={styles.errorText}>
            {sendError}
          </Text>
        ) : null}
        {streamError ? (
          <Text accessibilityRole="alert" style={styles.errorText}>
            {streamError}
          </Text>
        ) : null}
        <View style={styles.composer}>
          <TextInput
            accessibilityLabel={translate('chatPlaceholder')}
            multiline
            onChangeText={setText}
            placeholder={translate('chatPlaceholder')}
            placeholderTextColor={colors.muted}
            style={styles.input}
            value={text}
          />
          <Pressable
            accessibilityLabel={translate('chatSend')}
            accessibilityRole="button"
            accessibilityState={{ disabled: !canSend }}
            disabled={!canSend}
            onPress={send}
            style={({ pressed }) => [
              styles.sendButton,
              !canSend && styles.sendButtonDisabled,
              pressed && canSend && styles.sendButtonPressed,
            ]}
          >
            <Feather color={colors.background} name="send" size={18} />
          </Pressable>
        </View>
      </ScrollView>
    </FoundationShell>
  );
}

const styles = StyleSheet.create({
  assistantAuthor: { color: colors.primary },
  assistantBubble: {
    backgroundColor: colors.surfaceMuted,
    borderTopLeftRadius: radii.small,
  },
  assistantRow: { alignItems: 'flex-start' },
  assistantText: { color: colors.text },
  composer: {
    alignItems: 'flex-end',
    flexDirection: 'row',
    gap: spacing.small,
  },
  content: { gap: spacing.medium, paddingBottom: spacing.small },
  errorText: { color: colors.danger, fontSize: 14, lineHeight: 20 },
  input: {
    backgroundColor: colors.background,
    borderColor: colors.borderStrong,
    borderRadius: radii.medium,
    borderWidth: 1,
    color: colors.text,
    flex: 1,
    fontSize: 16,
    lineHeight: 22,
    maxHeight: 128,
    minHeight: 52,
    paddingHorizontal: spacing.medium,
    paddingVertical: 12,
    textAlignVertical: 'top',
  },
  messageAuthor: {
    fontSize: 12,
    fontWeight: '800',
    marginBottom: spacing.xsmall,
  },
  messageBubble: {
    borderRadius: radii.medium,
    maxWidth: '88%',
    padding: spacing.medium,
  },
  messageList: { gap: spacing.small },
  messageRow: { flexDirection: 'row', width: '100%' },
  messageText: { fontSize: 16, lineHeight: 23 },
  pendingText: { color: colors.muted, fontSize: 12, marginTop: spacing.small },
  sendButton: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: radii.medium,
    justifyContent: 'center',
    minHeight: 52,
    width: 52,
  },
  sendButtonDisabled: { backgroundColor: colors.borderStrong },
  sendButtonPressed: { backgroundColor: colors.primaryPressed },
  userBubble: {
    backgroundColor: colors.primary,
    borderTopRightRadius: radii.small,
  },
  userRow: { justifyContent: 'flex-end' },
  userText: { color: colors.background },
});
