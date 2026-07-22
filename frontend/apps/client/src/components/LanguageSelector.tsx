import type { ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, radii, spacing } from '@fabricassist/design-tokens';

import { useTranslation } from '../i18n/TranslationProvider';

export function LanguageSelector(): ReactNode {
  const { locale, setLocale, translate } = useTranslation();
  return (
    <View
      accessibilityRole="radiogroup"
      accessibilityLabel={translate('language')}
      style={styles.group}
    >
      {(['en', 'es'] as const).map((option) => {
        const selected = locale === option;
        return (
          <Pressable
            key={option}
            accessibilityRole="radio"
            accessibilityState={{ selected }}
            onPress={() => setLocale(option)}
            style={({ pressed }) => [
              styles.option,
              selected && styles.optionSelected,
              pressed && styles.optionPressed,
            ]}
          >
            <Text style={[styles.label, selected && styles.labelSelected]}>
              {option.toUpperCase()}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}
const styles = StyleSheet.create({
  group: {
    borderColor: colors.border,
    borderWidth: 1,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radii.pill,
    flexDirection: 'row',
    gap: spacing.xsmall,
    padding: spacing.xsmall,
  },
  option: {
    borderRadius: radii.pill,
    minHeight: 36,
    minWidth: 46,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 10,
  },
  optionSelected: { backgroundColor: colors.background },
  optionPressed: { opacity: 0.72, transform: [{ scale: 0.96 }] },
  label: { color: colors.muted, fontSize: 12, fontWeight: '700' },
  labelSelected: { color: colors.primary },
});
