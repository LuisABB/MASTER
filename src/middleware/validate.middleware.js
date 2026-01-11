import { z } from 'zod';
import logger from '../utils/logger.js';

/**
 * Validate request body against a Zod schema
 */
export function validate(schema) {
  return (req, res, next) => {
    try {
      const validated = schema.parse(req.body);
      req.validatedBody = validated;
      next();
    } catch (error) {
      if (error instanceof z.ZodError) {
        logger.warn({ 
          requestId: req.requestId, 
          errors: error.errors 
        }, 'Validation error');
        
        return res.status(400).json({
          error: 'Validation failed',
          details: error.errors.map(err => ({
            field: err.path.join('.'),
            message: err.message
          })),
          request_id: req.requestId
        });
      }
      next(error);
    }
  };
}
