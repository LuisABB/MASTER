import express from 'express';
import prisma from '../db/prismaClient.js';
import redis from '../cache/redisClient.js';

const router = express.Router();

/**
 * GET /health
 * Health check endpoint
 */
router.get('/', async (req, res) => {
  const health = {
    status: 'ok',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    services: {
      database: 'unknown',
      cache: 'unknown'
    }
  };

  // Check database connection
  try {
    await prisma.$queryRaw`SELECT 1`;
    health.services.database = 'ok';
  } catch (error) {
    health.services.database = 'error';
    health.status = 'degraded';
  }

  // Check Redis connection
  try {
    await redis.ping();
    health.services.cache = 'ok';
  } catch (error) {
    health.services.cache = 'error';
    health.status = 'degraded';
  }

  const statusCode = health.status === 'ok' ? 200 : 503;
  res.status(statusCode).json(health);
});

export default router;
