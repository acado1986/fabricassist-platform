import type { ReactNode } from 'react';
import { useState } from 'react';
import { Link } from 'expo-router';
import { Button, Text, TextInput } from 'react-native';
import { useSession } from '../../auth/session';
import { FoundationShell } from '../../components/FoundationShell';
export default function Login(): ReactNode {
  const { signIn } = useSession();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(false);
  return (
    <FoundationShell>
      <Text accessibilityRole="header">Sign in</Text>
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
      {error ? <Text>Sign in failed.</Text> : null}
      <Button
        title="Sign in"
        onPress={() => {
          void signIn(email, password, false).catch(() => setError(true));
        }}
      />
      <Link href="/register">Create an account</Link>
    </FoundationShell>
  );
}
