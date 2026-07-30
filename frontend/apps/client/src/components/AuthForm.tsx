import type { ReactNode } from 'react';
import { useEffect, useRef, useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link } from 'expo-router';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
import { z } from 'zod';

import { useSession } from '../auth/session';
import { FoundationShell } from './FoundationShell';
import { useTranslation } from '../i18n/TranslationProvider';

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(12),
});
type Values = z.infer<typeof schema>;

export function AuthForm({ mode }: { mode: 'login' | 'register' }): ReactNode {
  const { signIn, bootstrapLogin } = useSession();
  const { translate } = useTranslation();
  const [serverError, setServerError] = useState(false);
  const bootstrapStarted = useRef(false);
  const [isBootstrapping, setIsBootstrapping] = useState(false);
  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '' },
  });
  const register = mode === 'register';

  async function submit(values: Values): Promise<void> {
    setServerError(false);
    await signIn(values.email, values.password, register).catch(() =>
      setServerError(true),
    );
  }

  useEffect(() => {
    if (register || bootstrapStarted.current) return;
    bootstrapStarted.current = true;
    setIsBootstrapping(true);
    void bootstrapLogin().finally(() => setIsBootstrapping(false));
  }, [bootstrapLogin, register]);

  return (
    <FoundationShell
      title={translate(register ? 'registerTitle' : 'loginTitle')}
      description={translate(
        register ? 'registerDescription' : 'loginDescription',
      )}
    >
      <View style={styles.fieldGroup}>
        <Text style={styles.label}>{translate('emailLabel')}</Text>
        <Controller
          control={control}
          name="email"
          render={({ field: { onBlur, onChange, value } }) => (
            <TextInput
              accessibilityLabel={translate('emailLabel')}
              autoCapitalize="none"
              autoComplete="email"
              inputMode="email"
              onBlur={onBlur}
              onChangeText={onChange}
              placeholder={translate('emailPlaceholder')}
              placeholderTextColor={colors.borderStrong}
              style={[styles.input, errors.email && styles.inputError]}
              value={value}
            />
          )}
        />
        {errors.email ? (
          <Text style={styles.error}>{translate('emailError')}</Text>
        ) : null}
      </View>
      <View style={styles.fieldGroup}>
        <Text style={styles.label}>{translate('passwordLabel')}</Text>
        <Controller
          control={control}
          name="password"
          render={({ field: { onBlur, onChange, value } }) => (
            <TextInput
              accessibilityLabel={translate('passwordLabel')}
              autoComplete={register ? 'new-password' : 'current-password'}
              onBlur={onBlur}
              onChangeText={onChange}
              placeholder={translate('passwordPlaceholder')}
              placeholderTextColor={colors.borderStrong}
              secureTextEntry
              style={[styles.input, errors.password && styles.inputError]}
              value={value}
            />
          )}
        />
        <Text style={styles.hint}>{translate('passwordHint')}</Text>
        {errors.password ? (
          <Text style={styles.error}>{translate('passwordError')}</Text>
        ) : null}
      </View>
      {isBootstrapping ? (
        <Text accessibilityLiveRegion="polite" style={styles.hint}>
          {translate('loginWarming')}
        </Text>
      ) : null}
      {serverError ? (
        <View style={styles.errorBanner}>
          <Text style={styles.error}>
            {translate(register ? 'registerError' : 'loginError')}
          </Text>
        </View>
      ) : null}
      <Pressable
        accessibilityRole="button"
        disabled={isSubmitting}
        onPress={() => void handleSubmit(submit)()}
        style={({ pressed }) => [
          styles.primaryButton,
          pressed && styles.primaryButtonPressed,
          isSubmitting && styles.disabled,
        ]}
      >
        {isSubmitting ? (
          <ActivityIndicator color={colors.background} />
        ) : (
          <Text style={styles.primaryButtonText}>
            {translate(register ? 'registerAction' : 'loginAction')}
          </Text>
        )}
      </Pressable>
      <View style={styles.switchRow}>
        <Text style={styles.switchText}>
          {translate(register ? 'haveAccount' : 'needAccount')}
        </Text>
        <Link href={register ? '/login' : '/register'} style={styles.link}>
          {translate(register ? 'loginAction' : 'registerAction')}
        </Link>
      </View>
    </FoundationShell>
  );
}

const styles = StyleSheet.create({
  fieldGroup: { gap: spacing.small },
  label: { color: colors.text, fontSize: 14, fontWeight: '700' },
  input: {
    backgroundColor: colors.background,
    borderColor: colors.borderStrong,
    borderRadius: radii.medium,
    borderWidth: 1.5,
    color: colors.text,
    fontSize: 16,
    minHeight: 52,
    paddingHorizontal: spacing.medium,
    paddingVertical: 12,
  },
  inputError: { borderColor: colors.danger },
  hint: { color: colors.muted, fontSize: 12, lineHeight: 18 },
  error: { color: colors.danger, fontSize: 13, fontWeight: '600' },
  errorBanner: {
    backgroundColor: colors.dangerSoft,
    borderRadius: radii.small,
    padding: 12,
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: radii.medium,
    justifyContent: 'center',
    minHeight: 52,
    paddingHorizontal: spacing.large,
    shadowColor: colors.primary,
    shadowOffset: { height: 6, width: 0 },
    shadowOpacity: 0.22,
    shadowRadius: 10,
    elevation: 3,
  },
  primaryButtonPressed: {
    backgroundColor: colors.primaryPressed,
    transform: [{ translateY: 1 }],
  },
  primaryButtonText: {
    color: colors.background,
    fontSize: 16,
    fontWeight: '800',
  },
  disabled: { opacity: 0.65 },
  switchRow: {
    alignItems: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    justifyContent: 'center',
    paddingTop: spacing.small,
  },
  switchText: { color: colors.muted, fontSize: 14 },
  link: { color: colors.primary, fontSize: 14, fontWeight: '800' },
});
