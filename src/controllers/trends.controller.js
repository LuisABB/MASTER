import trendEngineService from '../services/trendEngine.service.js';
import logger from '../utils/logger.js';

/**
 * Trend Query Controller
 */
export async function queryTrend(req, res, next) {
  try {
    const params = {
      keyword: req.validatedBody.keyword,
      country: req.validatedBody.country,
      windowDays: req.validatedBody.window_days,
      baselineDays: req.validatedBody.baseline_days
    };

    logger.info({ 
      requestId: req.requestId, 
      params 
    }, 'Processing trend query request');

    const result = await trendEngineService.executeTrendQuery(params, req.requestId);

    res.json(result);
  } catch (error) {
    next(error);
  }
}
