import crypto from 'crypto';

/**
 * Middleware to generate and attach a unique request ID to each request
 */
export function requestIdMiddleware(req, res, next) {
  const requestId = req.headers['x-request-id'] || crypto.randomUUID();
  req.requestId = requestId;
  res.setHeader('X-Request-Id', requestId);
  next();
}
