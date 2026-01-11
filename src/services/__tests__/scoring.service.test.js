import { describe, test, expect } from '@jest/globals';
import scoringService from '../scoring.service.js';

describe('ScoringService', () => {
  describe('calculateScore', () => {
    test('debe calcular score para tendencia creciente', () => {
      const timeSeries = [
        { date: '2025-01-01', value: 20 },
        { date: '2025-01-02', value: 25 },
        { date: '2025-01-03', value: 30 },
        { date: '2025-01-04', value: 35 },
        { date: '2025-01-05', value: 40 },
        { date: '2025-01-06', value: 45 },
        { date: '2025-01-07', value: 50 },
        { date: '2025-01-08', value: 55 },
        { date: '2025-01-09', value: 60 },
        { date: '2025-01-10', value: 65 },
        { date: '2025-01-11', value: 70 },
        { date: '2025-01-12', value: 75 },
        { date: '2025-01-13', value: 80 },
        { date: '2025-01-14', value: 85 },
        { date: '2025-01-15', value: 90 }
      ];

      const result = scoringService.calculateScore(timeSeries, 'bitcoin', 'MX');

      expect(result.trendScore).toBeGreaterThan(60);
      expect(result.signals.growth_7_vs_30).toBeGreaterThan(1);
      expect(result.signals.slope_14d).toBeGreaterThan(0);
      expect(result.signals.recent_peak_30d).toBeGreaterThan(0.5);
      expect(result.explain).toHaveLength(4);
      expect(result.explain[3]).toContain('MX');
    });

    test('debe calcular score para tendencia decreciente', () => {
      const timeSeries = [
        { date: '2025-01-01', value: 90 },
        { date: '2025-01-02', value: 85 },
        { date: '2025-01-03', value: 80 },
        { date: '2025-01-04', value: 75 },
        { date: '2025-01-05', value: 70 },
        { date: '2025-01-06', value: 65 },
        { date: '2025-01-07', value: 60 },
        { date: '2025-01-08', value: 55 },
        { date: '2025-01-09', value: 50 },
        { date: '2025-01-10', value: 45 },
        { date: '2025-01-11', value: 40 },
        { date: '2025-01-12', value: 35 },
        { date: '2025-01-13', value: 30 },
        { date: '2025-01-14', value: 25 },
        { date: '2025-01-15', value: 20 }
      ];

      const result = scoringService.calculateScore(timeSeries, 'test', 'CR');

      expect(result.trendScore).toBeLessThan(40);
      expect(result.signals.growth_7_vs_30).toBeLessThan(1);
      expect(result.signals.slope_14d).toBeLessThan(0);
      expect(result.explain[3]).toContain('CR');
    });

    test('debe calcular score para tendencia estable', () => {
      const timeSeries = Array.from({ length: 30 }, (_, i) => ({
        date: `2025-01-${String(i + 1).padStart(2, '0')}`,
        value: 50
      }));

      const result = scoringService.calculateScore(timeSeries, 'stable', 'ES');

      expect(result.trendScore).toBeGreaterThan(30);
      expect(result.trendScore).toBeLessThan(60);
      expect(result.signals.growth_7_vs_30).toBeCloseTo(1, 1);
      expect(result.signals.slope_14d).toBeCloseTo(0, 2);
      expect(result.explain[3]).toContain('ES');
    });

    test('debe lanzar error si timeSeries está vacío', () => {
      expect(() => {
        scoringService.calculateScore([], 'test', 'MX');
      }).toThrow('Time series data is empty');
    });

    test('debe lanzar error si timeSeries es null', () => {
      expect(() => {
        scoringService.calculateScore(null, 'test', 'MX');
      }).toThrow('Time series data is empty');
    });

    test('debe generar explicación de crecimiento alto', () => {
      const timeSeries = [
        ...Array.from({ length: 23 }, (_, i) => ({
          date: `2025-01-${String(i + 1).padStart(2, '0')}`,
          value: 30
        })),
        ...Array.from({ length: 7 }, (_, i) => ({
          date: `2025-01-${String(i + 24).padStart(2, '0')}`,
          value: 50
        }))
      ];

      const result = scoringService.calculateScore(timeSeries, 'test', 'MX');

      expect(result.explain[0]).toContain('creció');
      expect(result.explain[0]).toContain('%');
    });

    test('debe generar explicación de caída', () => {
      const timeSeries = [
        ...Array.from({ length: 23 }, (_, i) => ({
          date: `2025-01-${String(i + 1).padStart(2, '0')}`,
          value: 70
        })),
        ...Array.from({ length: 7 }, (_, i) => ({
          date: `2025-01-${String(i + 24).padStart(2, '0')}`,
          value: 30
        }))
      ];

      const result = scoringService.calculateScore(timeSeries, 'test', 'MX');

      expect(result.explain[0]).toContain('cayó');
    });

    test('debe generar explicación de estabilidad', () => {
      const timeSeries = Array.from({ length: 30 }, (_, i) => ({
        date: `2025-01-${String(i + 1).padStart(2, '0')}`,
        value: 50
      }));

      const result = scoringService.calculateScore(timeSeries, 'test', 'MX');

      expect(result.explain[0]).toContain('estable');
    });

    test('debe incluir país en explicación final', () => {
      const timeSeries = Array.from({ length: 15 }, (_, i) => ({
        date: `2025-01-${String(i + 1).padStart(2, '0')}`,
        value: 50
      }));

      const resultMX = scoringService.calculateScore(timeSeries, 'test', 'MX');
      const resultCR = scoringService.calculateScore(timeSeries, 'test', 'CR');
      const resultES = scoringService.calculateScore(timeSeries, 'test', 'ES');

      expect(resultMX.explain[3]).toContain('MX');
      expect(resultCR.explain[3]).toContain('CR');
      expect(resultES.explain[3]).toContain('ES');
    });

    test('debe redondear valores correctamente', () => {
      const timeSeries = [
        { date: '2025-01-01', value: 33 },
        { date: '2025-01-02', value: 34 },
        { date: '2025-01-03', value: 35 },
        { date: '2025-01-04', value: 36 },
        { date: '2025-01-05', value: 37 },
        { date: '2025-01-06', value: 38 },
        { date: '2025-01-07', value: 39 },
        { date: '2025-01-08', value: 40 },
        { date: '2025-01-09', value: 41 },
        { date: '2025-01-10', value: 42 },
        { date: '2025-01-11', value: 43 },
        { date: '2025-01-12', value: 44 },
        { date: '2025-01-13', value: 45 },
        { date: '2025-01-14', value: 46 },
        { date: '2025-01-15', value: 47 }
      ];

      const result = scoringService.calculateScore(timeSeries, 'test', 'MX');

      // Trend score debe tener máximo 2 decimales
      expect(result.trendScore.toString().split('.')[1]?.length || 0).toBeLessThanOrEqual(2);
      
      // Growth debe tener máximo 2 decimales
      expect(result.signals.growth_7_vs_30.toString().split('.')[1]?.length || 0).toBeLessThanOrEqual(2);
      
      // Slope debe tener máximo 4 decimales
      expect(result.signals.slope_14d.toString().split('.')[1]?.length || 0).toBeLessThanOrEqual(4);
      
      // Peak debe tener máximo 2 decimales
      expect(result.signals.recent_peak_30d.toString().split('.')[1]?.length || 0).toBeLessThanOrEqual(2);
    });
  });
});
