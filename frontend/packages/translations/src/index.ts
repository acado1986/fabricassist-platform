import { en } from './en';
import { es } from './es';

export type {
  SupportedLocale,
  TranslationCatalog,
  TranslationKey,
} from './types';

export const catalogs = { en, es } as const;
