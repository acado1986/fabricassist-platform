import { type ReactNode } from 'react';
import { Pressable, StyleSheet, Text } from 'react-native';
import { router } from 'expo-router';
import { colors } from '@fabricassist/design-tokens';

export function BackBreadcrumb({ label }: { label: string }): ReactNode {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={() => router.back()}
      style={styles.button}
    >
      <Text style={styles.text}>‹ {label}</Text>
    </Pressable>
  );
}
const styles = StyleSheet.create({
  button: { alignSelf: 'flex-start' },
  text: { color: colors.primary, fontWeight: '700' },
});
