import express from 'express';
import { validate } from '../middleware/validate.middleware.js';
import { trendQuerySchema } from '../schemas/trend.schema.js';
import { queryTrend } from '../controllers/trends.controller.js';

const router = express.Router();

/**
 * POST /v1/trends/query
 * Execute a trend analysis query
 */
router.post('/query', validate(trendQuerySchema), queryTrend);

export default router;
