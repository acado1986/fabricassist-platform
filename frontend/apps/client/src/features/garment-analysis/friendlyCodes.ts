import type { TranslationKey } from '@fabricassist/translations';

const keys: Record<string, TranslationKey> = {
  needs_better_image: 'validationNeedsBetterImage',
  CARE_LABEL_REQUIRED: 'warningCareLabelRequired',
  LABEL_EXTRACTION_FAILED: 'statusLabelExtractionFailed',
  label_unknown: 'statusLabelUnknown',
  not_attempted: 'statusNotAttempted',
  not_found: 'statusNotFound',
  LABEL_PROHIBITS_WATER_WASH: 'warningWaterWashProhibited',
  LABEL_PROHIBITS_DRY_CLEAN: 'warningDryCleanProhibited',
  WASH_TEMPERATURE_EXCEEDS_LABEL: 'warningTemperatureExceeded',
};

export function friendlyCode(
  value: string,
  translate: (key: TranslationKey) => string,
): string {
  const key = keys[value];
  if (key) return translate(key);
  return value
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
