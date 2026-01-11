import Redis from 'ioredis';
import logger from '../utils/logger.js';

const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';

const redis = new Redis(REDIS_URL, {
  retryStrategy: (times) => {
    const delay = Math.min(times * 50, 2000);
    return delay;
  },
  maxRetriesPerRequest: 3,
  enableReadyCheck: true,
  lazyConnect: false
});

redis.on('connect', () => {
  logger.info('Redis connected successfully');
});

redis.on('error', (error) => {
  logger.error({ error }, 'Redis connection error');
});

redis.on('close', () => {
  logger.warn('Redis connection closed');
});

// Graceful shutdown
process.on('beforeExit', async () => {
  await redis.quit();
  logger.info('Redis disconnected');
});

/**
 * Cache helper functions
 */
export const cache = {
  /**
   * Generate cache key for trend query
   */
  generateKey(keyword, region, windowDays, baselineDays) {
    return `trend:${keyword.toLowerCase()}:${region}:${windowDays}:${baselineDays}`;
  },

  /**
   * Get cached trend result
   */
  async get(key) {
    try {
      const data = await redis.get(key);
      return data ? JSON.parse(data) : null;
    } catch (error) {
      logger.error({ error, key }, 'Cache get error');
      return null;
    }
  },

  /**
   * Set cached trend result with TTL
   */
  async set(key, value, ttlSeconds = parseInt(process.env.CACHE_TTL_SECONDS || '21600', 10)) {
    try {
      await redis.setex(key, ttlSeconds, JSON.stringify(value));
      return true;
    } catch (error) {
      logger.error({ error, key }, 'Cache set error');
      return false;
    }
  },

  /**
   * Delete cache entry
   */
  async delete(key) {
    try {
      await redis.del(key);
      return true;
    } catch (error) {
      logger.error({ error, key }, 'Cache delete error');
      return false;
    }
  },

  /**
   * Get TTL for cache key
   */
  async getTTL(key) {
    try {
      return await redis.ttl(key);
    } catch (error) {
      logger.error({ error, key }, 'Cache TTL error');
      return -1;
    }
  }
};

export default redis;
