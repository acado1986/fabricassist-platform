import type { en } from './en';

type TranslationShape<T> = {
  [Key in keyof T]: T[Key] extends Record<string, unknown>
    ? TranslationShape<T[Key]>
    : string;
};

export type TranslationCatalog = TranslationShape<typeof en>;
export type TranslationKey = keyof TranslationCatalog['shell'];
export type SupportedLocale = 'en' | 'es';
