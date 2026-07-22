import type { ReactNode } from 'react';
import {
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, radii, spacing } from '@fabricassist/design-tokens';

import { LanguageSelector } from './LanguageSelector';
import { useTranslation } from '../i18n/TranslationProvider';

export function FoundationShell({
  children,
  title,
  description,
  wide = false,
}: {
  children: ReactNode;
  title?: string;
  description?: string;
  wide?: boolean;
}): ReactNode {
  const { translate } = useTranslation();
  const { width } = useWindowDimensions();
  const isCompact = width < 640;

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <View style={[styles.topBar, isCompact && styles.topBarCompact]}>
          <View style={styles.brandRow}>
            <View style={styles.mark} accessibilityElementsHidden>
              <Text style={styles.markText}>FA</Text>
            </View>
            <View>
              <Text style={styles.brand}>{translate('title')}</Text>
              <Text style={styles.tagline}>{translate('tagline')}</Text>
            </View>
          </View>
          <LanguageSelector />
        </View>

        <View style={[styles.content, wide && styles.contentWide]}>
          {title ? (
            <View style={styles.headingGroup}>
              <Text accessibilityRole="header" style={styles.pageTitle}>
                {title}
              </Text>
              {description ? (
                <Text style={styles.pageDescription}>{description}</Text>
              ) : null}
            </View>
          ) : null}
          <View style={styles.card}>{children}</View>
          <Text style={styles.privacyNote}>{translate('privacyNote')}</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { backgroundColor: colors.canvas, flex: 1 },
  scrollContent: { flexGrow: 1, paddingBottom: spacing.xxlarge },
  topBar: {
    alignItems: 'center',
    alignSelf: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    maxWidth: 1120,
    paddingHorizontal: spacing.large,
    paddingVertical: spacing.large,
    width: '100%',
  },
  topBarCompact: {
    alignItems: 'flex-start',
    flexDirection: 'column',
    gap: spacing.medium,
  },
  brandRow: { alignItems: 'center', flexDirection: 'row', gap: 12 },
  mark: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: radii.medium,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  markText: {
    color: colors.background,
    fontSize: 16,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  brand: {
    color: colors.text,
    fontSize: 21,
    fontWeight: '800',
    letterSpacing: -0.4,
  },
  tagline: { color: colors.muted, fontSize: 12, marginTop: 2 },
  content: {
    alignSelf: 'center',
    maxWidth: 520,
    paddingHorizontal: spacing.medium,
    paddingTop: spacing.xlarge,
    width: '100%',
  },
  contentWide: { maxWidth: 760 },
  headingGroup: { marginBottom: spacing.large },
  pageTitle: {
    color: colors.text,
    fontSize: 34,
    fontWeight: '800',
    letterSpacing: -0.8,
    lineHeight: 40,
  },
  pageDescription: {
    color: colors.muted,
    fontSize: 16,
    lineHeight: 24,
    marginTop: spacing.small,
  },
  card: {
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: radii.large,
    borderWidth: 1,
    gap: spacing.medium,
    padding: spacing.xlarge,
    shadowColor: '#173D31',
    shadowOffset: { height: 8, width: 0 },
    shadowOpacity: 0.08,
    shadowRadius: 24,
  },
  privacyNote: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 18,
    marginTop: spacing.medium,
    textAlign: 'center',
  },
});
