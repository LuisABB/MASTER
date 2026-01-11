import { describe, test, expect, jest } from '@jest/globals';
import { AppError, errorHandler, notFoundHandler } from '../error.middleware.js';

describe('ErrorMiddleware', () => {
  describe('AppError', () => {
    test('debe crear error con mensaje, statusCode y details', () => {
      const error = new AppError('Test error', 400, { field: 'test' });

      expect(error.message).toBe('Test error');
      expect(error.statusCode).toBe(400);
      expect(error.details).toEqual({ field: 'test' });
      expect(error.name).toBe('AppError');
      expect(error instanceof Error).toBe(true);
    });

    test('debe usar statusCode 500 por defecto', () => {
      const error = new AppError('Test error');

      expect(error.statusCode).toBe(500);
    });

    test('debe permitir details undefined o null', () => {
      const error = new AppError('Test error', 404);

      // AppError puede inicializar details como null o undefined
      expect(error.details === undefined || error.details === null).toBe(true);
    });

    test('debe capturar stack trace', () => {
      const error = new AppError('Test error');

      expect(error.stack).toBeDefined();
      expect(typeof error.stack).toBe('string');
    });

    test('debe ser instancia de Error', () => {
      const error = new AppError('Test error');

      expect(error instanceof Error).toBe(true);
      expect(error instanceof AppError).toBe(true);
    });

    test('debe manejar details complejos', () => {
      const details = {
        field: 'keyword',
        value: 'test',
        constraints: ['minLength', 'maxLength']
      };
      const error = new AppError('Validation failed', 400, details);

      expect(error.details).toEqual(details);
    });
  });

  describe('errorHandler', () => {
    let mockReq;
    let mockRes;
    let mockNext;

    beforeEach(() => {
      mockReq = {
        requestId: 'test-request-id-123',
        method: 'POST',
        url: '/api/test',
        body: {}
      };
      mockRes = {
        status: jest.fn().mockReturnThis(),
        json: jest.fn()
      };
      mockNext = jest.fn();
      // Set NODE_ENV to development for consistent testing
      process.env.NODE_ENV = 'development';
    });

    afterEach(() => {
      delete process.env.NODE_ENV;
    });

    test('debe manejar AppError con statusCode personalizado', () => {
      const error = new AppError('Not found', 404, { resource: 'user' });

      errorHandler(error, mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(404);
      expect(mockRes.json).toHaveBeenCalledWith({
        error: 'Not found',
        details: { resource: 'user' },
        request_id: 'test-request-id-123'
      });
    });

    test('debe manejar error genérico con statusCode 500 en development', () => {
      const error = new Error('Something went wrong');

      errorHandler(error, mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(500);
      expect(mockRes.json).toHaveBeenCalledWith({
        error: 'Something went wrong',  // Shows actual message in development
        request_id: 'test-request-id-123'
      });
    });

    test('debe incluir requestId en respuesta', () => {
      const error = new AppError('Test error', 400);
      mockReq.requestId = 'custom-id-789';

      errorHandler(error, mockReq, mockRes, mockNext);

      const response = mockRes.json.mock.calls[0][0];
      expect(response.request_id).toBe('custom-id-789');
    });

    test('debe omitir details si es undefined', () => {
      const error = new AppError('Test error', 400);

      errorHandler(error, mockReq, mockRes, mockNext);

      const response = mockRes.json.mock.calls[0][0];
      expect(response).not.toHaveProperty('details');
      expect(response.error).toBe('Test error');
    });

    test('debe manejar error 401 Unauthorized', () => {
      const error = new AppError('Unauthorized', 401);

      errorHandler(error, mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(401);
      expect(mockRes.json.mock.calls[0][0].error).toBe('Unauthorized');
    });

    test('debe manejar error 403 Forbidden', () => {
      const error = new AppError('Forbidden', 403);

      errorHandler(error, mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(403);
    });

    test('debe manejar error 429 Too Many Requests', () => {
      const error = new AppError('Rate limit exceeded', 429);

      errorHandler(error, mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(429);
    });

    test('debe manejar error 503 Service Unavailable', () => {
      const error = new AppError('Service unavailable', 503);

      errorHandler(error, mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(503);
    });

    test('debe NO exponer mensaje interno en error genérico en production', () => {
      process.env.NODE_ENV = 'production';
      const error = new Error('Database connection failed: secret-password');

      errorHandler(error, mockReq, mockRes, mockNext);

      const response = mockRes.json.mock.calls[0][0];
      expect(response.error).toBe('Internal server error');
      expect(response.error).not.toContain('secret-password');
    });

    test('debe manejar error sin mensaje', () => {
      const error = new Error();

      errorHandler(error, mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(500);
      expect(mockRes.json).toHaveBeenCalled();
    });

    test('debe manejar error con statusCode inválido', () => {
      const error = new AppError('Test', 999);

      errorHandler(error, mockReq, mockRes, mockNext);

      // Debería usar el statusCode aunque sea inválido
      expect(mockRes.status).toHaveBeenCalledWith(999);
    });

    test('debe manejar múltiples errores consecutivos', () => {
      const error1 = new AppError('Error 1', 400);
      const error2 = new AppError('Error 2', 404);
      const error3 = new AppError('Error 3', 500);

      errorHandler(error1, mockReq, mockRes, mockNext);
      errorHandler(error2, mockReq, mockRes, mockNext);
      errorHandler(error3, mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledTimes(3);
      expect(mockRes.json).toHaveBeenCalledTimes(3);
    });

    test('debe incluir details cuando está presente', () => {
      const error = new AppError('Validation error', 400, {
        fields: ['email', 'password'],
        constraints: { email: 'invalid format' }
      });

      errorHandler(error, mockReq, mockRes, mockNext);

      const response = mockRes.json.mock.calls[0][0];
      expect(response.details).toEqual({
        fields: ['email', 'password'],
        constraints: { email: 'invalid format' }
      });
    });

    test('debe manejar error con details null', () => {
      const error = new AppError('Test', 400, null);

      errorHandler(error, mockReq, mockRes, mockNext);

      const response = mockRes.json.mock.calls[0][0];
      expect(response).not.toHaveProperty('details');
    });

    test('debe manejar requestId undefined', () => {
      delete mockReq.requestId;

      const error = new AppError('Test', 400);
      errorHandler(error, mockReq, mockRes, mockNext);

      const response = mockRes.json.mock.calls[0][0];
      expect(response.request_id).toBeUndefined();
    });

    test('debe preservar estructura de error para diferentes códigos', () => {
      const statusCodes = [400, 401, 403, 404, 422, 429, 500, 503];

      statusCodes.forEach(code => {
        const error = new AppError(`Error ${code}`, code);
        const req = { requestId: `req-${code}` };
        const res = {
          status: jest.fn().mockReturnThis(),
          json: jest.fn()
        };

        errorHandler(error, req, res, mockNext);

        expect(res.status).toHaveBeenCalledWith(code);
        const response = res.json.mock.calls[0][0];
        expect(response).toHaveProperty('error');
        expect(response).toHaveProperty('request_id');
      });
    });
  });

  describe('notFoundHandler', () => {
    let mockReq;
    let mockRes;

    beforeEach(() => {
      mockReq = {
        requestId: 'test-request-id-123',
        path: '/api/nonexistent'
      };
      mockRes = {
        status: jest.fn().mockReturnThis(),
        json: jest.fn()
      };
    });

    test('debe retornar 404 con mensaje apropiado', () => {
      notFoundHandler(mockReq, mockRes);

      expect(mockRes.status).toHaveBeenCalledWith(404);
      expect(mockRes.json).toHaveBeenCalledWith({
        error: 'Route not found',
        path: '/api/nonexistent',
        request_id: 'test-request-id-123'
      });
    });

    test('debe incluir path del request', () => {
      mockReq.path = '/v1/trends/invalid';

      notFoundHandler(mockReq, mockRes);

      const response = mockRes.json.mock.calls[0][0];
      expect(response.path).toBe('/v1/trends/invalid');
    });

    test('debe incluir requestId', () => {
      mockReq.requestId = 'not-found-req-999';

      notFoundHandler(mockReq, mockRes);

      const response = mockRes.json.mock.calls[0][0];
      expect(response.request_id).toBe('not-found-req-999');
    });

    test('debe manejar rutas largas', () => {
      mockReq.path = '/api/v1/trends/query/bitcoin/MX/30/365/extra/params';

      notFoundHandler(mockReq, mockRes);

      const response = mockRes.json.mock.calls[0][0];
      expect(response.path).toBe('/api/v1/trends/query/bitcoin/MX/30/365/extra/params');
    });

    test('debe manejar rutas sin query strings', () => {
      mockReq.path = '/api/trends';

      notFoundHandler(mockReq, mockRes);

      const response = mockRes.json.mock.calls[0][0];
      expect(response.path).toBe('/api/trends');
    });

    test('debe manejar path undefined', () => {
      delete mockReq.path;

      notFoundHandler(mockReq, mockRes);

      expect(mockRes.status).toHaveBeenCalledWith(404);
      const response = mockRes.json.mock.calls[0][0];
      expect(response).toHaveProperty('error', 'Route not found');
    });

    test('debe siempre retornar 404', () => {
      const urls = ['/api/test', '/v1/users/123', '/nonexistent', '/'];

      urls.forEach(url => {
        const req = { requestId: 'test', originalUrl: url };
        const res = {
          status: jest.fn().mockReturnThis(),
          json: jest.fn()
        };

        notFoundHandler(req, res);

        expect(res.status).toHaveBeenCalledWith(404);
      });
    });

    test('debe tener estructura de respuesta consistente', () => {
      notFoundHandler(mockReq, mockRes);

      const response = mockRes.json.mock.calls[0][0];
      expect(response).toHaveProperty('error');
      expect(response).toHaveProperty('path');
      expect(response).toHaveProperty('request_id');
      expect(Object.keys(response).length).toBe(3);
    });
  });
});
