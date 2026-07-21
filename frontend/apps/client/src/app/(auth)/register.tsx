import type { ReactNode } from 'react';
import { useState } from 'react';
import { Link } from 'expo-router';
import { Button, Text, TextInput } from 'react-native';
import { useSession } from '../../auth/session';
import { FoundationShell } from '../../components/FoundationShell';
export default function Register(): ReactNode {
  const { signIn } = useSession();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(false);
  return (
    <FoundationShell>
      <Text accessibilityRole="header">Create account</Text>
      <TextInput
        accessibilityLabel="Email"
        autoCapitalize="none"
        value={email}
        onChangeText={setEmail}
      />
      <TextInput
        accessibilityLabel="Password"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
      />
      {error ? <Text>Registration failed.</Text> : null}
      <Button
        title="Create account"
        onPress={() => {
          void signIn(email, password, true).catch(() => setError(true));
        }}
      />
      <Link href="/login">Sign in</Link>
    </FoundationShell>
  );
}
