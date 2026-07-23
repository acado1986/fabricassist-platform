import type { ReactNode } from 'react';
import { useCallback, useEffect, useState } from 'react';
import { useLocalSearchParams } from 'expo-router';
import { Pressable, ScrollView, Text, TextInput, View } from 'react-native';
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

export default function Chat(): ReactNode {
  const { scanId } = useLocalSearchParams<{ scanId: string }>();
  const { token } = useSession();
  const { translate } = useTranslation();
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState('');
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
    await fetch(`${getApiBaseUrl()}/api/v1/scans/${scanId}/messages`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        'Idempotency-Key': crypto.randomUUID(),
      },
      body: JSON.stringify({ text }),
    });
    setText('');
    void load();
  };
  return (
    <FoundationShell
      title={translate('chatTitle')}
      description={translate('chatQueued')}
    >
      <ScrollView>
        <View>
          {messages.map((message) => (
            <Text key={message.id}>
              {message.role}: {message.text}
            </Text>
          ))}
        </View>
        <TextInput
          accessibilityLabel={translate('chatPlaceholder')}
          value={text}
          onChangeText={setText}
          placeholder={translate('chatPlaceholder')}
        />
        <Pressable accessibilityRole="button" onPress={send}>
          <Text>{translate('chatSend')}</Text>
        </Pressable>
      </ScrollView>
    </FoundationShell>
  );
}
