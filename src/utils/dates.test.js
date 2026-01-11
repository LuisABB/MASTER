import { describe, test, expect } from '@jest/globals';
import { getDateRange } from './dates.js';

describe('Utils: dates.js', () => {
  describe('getDateRange', () => {
    test('debe generar rango de fechas correcto con 30 días de ventana y 60 de baseline', () => {
      const result = getDateRange(30, 60);
      
      expect(result).toHaveProperty('startDate');
      expect(result).toHaveProperty('endDate');
      expect(result).toHaveProperty('windowStartDate');
      expect(typeof result.startDate).toBe('string');
      expect(typeof result.endDate).toBe('string');
      expect(typeof result.windowStartDate).toBe('string');
      
      // Verificar formato de fecha (YYYY-MM-DD)
      expect(result.startDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(result.endDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(result.windowStartDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    });

    test('debe calcular correctamente la diferencia de días (baseline)', () => {
      const result = getDateRange(7, 30);
      
      const start = new Date(result.startDate);
      const end = new Date(result.endDate);
      const diffDays = Math.ceil((end - start) / (1000 * 60 * 60 * 24));
      
      // Debe ser 30 días (solo baseline)
      expect(diffDays).toBe(30);
    });

    test('debe calcular correctamente windowStartDate', () => {
      const result = getDateRange(7, 30);
      
      const windowStart = new Date(result.windowStartDate);
      const end = new Date(result.endDate);
      const diffDays = Math.ceil((end - windowStart) / (1000 * 60 * 60 * 24));
      
      // Ventana debe ser 7 días
      expect(diffDays).toBe(7);
    });

    test('debe retornar endDate como fecha actual (o muy cercana)', () => {
      const result = getDateRange(30, 60);
      const today = new Date().toISOString().split('T')[0];
      const endDate = result.endDate;
      
      // Verificar que endDate sea hoy o ayer (por diferencia de zona horaria)
      const isToday = endDate === today;
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      const isYesterday = endDate === yesterday.toISOString().split('T')[0];
      
      expect(isToday || isYesterday).toBe(true);
    });

    test('debe manejar valores pequeños correctamente', () => {
      const result = getDateRange(1, 1);
      
      const start = new Date(result.startDate);
      const end = new Date(result.endDate);
      const diffDays = Math.ceil((end - start) / (1000 * 60 * 60 * 24));
      
      expect(diffDays).toBe(1); // Solo baseline = 1 día
    });

    test('debe manejar valores grandes correctamente', () => {
      const result = getDateRange(90, 365);
      
      const start = new Date(result.startDate);
      const end = new Date(result.endDate);
      const diffDays = Math.ceil((end - start) / (1000 * 60 * 60 * 24));
      
      expect(diffDays).toBe(365); // Solo baseline = 365 días
    });

    test('windowStartDate debe estar entre startDate y endDate', () => {
      const result = getDateRange(15, 60);
      
      const start = new Date(result.startDate);
      const windowStart = new Date(result.windowStartDate);
      const end = new Date(result.endDate);
      
      expect(windowStart.getTime()).toBeGreaterThan(start.getTime());
      expect(windowStart.getTime()).toBeLessThan(end.getTime());
    });
  });
});

