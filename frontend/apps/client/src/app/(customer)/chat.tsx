import type { ReactNode } from 'react';
import { useCallback, useEffect, useState } from 'react';
import Feather from '@expo/vector-icons/Feather';
import { useLocalSearchParams } from 'expo-router';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
import { useSession } from '../../auth/session';
import { FoundationShell } from '../../components/FoundationShell';
import { getApiBaseUrl } from '../../config/environment';
import { useTranslation } from '../../i18n/TranslationProvider';

type Message = {
  id: string;
  role: string;
  status: string;
  text: string;
  uncertainties: string[];
};

function newIdempotencyKey(): string {
  // `crypto.randomUUID()` is not available in every Android/Hermes runtime.
  // This only de-duplicates an accidental resend; it is not a security token.
  return `chat-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

export default function Chat(): ReactNode {
  const { scanId } = useLocalSearchParams<{ scanId: string }>();
  const { token } = useSession();
  const { translate } = useTranslation();
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState('');
  const [sendError, setSendError] = useState<string | null>(null);
  const canSend = Boolean(text.trim() && token);
  const load = useCallback(async (): Promise<void> => {
    if (!scanId || !token) return;
    const response = await fetch(
      `${getApiBaseUrl()}/api/v1/scans/${scanId}/messages`,
      {
        headers: { Authorization: `Bearer ${token}` },
      },
    );
    if (response.ok)
      setMessages(((await response.json()) as { items: Message[] }).items);
  }, [scanId, token]);
  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), 2000);
    return () => clearInterval(id);
  }, [load]);
  const send = async (): Promise<void> => {
    if (!text.trim() || !token) return;
    try {
      const response = await fetch(
        `${getApiBaseUrl()}/api/v1/scans/${scanId}/messages`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
            'Idempotency-Key': newIdempotencyKey(),
          },
          body: JSON.stringify({ text: text.trim() }),
        },
      );
      if (!response.ok) {
        setSendError(translate('chatSendFailed'));
        return;
      }
      setSendError(null);
      setText('');
      void load();
    } catch {
      setSendError(translate('chatSendFailed'));
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
          {messages.map((message) => (
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
        {sendError ? (
          <Text accessibilityRole="alert" style={styles.errorText}>
            {sendError}
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
