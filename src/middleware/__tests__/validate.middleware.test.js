import { describe, test, expect, jest } from '@jest/globals';
import { validate } from '../validate.middleware.js';
import { z } from 'zod';

describe('ValidateMiddleware', () => {
  let mockReq;
  let mockRes;
  let mockNext;

  beforeEach(() => {
    mockReq = {
      body: {},
      requestId: 'test-req-id'
    };
    mockRes = {
      status: jest.fn().mockReturnThis(),
      json: jest.fn()
    };
    mockNext = jest.fn();
  });

  describe('Validación exitosa', () => {
    test('debe pasar validación con datos correctos', () => {
      const schema = z.object({
        keyword: z.string(),
        country: z.string()
      });

      mockReq.body = {
        keyword: 'bitcoin',
        country: 'MX'
      };

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      expect(mockNext).toHaveBeenCalledTimes(1);
      expect(mockNext).toHaveBeenCalledWith();
      expect(mockRes.status).not.toHaveBeenCalled();
      expect(mockRes.json).not.toHaveBeenCalled();
    });

    test('debe agregar validatedBody al request', () => {
      const schema = z.object({
        keyword: z.string(),
        value: z.number()
      });

      mockReq.body = {
        keyword: 'test',
        value: 42
      };

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      expect(mockReq.validatedBody).toEqual({
        keyword: 'test',
        value: 42
      });
    });

    test('debe transformar datos según schema', () => {
      const schema = z.object({
        keyword: z.string().toLowerCase(),
        count: z.string().transform(val => parseInt(val, 10))
      });

      mockReq.body = {
        keyword: 'BITCOIN',
        count: '123'
      };

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      expect(mockReq.validatedBody).toEqual({
        keyword: 'bitcoin',
        count: 123
      });
      expect(mockNext).toHaveBeenCalled();
    });

    test('debe manejar campos opcionales', () => {
      const schema = z.object({
        keyword: z.string(),
        optional: z.string().optional()
      });

      mockReq.body = {
        keyword: 'test'
      };

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      expect(mockNext).toHaveBeenCalled();
      expect(mockReq.validatedBody.keyword).toBe('test');
    });

    test('debe aplicar defaults de schema', () => {
      const schema = z.object({
        keyword: z.string(),
        limit: z.number().default(10)
      });

      mockReq.body = {
        keyword: 'test'
      };

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      expect(mockReq.validatedBody.limit).toBe(10);
    });
  });

  describe('Validación fallida', () => {
    test('debe retornar 400 con campo faltante', () => {
      const schema = z.object({
        keyword: z.string(),
        country: z.string()
      });

      mockReq.body = {
        keyword: 'bitcoin'
        // country faltante
      };

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(400);
      expect(mockRes.json).toHaveBeenCalled();
      expect(mockNext).not.toHaveBeenCalled();

      const errorResponse = mockRes.json.mock.calls[0][0];
      expect(errorResponse).toHaveProperty('error');
      expect(errorResponse).toHaveProperty('details');
      expect(errorResponse).toHaveProperty('request_id', 'test-req-id');
    });

    test('debe retornar detalles del error de validación', () => {
      const schema = z.object({
        email: z.string().email(),
        age: z.number().min(18)
      });

      mockReq.body = {
        email: 'invalid-email',
        age: 15
      };

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(400);
      
      const errorResponse = mockRes.json.mock.calls[0][0];
      expect(errorResponse.error).toBe('Validation failed');
      expect(Array.isArray(errorResponse.details)).toBe(true);
      expect(errorResponse.details.length).toBeGreaterThan(0);
    });

    test('debe incluir el campo que falló en details', () => {
      const schema = z.object({
        keyword: z.string().min(3)
      });

      mockReq.body = {
        keyword: 'ab' // muy corto
      };

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      const errorResponse = mockRes.json.mock.calls[0][0];
      expect(errorResponse.details[0]).toHaveProperty('field');
      expect(errorResponse.details[0].field).toContain('keyword');
    });

    test('debe validar tipo de dato incorrecto', () => {
      const schema = z.object({
        count: z.number()
      });

      mockReq.body = {
        count: 'not-a-number'
      };

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(400);
      expect(mockNext).not.toHaveBeenCalled();
    });

    test('debe validar enum values', () => {
      const schema = z.object({
        country: z.enum(['MX', 'CR', 'ES'])
      });

      mockReq.body = {
        country: 'US'
      };

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(400);
      const errorResponse = mockRes.json.mock.calls[0][0];
      expect(errorResponse.details[0].message).toBeDefined();
    });

    test('debe validar valores mínimos y máximos', () => {
      const schema = z.object({
        rating: z.number().min(1).max(5)
      });

      mockReq.body = {
        rating: 10
      };

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(400);
    });

    test('debe validar longitud de strings', () => {
      const schema = z.object({
        keyword: z.string().min(2).max(60)
      });

      mockReq.body = {
        keyword: 'a'.repeat(100)
      };

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(400);
    });

    test('debe manejar body vacío', () => {
      const schema = z.object({
        keyword: z.string()
      });

      mockReq.body = {};

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(400);
    });

    test('debe manejar body null', () => {
      const schema = z.object({
        keyword: z.string()
      });

      mockReq.body = null;

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(400);
    });

    test('debe incluir requestId en respuesta de error', () => {
      const schema = z.object({
        keyword: z.string()
      });

      mockReq.body = {};
      mockReq.requestId = 'custom-req-id-456';

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      const errorResponse = mockRes.json.mock.calls[0][0];
      expect(errorResponse.request_id).toBe('custom-req-id-456');
    });

    test('debe formatear múltiples errores correctamente', () => {
      const schema = z.object({
        keyword: z.string().min(3),
        country: z.enum(['MX', 'CR', 'ES']),
        value: z.number()
      });

      mockReq.body = {
        keyword: 'ab',
        country: 'US',
        value: 'invalid'
      };

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      const errorResponse = mockRes.json.mock.calls[0][0];
      expect(errorResponse.details.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('Casos edge', () => {
    test('debe manejar schema complejo anidado', () => {
      const schema = z.object({
        user: z.object({
          name: z.string(),
          age: z.number()
        })
      });

      mockReq.body = {
        user: {
          name: 'John',
          age: 25
        }
      };

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      expect(mockNext).toHaveBeenCalled();
      expect(mockReq.validatedBody.user.name).toBe('John');
    });

    test('debe manejar arrays en schema', () => {
      const schema = z.object({
        tags: z.array(z.string())
      });

      mockReq.body = {
        tags: ['bitcoin', 'crypto', 'trends']
      };

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      expect(mockNext).toHaveBeenCalled();
      expect(mockReq.validatedBody.tags).toHaveLength(3);
    });

    test('debe manejar validación custom con refine', () => {
      const schema = z.object({
        password: z.string().refine(val => val.length >= 8, {
          message: 'Password must be at least 8 characters'
        })
      });

      mockReq.body = {
        password: 'short'
      };

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      expect(mockRes.status).toHaveBeenCalledWith(400);
      const errorResponse = mockRes.json.mock.calls[0][0];
      expect(errorResponse.details[0].message).toContain('8 characters');
    });

    test('debe preservar body original sin modificar', () => {
      const schema = z.object({
        keyword: z.string().toLowerCase()
      });

      const originalBody = { keyword: 'BITCOIN' };
      mockReq.body = { ...originalBody };

      const middleware = validate(schema);
      middleware(mockReq, mockRes, mockNext);

      // El body original no debería cambiar
      expect(mockReq.body.keyword).toBe('BITCOIN');
      // Pero validatedBody sí debería estar transformado
      expect(mockReq.validatedBody.keyword).toBe('bitcoin');
    });
  });
});
