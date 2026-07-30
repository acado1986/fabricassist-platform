import type { ReactNode } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import Feather from '@expo/vector-icons/Feather';
import { colors, radii, spacing } from '@fabricassist/design-tokens';
import { useTranslation } from '../i18n/TranslationProvider';

type GarmentDeletionConfirmationProps = {
  isDeleting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  visible: boolean;
};

/** A platform-neutral confirmation dialog for irreversible garment deletion. */
export function GarmentDeletionConfirmation({
  isDeleting,
  onCancel,
  onConfirm,
  visible,
}: GarmentDeletionConfirmationProps): ReactNode {
  const { translate } = useTranslation();

  return (
    <Modal
      animationType="fade"
      onRequestClose={onCancel}
      transparent
      visible={visible}
    >
      <View accessibilityViewIsModal style={styles.overlay}>
        <View accessibilityRole="alert" style={styles.dialog}>
          <Feather color={colors.danger} name="alert-triangle" size={28} />
          <Text accessibilityRole="header" style={styles.title}>
            {translate('deleteGarmentConfirmTitle')}
          </Text>
          <Text style={styles.description}>
            {translate('deleteGarmentConfirmDescription')}
          </Text>
          <View style={styles.actions}>
            <Pressable
              accessibilityLabel={translate('cameraCancel')}
              accessibilityRole="button"
              disabled={isDeleting}
              onPress={onCancel}
              style={({ pressed }) => [
                styles.cancelButton,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.cancelText}>{translate('cameraCancel')}</Text>
            </Pressable>
            <Pressable
              accessibilityLabel={translate('deleteGarmentConfirmAction')}
              accessibilityRole="button"
              disabled={isDeleting}
              onPress={onConfirm}
              style={({ pressed }) => [
                styles.confirmButton,
                pressed && styles.pressed,
                isDeleting && styles.disabled,
              ]}
            >
              <Text style={styles.confirmText}>
                {translate('deleteGarmentConfirmAction')}
              </Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    alignItems: 'center',
    backgroundColor: 'rgba(20, 35, 31, 0.52)',
    flex: 1,
    justifyContent: 'center',
    padding: spacing.large,
  },
  dialog: {
    alignItems: 'center',
    backgroundColor: colors.background,
    borderRadius: radii.medium,
    gap: spacing.medium,
    maxWidth: 440,
    padding: spacing.large,
    width: '100%',
  },
  title: {
    color: colors.text,
    fontSize: 21,
    fontWeight: '800',
    textAlign: 'center',
  },
  description: { color: colors.muted, lineHeight: 21, textAlign: 'center' },
  actions: {
    flexDirection: 'row',
    gap: spacing.small,
    justifyContent: 'flex-end',
    width: '100%',
  },
  cancelButton: {
    borderColor: colors.border,
    borderRadius: radii.small,
    borderWidth: 1,
    paddingHorizontal: spacing.medium,
    paddingVertical: spacing.small,
  },
  cancelText: { color: colors.text, fontWeight: '700' },
  confirmButton: {
    backgroundColor: colors.danger,
    borderRadius: radii.small,
    paddingHorizontal: spacing.medium,
    paddingVertical: spacing.small,
  },
  confirmText: { color: colors.background, fontWeight: '800' },
  pressed: { opacity: 0.72 },
  disabled: { opacity: 0.55 },
});
