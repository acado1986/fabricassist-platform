import type { ReactNode } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';
import Feather from '@expo/vector-icons/Feather';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, radii, spacing } from '@fabricassist/design-tokens';

import { LanguageSelector } from './LanguageSelector';
import { useTranslation } from '../i18n/TranslationProvider';
import { useSession } from '../auth/session';

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
  const { token, signOut } = useSession();
  const { width } = useWindowDimensions();
  const isCompact = width < 640;

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <View
          role="banner"
          style={[styles.topBar, isCompact && styles.topBarCompact]}
        >
          <View style={styles.brandRow}>
            <View style={styles.mark} accessibilityElementsHidden>
              <Text style={styles.markText}>FA</Text>
            </View>
            <View>
              <Text style={styles.brand}>{translate('title')}</Text>
              <Text style={styles.tagline}>{translate('tagline')}</Text>
            </View>
          </View>
          <View style={styles.headerActions}>
            {token ? (
              <>
                <Pressable
                  accessibilityLabel={translate('customerHistory')}
                  accessibilityRole="button"
                  onPress={() => router.push('/history')}
                  style={({ pressed }) => [
                    styles.headerButton,
                    pressed && styles.headerButtonPressed,
                  ]}
                >
                  <Feather color={colors.text} name="clock" size={17} />
                  <Text style={styles.headerButtonText}>
                    {translate('history')}
                  </Text>
                </Pressable>
                <Pressable
                  accessibilityLabel={translate('signOut')}
                  accessibilityRole="button"
                  onPress={() => void signOut()}
                  style={({ pressed }) => [
                    styles.headerButton,
                    pressed && styles.headerButtonPressed,
                  ]}
                >
                  <Feather color={colors.text} name="log-out" size={17} />
                  <Text style={styles.headerButtonText}>
                    {translate('signOut')}
                  </Text>
                </Pressable>
              </>
            ) : null}
            <LanguageSelector />
          </View>
        </View>

        <View role="main" style={[styles.content, wide && styles.contentWide]}>
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
  headerActions: {
    alignItems: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.small,
    justifyContent: 'flex-end',
  },
  headerButton: {
    alignItems: 'center',
    borderColor: colors.border,
    borderRadius: radii.pill,
    borderWidth: 1,
    flexDirection: 'row',
    gap: spacing.xsmall,
    minHeight: 36,
    paddingHorizontal: spacing.small,
  },
  headerButtonPressed: { opacity: 0.72 },
  headerButtonText: { color: colors.text, fontSize: 12, fontWeight: '700' },
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
