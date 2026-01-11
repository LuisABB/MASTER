import googleTrendsConnector from '../connectors/googleTrends.connector.js';
import scoringService from './scoring.service.js';
import prisma from '../db/prismaClient.js';
import { cache } from '../cache/redisClient.js';
import logger from '../utils/logger.js';
import { AppError } from '../middleware/error.middleware.js';

/**
 * Trend Engine Service
 * Orchestrates the complete trend analysis workflow
 */
class TrendEngineService {
  /**
   * Execute trend query with caching and persistence
   */
  async executeTrendQuery(params, requestId) {
    const { keyword, country, windowDays, baselineDays } = params;

    logger.info({ 
      requestId, 
      keyword, 
      country, 
      windowDays, 
      baselineDays 
    }, 'Executing trend query');

    // Check cache first
    const cacheKey = cache.generateKey(keyword, country, windowDays, baselineDays);
    const cachedResult = await cache.get(cacheKey);

    if (cachedResult) {
      logger.info({ requestId, cacheKey }, 'Cache hit');
      const ttl = await cache.getTTL(cacheKey);
      return {
        ...cachedResult,
        cache: {
          hit: true,
          ttl_seconds: ttl
        }
      };
    }

    logger.info({ requestId, cacheKey }, 'Cache miss - fetching fresh data');

    // Create query record in DB
    const query = await this._createQueryRecord(params);

    try {
      // Fetch data from Google Trends
      const trendsData = await googleTrendsConnector.fetchComplete(
        keyword,
        country,
        windowDays,
        baselineDays
      );

      // Calculate score and signals
      const scoring = scoringService.calculateScore(
        trendsData.timeSeries,
        keyword,
        country
      );

      // Persist results to database
      await this._persistResults(query.id, trendsData, scoring);

      // Update query status
      await this._updateQueryStatus(query.id, 'DONE');

      // Build response
      const response = {
        keyword,
        country,
        window_days: windowDays,
        baseline_days: baselineDays,
        generated_at: new Date().toISOString(),
        sources_used: ['google_trends'],
        trend_score: scoring.trendScore,
        signals: scoring.signals,
        series: trendsData.timeSeries,
        by_country: trendsData.byCountry,
        explain: scoring.explain,
        cache: {
          hit: false,
          ttl_seconds: parseInt(process.env.CACHE_TTL_SECONDS || '21600', 10)
        },
        request_id: requestId
      };

      // Cache the result
      await cache.set(cacheKey, response);

      logger.info({ 
        requestId, 
        keyword, 
        country, 
        trendScore: scoring.trendScore 
      }, 'Trend query completed successfully');

      return response;

    } catch (error) {
      // Update query status to error
      await this._updateQueryStatus(query.id, 'ERROR', error.message);

      logger.error({ 
        requestId, 
        error, 
        keyword, 
        country 
      }, 'Trend query failed');

      // Determine if it's a data availability issue or system error
      if (error.message.includes('Invalid response') || error.message.includes('No data')) {
        throw new AppError(
          `No trend data available for keyword "${keyword}" in country "${country}"`,
          404,
          { keyword, country }
        );
      }

      throw new AppError(
        `Failed to fetch trend data: ${error.message}`,
        500,
        { originalError: error.message }
      );
    }
  }

  /**
   * Create initial query record
   */
  async _createQueryRecord(params) {
    try {
      return await prisma.trendQuery.create({
        data: {
          keyword: params.keyword,
          country: params.country,
          windowDays: params.windowDays,
          baselineDays: params.baselineDays,
          status: 'RUNNING'
        }
      });
    } catch (error) {
      logger.error({ error, params }, 'Failed to create query record');
      throw new AppError('Database error while creating query', 500);
    }
  }

  /**
   * Persist results to database
   */
  async _persistResults(queryId, trendsData, scoring) {
    try {
      // Use transaction to ensure atomicity
      await prisma.$transaction(async (tx) => {
        // Create result record
        await tx.trendResult.create({
          data: {
            queryId,
            trendScore: scoring.trendScore,
            signals: scoring.signals,
            explain: scoring.explain,
            sourcesUsed: ['google_trends']
          }
        });

        // Create series points
        if (trendsData.timeSeries && trendsData.timeSeries.length > 0) {
          await tx.trendSeriesPoint.createMany({
            data: trendsData.timeSeries.map(point => ({
              queryId,
              date: new Date(point.date),
              value: point.value
            }))
          });
        }

        // Create country comparison data
        if (trendsData.byCountry && trendsData.byCountry.length > 0) {
          await tx.trendByCountry.createMany({
            data: trendsData.byCountry.map(point => ({
              queryId,
              country: point.country,
              value: point.value
            }))
          });
        }
      });

      logger.info({ queryId }, 'Results persisted successfully');
    } catch (error) {
      logger.error({ error, queryId }, 'Failed to persist results');
      // Don't throw - we still want to return results even if DB fails
    }
  }

  /**
   * Update query status
   */
  async _updateQueryStatus(queryId, status, errorMessage = null) {
    try {
      await prisma.trendQuery.update({
        where: { id: queryId },
        data: {
          status,
          finishedAt: new Date(),
          errorMessage
        }
      });
    } catch (error) {
      logger.error({ error, queryId, status }, 'Failed to update query status');
      // Don't throw - this is non-critical
    }
  }

  /**
   * Get query history (optional - for future use)
   */
  async getQueryHistory(limit = 10) {
    try {
      return await prisma.trendQuery.findMany({
        take: limit,
        orderBy: { createdAt: 'desc' },
        include: {
          result: true
        }
      });
    } catch (error) {
      logger.error({ error }, 'Failed to fetch query history');
      throw new AppError('Database error while fetching history', 500);
    }
  }
}

export default new TrendEngineService();
