import type { ComponentProps, ReactNode } from 'react';
import { useState } from 'react';
import {
  Modal,
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
  const [customerMenuOpen, setCustomerMenuOpen] = useState(false);
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
              <View style={styles.customerMenu}>
                <Pressable
                  accessibilityLabel={translate('customerMenu')}
                  accessibilityRole="button"
                  accessibilityState={{ expanded: customerMenuOpen }}
                  onPress={() => setCustomerMenuOpen((open) => !open)}
                  style={({ pressed }) => [
                    styles.headerButton,
                    pressed && styles.headerButtonPressed,
                  ]}
                >
                  <Feather color={colors.text} name="menu" size={18} />
                  <Text style={styles.headerButtonText}>
                    {translate('customerMenu')}
                  </Text>
                </Pressable>
              </View>
            ) : null}
            {!token ? <LanguageSelector /> : null}
          </View>
        </View>

        <Modal
          animationType="fade"
          onRequestClose={() => setCustomerMenuOpen(false)}
          transparent
          visible={customerMenuOpen}
        >
          <View style={styles.menuOverlay}>
            <Pressable
              accessibilityLabel={translate('closeMenu')}
              accessibilityRole="button"
              onPress={() => setCustomerMenuOpen(false)}
              style={styles.menuBackdrop}
            />
            <View
              accessibilityRole="menu"
              style={[styles.menuPanel, isCompact && styles.menuPanelCompact]}
            >
              <MenuItem
                icon="camera"
                label={translate('scan')}
                onPress={() => {
                  setCustomerMenuOpen(false);
                  router.push('/scan');
                }}
              />
              <MenuItem
                icon="clock"
                label={translate('history')}
                onPress={() => {
                  setCustomerMenuOpen(false);
                  router.push('/history');
                }}
              />
              <View style={styles.languageMenuItem}>
                <Text style={styles.menuLabel}>{translate('language')}</Text>
                <LanguageSelector />
              </View>
              <MenuItem
                icon="log-out"
                label={translate('signOut')}
                onPress={() => void signOut()}
              />
            </View>
          </View>
        </Modal>

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

function MenuItem({
  icon,
  label,
  onPress,
}: {
  icon: ComponentProps<typeof Feather>['name'];
  label: string;
  onPress: () => void;
}): ReactNode {
  return (
    <Pressable
      accessibilityRole="menuitem"
      onPress={onPress}
      style={({ pressed }) => [
        styles.menuItem,
        pressed && styles.menuItemPressed,
      ]}
    >
      <Feather color={colors.text} name={icon} size={17} />
      <Text style={styles.menuLabel}>{label}</Text>
    </Pressable>
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
    alignSelf: 'flex-end',
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.small,
    justifyContent: 'flex-end',
  },
  customerMenu: { zIndex: 3 },
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
  menuOverlay: { flex: 1 },
  menuBackdrop: { bottom: 0, left: 0, position: 'absolute', right: 0, top: 0 },
  menuPanel: {
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: radii.medium,
    borderWidth: 1,
    elevation: 8,
    gap: spacing.xsmall,
    minWidth: 200,
    padding: spacing.xsmall,
    position: 'absolute',
    right: spacing.large,
    top: 76,
  },
  menuPanelCompact: {
    right: spacing.medium,
    top: 118,
  },
  menuItem: {
    alignItems: 'center',
    borderRadius: radii.small,
    flexDirection: 'row',
    gap: spacing.small,
    minHeight: 44,
    paddingHorizontal: spacing.small,
  },
  menuItemPressed: { backgroundColor: colors.surfaceMuted },
  menuLabel: { color: colors.text, fontSize: 14, fontWeight: '600' },
  languageMenuItem: {
    alignItems: 'center',
    borderTopColor: colors.border,
    borderTopWidth: 1,
    flexDirection: 'row',
    gap: spacing.small,
    justifyContent: 'space-between',
    minHeight: 52,
    paddingHorizontal: spacing.small,
  },
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
