import { z } from 'zod';

/** Strict custom-scalar boundary validation shared by typed GraphQL callers. */
export const uuidSchema = z.uuid();
export const dateTimeSchema = z.iso.datetime({ offset: true });
export const decimalSchema = z.string().regex(/^-?\d+(?:\.\d+)?$/);

export type UUID = z.infer<typeof uuidSchema>;
export type DateTime = z.infer<typeof dateTimeSchema>;
export type Decimal = z.infer<typeof decimalSchema>;

export function parseUuid(value: unknown): UUID {
  return uuidSchema.parse(value);
}
