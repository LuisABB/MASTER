import { describe, test, expect } from '@jest/globals';
import { 
  normalizeTimeSeries, 
  normalizeRegionalData,
  clamp,
  average,
  max
} from './normalize.js';

describe('Utils: normalize.js', () => {
  describe('normalizeTimeSeries', () => {
    test('debe normalizar datos con formattedTime', () => {
      const mockData = [
        { formattedTime: '2022-01-02', value: 50 },
        { formattedTime: '2022-01-03', value: 75 },
        { formattedTime: '2022-01-01', value: 25 }
      ];

      const result = normalizeTimeSeries(mockData);

      expect(result).toHaveLength(3);
      // Debe ordenar por fecha
      expect(result[0]).toEqual({ date: '2022-01-01', value: 25 });
      expect(result[1]).toEqual({ date: '2022-01-02', value: 50 });
      expect(result[2]).toEqual({ date: '2022-01-03', value: 75 });
    });

    test('debe parsear valores a enteros', () => {
      const mockData = [
        { formattedTime: '2022-01-01', value: '42' },
        { formattedTime: '2022-01-02', value: 75.9 }
      ];

      const result = normalizeTimeSeries(mockData);

      expect(result[0].value).toBe(42);
      expect(result[1].value).toBe(75);
    });

    test('debe filtrar puntos sin value', () => {
      const mockData = [
        { formattedTime: '2022-01-01', value: 50 },
        { formattedTime: '2022-01-02' }, // Sin value
        { formattedTime: '2022-01-03', value: 100 }
      ];

      const result = normalizeTimeSeries(mockData);

      expect(result).toHaveLength(2);
    });

    test('debe retornar array vacío si input no es array', () => {
      expect(normalizeTimeSeries(null)).toEqual([]);
      expect(normalizeTimeSeries(undefined)).toEqual([]);
      expect(normalizeTimeSeries('string')).toEqual([]);
    });

    test('debe manejar valores 0 correctamente', () => {
      const mockData = [
        { formattedTime: '2022-01-01', value: 0 }
      ];

      const result = normalizeTimeSeries(mockData);

      expect(result[0].value).toBe(0);
    });
  });

  describe('normalizeRegionalData', () => {
    test('debe normalizar datos de países con geoCode', () => {
      const mockData = [
        { geoCode: 'MX', value: 100 },
        { geoCode: 'CR', value: 75 },
        { geoCode: 'ES', value: 50 }
      ];

      const result = normalizeRegionalData(mockData);

      expect(result).toHaveLength(3);
      // Debe ordenar por value descendente
      expect(result[0]).toEqual({ country: 'MX', value: 100 });
      expect(result[1]).toEqual({ country: 'CR', value: 75 });
      expect(result[2]).toEqual({ country: 'ES', value: 50 });
    });

    test('debe parsear valores a enteros', () => {
      const mockData = [
        { geoCode: 'MX', value: '88' },
        { geoCode: 'CR', value: 75.9 }
      ];

      const result = normalizeRegionalData(mockData);

      expect(result[0].value).toBe(88);
      expect(result[1].value).toBe(75);
    });

    test('debe usar UNKNOWN si no hay geoCode', () => {
      const mockData = [
        { value: 50 }
      ];

      const result = normalizeRegionalData(mockData);

      expect(result[0].country).toBe('UNKNOWN');
    });

    test('debe ordenar por value descendente', () => {
      const mockData = [
        { geoCode: 'MX-A', value: 30 },
        { geoCode: 'MX-B', value: 90 },
        { geoCode: 'MX-C', value: 60 }
      ];

      const result = normalizeRegionalData(mockData);

      expect(result[0].value).toBe(90);
      expect(result[1].value).toBe(60);
      expect(result[2].value).toBe(30);
    });

    test('debe retornar array vacío si input no es array', () => {
      expect(normalizeRegionalData(null)).toEqual([]);
      expect(normalizeRegionalData(undefined)).toEqual([]);
    });
  });

  describe('clamp', () => {
    test('debe limitar valores al rango 0-1 por defecto', () => {
      expect(clamp(0.5)).toBe(0.5);
      expect(clamp(1.5)).toBe(1);
      expect(clamp(-0.5)).toBe(0);
    });

    test('debe aceptar rangos personalizados', () => {
      expect(clamp(50, 0, 100)).toBe(50);
      expect(clamp(150, 0, 100)).toBe(100);
      expect(clamp(-10, 0, 100)).toBe(0);
    });

    test('debe manejar valores en el límite', () => {
      expect(clamp(0, 0, 1)).toBe(0);
      expect(clamp(1, 0, 1)).toBe(1);
    });
  });

  describe('average', () => {
    test('debe calcular promedio correcto', () => {
      expect(average([10, 20, 30])).toBe(20);
      expect(average([1, 2, 3, 4, 5])).toBe(3);
      expect(average([100])).toBe(100);
    });

    test('debe manejar arrays vacíos', () => {
      expect(average([])).toBe(0);
      expect(average(null)).toBe(0);
      expect(average(undefined)).toBe(0);
    });

    test('debe manejar valores decimales', () => {
      expect(average([1.5, 2.5, 3.5])).toBeCloseTo(2.5);
    });

    test('debe manejar valores negativos', () => {
      expect(average([-10, 0, 10])).toBe(0);
    });
  });

  describe('max', () => {
    test('debe retornar el valor máximo', () => {
      expect(max([10, 50, 30, 20])).toBe(50);
      expect(max([1])).toBe(1);
      expect(max([100, 200, 150])).toBe(200);
    });

    test('debe manejar arrays vacíos', () => {
      expect(max([])).toBe(0);
      expect(max(null)).toBe(0);
      expect(max(undefined)).toBe(0);
    });

    test('debe manejar valores negativos', () => {
      expect(max([-10, -5, -20])).toBe(-5);
    });

    test('debe manejar valores decimales', () => {
      expect(max([1.5, 2.9, 2.1])).toBe(2.9);
    });
  });
});
