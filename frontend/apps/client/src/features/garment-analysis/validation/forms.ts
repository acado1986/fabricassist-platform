import { z } from 'zod';

export const branchReanalysisSchema = z.object({
  branch: z.enum(['garment_inspection', 'label_extraction', 'stain_treatment']),
});

export const correctionSchema = z.object({
  fieldPath: z.string().regex(/^[a-z][a-z0-9_.[\]-]{0,159}$/),
  correctedValue: z.unknown(),
  reason: z.string().trim().min(3).max(500),
});
