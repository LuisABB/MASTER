import { describe, test, expect, jest } from '@jest/globals';
import { requestIdMiddleware } from '../requestId.middleware.js';

describe('RequestIdMiddleware', () => {
  let mockReq;
  let mockRes;
  let mockNext;

  beforeEach(() => {
    mockReq = {
      headers: {}
    };
    mockRes = {
      setHeader: jest.fn()
    };
    mockNext = jest.fn();
  });

  test('debe generar un requestId si no existe en headers', () => {
    requestIdMiddleware(mockReq, mockRes, mockNext);

    expect(mockReq.requestId).toBeDefined();
    expect(typeof mockReq.requestId).toBe('string');
    expect(mockReq.requestId.length).toBeGreaterThan(0);
    expect(mockNext).toHaveBeenCalledTimes(1);
  });

  test('debe usar x-request-id del header si existe', () => {
    mockReq.headers['x-request-id'] = 'custom-request-id-123';

    requestIdMiddleware(mockReq, mockRes, mockNext);

    expect(mockReq.requestId).toBe('custom-request-id-123');
    expect(mockNext).toHaveBeenCalledTimes(1);
  });

  test('debe generar UUID válido cuando no hay header', () => {
    requestIdMiddleware(mockReq, mockRes, mockNext);

    // UUID format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    expect(mockReq.requestId).toMatch(uuidRegex);
  });

  test('debe generar requestIds únicos en múltiples llamadas', () => {
    const requestIds = new Set();

    for (let i = 0; i < 100; i++) {
      const req = { headers: {} };
      const res = { setHeader: jest.fn() };
      const next = jest.fn();

      requestIdMiddleware(req, res, next);
      requestIds.add(req.requestId);
    }

    // Todos los IDs deben ser únicos
    expect(requestIds.size).toBe(100);
  });

  test('debe llamar a next() exactamente una vez', () => {
    requestIdMiddleware(mockReq, mockRes, mockNext);

    expect(mockNext).toHaveBeenCalledTimes(1);
    expect(mockNext).toHaveBeenCalledWith();
  });

  test('debe respetar header con diferentes variaciones de case', () => {
    // Express normaliza headers a lowercase
    mockReq.headers['x-request-id'] = 'header-id-456';

    requestIdMiddleware(mockReq, mockRes, mockNext);

    expect(mockReq.requestId).toBe('header-id-456');
  });

  test('debe manejar header vacío generando nuevo ID', () => {
    mockReq.headers['x-request-id'] = '';

    requestIdMiddleware(mockReq, mockRes, mockNext);

    // Si el header está vacío, debería generar uno nuevo
    expect(mockReq.requestId).toBeDefined();
    expect(mockReq.requestId.length).toBeGreaterThan(0);
  });

  test('debe trabajar con headers undefined', () => {
    mockReq.headers = undefined;

    // No debería lanzar error
    expect(() => {
      requestIdMiddleware(mockReq, mockRes, mockNext);
    }).not.toThrow();

    expect(mockReq.requestId).toBeDefined();
    expect(mockNext).toHaveBeenCalled();
  });

  test('debe agregar requestId al objeto req sin modificar otros campos', () => {
    mockReq.user = { id: 123 };
    mockReq.body = { keyword: 'test' };

    requestIdMiddleware(mockReq, mockRes, mockNext);

    expect(mockReq.requestId).toBeDefined();
    expect(mockReq.user).toEqual({ id: 123 });
    expect(mockReq.body).toEqual({ keyword: 'test' });
  });

  test('debe funcionar con requestId muy largo del header', () => {
    const longId = 'a'.repeat(500);
    mockReq.headers['x-request-id'] = longId;

    requestIdMiddleware(mockReq, mockRes, mockNext);

    expect(mockReq.requestId).toBe(longId);
  });

  test('debe manejar caracteres especiales en requestId del header', () => {
    mockReq.headers['x-request-id'] = 'req-123_ABC-xyz.test';

    requestIdMiddleware(mockReq, mockRes, mockNext);

    expect(mockReq.requestId).toBe('req-123_ABC-xyz.test');
  });
});
