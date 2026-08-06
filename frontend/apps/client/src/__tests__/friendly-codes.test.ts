import { catalogs } from '@fabricassist/translations';
import { friendlyCode } from '../features/garment-analysis/friendlyCodes';

describe('friendlyCode', () => {
  it.each([
    ['needs_better_image', 'validationNeedsBetterImage'],
    ['CARE_LABEL_REQUIRED', 'warningCareLabelRequired'],
    ['LABEL_PROHIBITS_WATER_WASH', 'warningWaterWashProhibited'],
  ])('translates %s in both supported locales', (code, key) => {
    expect(
      friendlyCode(code, (translationKey) => catalogs.en.shell[translationKey]),
    ).toBe(catalogs.en.shell[key as keyof typeof catalogs.en.shell]);
    expect(
      friendlyCode(code, (translationKey) => catalogs.es.shell[translationKey]),
    ).toBe(catalogs.es.shell[key as keyof typeof catalogs.es.shell]);
  });

  it('uses a readable fallback for an unknown provider value', () => {
    expect(friendlyCode('new_provider_status', () => 'unused')).toBe(
      'New Provider Status',
    );
  });
});
