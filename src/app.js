import express from 'express';
import helmet from 'helmet';
import cors from 'cors';
import rateLimit from 'express-rate-limit';
import pinoHttp from 'pino-http';
import logger from './utils/logger.js';
import { requestIdMiddleware } from './middleware/requestId.middleware.js';
import { errorHandler, notFoundHandler } from './middleware/error.middleware.js';

// Routes
import healthRoutes from './routes/health.routes.js';
import trendsRoutes from './routes/trends.routes.js';
import regionsRoutes from './routes/regions.routes.js';

const app = express();

// Security middleware
app.use(helmet());

// CORS configuration
app.use(cors({
  origin: process.env.CORS_ORIGIN || '*',
  credentials: true
}));

// Request parsing
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: true, limit: '1mb' }));

// Request ID middleware (must be before logger)
app.use(requestIdMiddleware);

// HTTP logging with Pino
app.use(pinoHttp({
  logger,
  customProps: (req) => ({
    requestId: req.requestId
  }),
  serializers: {
    req: (req) => ({
      id: req.id,
      method: req.method,
      url: req.url,
      requestId: req.raw.requestId
    }),
    res: (res) => ({
      statusCode: res.statusCode
    })
  }
}));

// Rate limiting
const limiter = rateLimit({
  windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS || '60000', 10), // 1 minute default
  max: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS || '60', 10), // 60 requests per window
  message: {
    error: 'Too many requests from this IP, please try again later.',
    retry_after_seconds: 60
  },
  standardHeaders: true,
  legacyHeaders: false,
  // Add request ID to rate limit response
  handler: (req, res) => {
    res.status(429).json({
      error: 'Too many requests from this IP, please try again later.',
      retry_after_seconds: 60,
      request_id: req.requestId
    });
  }
});

app.use('/v1/', limiter);

// Root endpoint
app.get('/', (req, res) => {
  res.json({
    name: 'Trends API',
    version: '1.0.0',
    status: 'running',
    endpoints: {
      health: '/health',
      trends: '/v1/trends/query',
      regions: '/v1/regions'
    }
  });
});

// API Routes
app.use('/health', healthRoutes);
app.use('/v1/trends', trendsRoutes);
app.use('/v1/regions', regionsRoutes);

// 404 handler
app.use(notFoundHandler);

// Global error handler (must be last)
app.use(errorHandler);

export default app;
