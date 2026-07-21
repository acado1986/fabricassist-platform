import type { ReactNode } from 'react';
import { Pressable, Text, View } from 'react-native';

import { useTranslation } from '../i18n/TranslationProvider';

export function LanguageSelector(): ReactNode {
  const { locale, setLocale, translate } = useTranslation();

  return (
    <View
      accessibilityRole="radiogroup"
      accessibilityLabel={translate('language')}
      style={{ flexDirection: 'row', gap: 12 }}
    >
      <Pressable
        accessibilityRole="radio"
        accessibilityState={{ selected: locale === 'en' }}
        onPress={() => setLocale('en')}
      >
        <Text>{translate('languageEnglish')}</Text>
      </Pressable>
      <Pressable
        accessibilityRole="radio"
        accessibilityState={{ selected: locale === 'es' }}
        onPress={() => setLocale('es')}
      >
        <Text>{translate('languageSpanish')}</Text>
      </Pressable>
    </View>
  );
}
