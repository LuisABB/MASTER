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
   * Version is included to prevent conflicts when data structure changes
   */
  generateKey(keyword, region, windowDays, baselineDays, version = 'v4') {
    return `trend:${version}:${keyword.toLowerCase()}:${region}:${windowDays}:${baselineDays}`;
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
   * Get stale cached data (incluso si expiró)
   * Útil como fallback cuando la API falla
   */
  async getStale(key) {
    try {
      const staleKey = `${key}:stale`;
      const data = await redis.get(staleKey);
      
      if (!data) {
        return null;
      }

      const parsed = JSON.parse(data);
      const now = Date.now();
      const age = Math.floor((now - parsed.cachedAt) / 1000); // Age in seconds

      return {
        ...parsed.data,
        age, // Edad en segundos
        cachedAt: parsed.cachedAt
      };
    } catch (error) {
      logger.error({ error, key }, 'Stale cache get error');
      return null;
    }
  },

  /**
   * Set cached trend result with TTL
   */
  async set(key, value, ttlSeconds = parseInt(process.env.CACHE_TTL_SECONDS || '86400', 10)) {
    try {
      // Guardar en cache normal
      await redis.setex(key, ttlSeconds, JSON.stringify(value));

      // Guardar copia stale con TTL más largo (para fallback)
      const staleTTL = parseInt(process.env.CACHE_STALE_TTL_SECONDS || '172800', 10);
      const staleKey = `${key}:stale`;
      await redis.setex(staleKey, staleTTL, JSON.stringify({
        data: value,
        cachedAt: Date.now()
      }));

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
