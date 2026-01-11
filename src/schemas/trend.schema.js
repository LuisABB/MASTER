import { z } from 'zod';
import { isRegionSupported } from '../utils/regionMap.js';

/**
 * Validation schema for trend query
 */
export const trendQuerySchema = z.object({
  keyword: z
    .string()
    .min(2, 'Keyword must be at least 2 characters')
    .max(60, 'Keyword must be at most 60 characters')
    .trim(),
  
  region: z
    .string()
    .refine(
      (val) => isRegionSupported(val),
      (val) => ({ message: `Region "${val}" is not supported` })
    ),
  
  window_days: z
    .number()
    .int()
    .positive()
    .refine(
      (val) => [7, 30, 90, 365].includes(val),
      { message: 'window_days must be one of: 7, 30, 90, 365' }
    )
    .default(90),
  
  baseline_days: z
    .number()
    .int()
    .positive()
    .max(730, 'baseline_days must be at most 730 (2 years)')
    .default(365)
}).refine(
  (data) => data.baseline_days >= data.window_days,
  {
    message: 'baseline_days must be greater than or equal to window_days',
    path: ['baseline_days']
  }
);
