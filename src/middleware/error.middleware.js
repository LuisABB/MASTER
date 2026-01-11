import logger from '../utils/logger.js';

/**
 * Global error handler middleware
 */
export function errorHandler(err, req, res, next) {
  const statusCode = err.statusCode || 500;
  const message = err.message || 'Internal server error';

  // Log error with full context
  logger.error({
    requestId: req.requestId,
    error: {
      message: err.message,
      stack: err.stack,
      code: err.code,
      statusCode
    },
    request: {
      method: req.method,
      url: req.url,
      body: req.body
    }
  }, 'Request error');

  // Don't leak internal errors in production
  const response = {
    error: statusCode === 500 && process.env.NODE_ENV === 'production' 
      ? 'Internal server error' 
      : message,
    request_id: req.requestId
  };

  // Include additional context in development
  if (process.env.NODE_ENV === 'development' && err.details) {
    response.details = err.details;
  }

  res.status(statusCode).json(response);
}

/**
 * 404 handler for undefined routes
 */
export function notFoundHandler(req, res) {
  res.status(404).json({
    error: 'Route not found',
    path: req.path,
    request_id: req.requestId
  });
}

/**
 * Custom error class for application errors
 */
export class AppError extends Error {
  constructor(message, statusCode = 500, details = null) {
    super(message);
    this.statusCode = statusCode;
    this.details = details;
    this.name = this.constructor.name;
    Error.captureStackTrace(this, this.constructor);
  }
}
