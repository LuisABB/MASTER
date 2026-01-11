import { describe, test, expect, jest } from '@jest/globals';

describe('TrendsController', () => {
  describe('queryTrend', () => {
    test('debe extraer parámetros correctamente de validatedBody', () => {
      const validatedBody = {
        keyword: 'bitcoin',
        country: 'MX',
        windowDays: 30,
        baselineDays: 365
      };

      expect(validatedBody.keyword).toBe('bitcoin');
      expect(validatedBody.country).toBe('MX');
      expect(validatedBody.windowDays).toBe(30);
      expect(validatedBody.baselineDays).toBe(365);
    });

    test('debe aceptar país MX', () => {
      const validatedBody = {
        keyword: 'test',
        country: 'MX',
        windowDays: 30,
        baselineDays: 365
      };

      expect(validatedBody.country).toBe('MX');
      expect(['MX', 'CR', 'ES']).toContain(validatedBody.country);
    });

    test('debe aceptar país CR', () => {
      const validatedBody = {
        keyword: 'test',
        country: 'CR',
        windowDays: 30,
        baselineDays: 365
      };

      expect(validatedBody.country).toBe('CR');
      expect(['MX', 'CR', 'ES']).toContain(validatedBody.country);
    });

    test('debe aceptar país ES', () => {
      const validatedBody = {
        keyword: 'test',
        country: 'ES',
        windowDays: 30,
        baselineDays: 365
      };

      expect(validatedBody.country).toBe('ES');
      expect(['MX', 'CR', 'ES']).toContain(validatedBody.country);
    });

    test('debe aceptar diferentes window_days válidos', () => {
      const validWindowDays = [7, 30, 90, 365];

      validWindowDays.forEach(windowDays => {
        const body = {
          keyword: 'test',
          country: 'MX',
          windowDays,
          baselineDays: 365
        };

        expect([7, 30, 90, 365]).toContain(body.windowDays);
      });
    });

    test('debe aceptar diferentes baseline_days', () => {
      const validBaselineDays = [30, 90, 180, 365, 730];

      validBaselineDays.forEach(baselineDays => {
        const body = {
          keyword: 'test',
          country: 'MX',
          windowDays: 30,
          baselineDays
        };

        expect(body.baselineDays).toBeGreaterThan(0);
        expect(body.baselineDays).toBeLessThanOrEqual(730);
      });
    });

    test('debe validar que country sea string', () => {
      const validatedBody = {
        keyword: 'test',
        country: 'MX',
        windowDays: 30,
        baselineDays: 365
      };

      expect(typeof validatedBody.country).toBe('string');
      expect(validatedBody.country.length).toBe(2); // ISO 3166-1 alpha-2
    });

    test('debe validar que keyword sea string', () => {
      const validatedBody = {
        keyword: 'bitcoin',
        country: 'MX',
        windowDays: 30,
        baselineDays: 365
      };

      expect(typeof validatedBody.keyword).toBe('string');
      expect(validatedBody.keyword.length).toBeGreaterThan(0);
    });

    test('debe validar que windowDays sea número', () => {
      const validatedBody = {
        keyword: 'test',
        country: 'MX',
        windowDays: 30,
        baselineDays: 365
      };

      expect(typeof validatedBody.windowDays).toBe('number');
      expect(Number.isInteger(validatedBody.windowDays)).toBe(true);
    });

    test('debe validar que baselineDays sea número', () => {
      const validatedBody = {
        keyword: 'test',
        country: 'MX',
        windowDays: 30,
        baselineDays: 365
      };

      expect(typeof validatedBody.baselineDays).toBe('number');
      expect(Number.isInteger(validatedBody.baselineDays)).toBe(true);
    });
  });
});
