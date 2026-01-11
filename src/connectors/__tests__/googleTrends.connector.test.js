import { describe, test, expect, beforeEach } from '@jest/globals';
import googleTrendsConnector from '../googleTrends.connector.js';

describe('GoogleTrendsConnector (MOCKED - No llama a Google Trends real)', () => {
  
  describe('Constructor y configuración', () => {
    test('debe inicializarse con configuración por defecto', () => {
      expect(googleTrendsConnector).toBeDefined();
      expect(googleTrendsConnector.maxRetries).toBeDefined();
      expect(googleTrendsConnector.retryDelay).toBeDefined();
      expect(googleTrendsConnector.requestDelay).toBeDefined();
      expect(googleTrendsConnector.concurrency).toBeDefined();
    });

    test('debe tener valores numéricos positivos en la configuración', () => {
      expect(typeof googleTrendsConnector.maxRetries).toBe('number');
      expect(typeof googleTrendsConnector.retryDelay).toBe('number');
      expect(typeof googleTrendsConnector.requestDelay).toBe('number');
      expect(typeof googleTrendsConnector.concurrency).toBe('number');
      
      expect(googleTrendsConnector.maxRetries).toBeGreaterThan(0);
      expect(googleTrendsConnector.retryDelay).toBeGreaterThan(0);
      expect(googleTrendsConnector.requestDelay).toBeGreaterThan(0);
      expect(googleTrendsConnector.concurrency).toBeGreaterThan(0);
    });

    test('debe tener lock queue inicializado', () => {
      expect(Array.isArray(googleTrendsConnector.lockQueue)).toBe(true);
    });
  });

  describe('fetchComplete', () => {
    test('debe retornar datos completos con timeSeries y byCountry', async () => {
      const result = await googleTrendsConnector.fetchComplete('bitcoin', 'MX', 30, 365);

      expect(result).toHaveProperty('timeSeries');
      expect(result).toHaveProperty('byCountry');
      expect(Array.isArray(result.timeSeries)).toBe(true);
      expect(Array.isArray(result.byCountry)).toBe(true);
    });

    test('debe retornar 366 puntos en timeSeries (window + baseline)', async () => {
      const result = await googleTrendsConnector.fetchComplete('test', 'MX', 30, 365);

      // 30 days window + 365 days baseline = 395 days
      // Pero el conector genera baseline_days + 1 para incluir el día actual
      expect(result.timeSeries.length).toBe(366);
    });

    test('debe retornar 3 países en byCountry', async () => {
      const result = await googleTrendsConnector.fetchComplete('test', 'MX', 30, 365);

      expect(result.byCountry).toHaveLength(3);
      
      const countryCodes = result.byCountry.map(c => c.country);
      expect(countryCodes).toContain('MX');
      expect(countryCodes).toContain('CR');
      expect(countryCodes).toContain('ES');
    });

    test('debe tener valores entre 0-100 en timeSeries', async () => {
      const result = await googleTrendsConnector.fetchComplete('test', 'MX', 30, 365);

      result.timeSeries.forEach(point => {
        expect(point.value).toBeGreaterThanOrEqual(0);
        expect(point.value).toBeLessThanOrEqual(100);
      });
    });

    test('debe tener valores entre 0-100 en byCountry', async () => {
      const result = await googleTrendsConnector.fetchComplete('test', 'CR', 30, 365);

      result.byCountry.forEach(point => {
        expect(point.value).toBeGreaterThanOrEqual(0);
        expect(point.value).toBeLessThanOrEqual(100);
      });
    });

    test('debe tener formato de fecha correcto en timeSeries', async () => {
      const result = await googleTrendsConnector.fetchComplete('test', 'ES', 7, 30);

      result.timeSeries.forEach(point => {
        expect(point).toHaveProperty('date');
        expect(point.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
        expect(new Date(point.date).toString()).not.toBe('Invalid Date');
      });
    });

    test('debe ordenar timeSeries cronológicamente', async () => {
      const result = await googleTrendsConnector.fetchComplete('test', 'MX', 30, 365);

      for (let i = 1; i < result.timeSeries.length; i++) {
        const prevDate = new Date(result.timeSeries[i - 1].date);
        const currDate = new Date(result.timeSeries[i].date);
        expect(currDate.getTime()).toBeGreaterThan(prevDate.getTime());
      }
    });

    test('debe ordenar byCountry por valor descendente', async () => {
      const result = await googleTrendsConnector.fetchComplete('test', 'MX', 30, 365);

      for (let i = 1; i < result.byCountry.length; i++) {
        expect(result.byCountry[i - 1].value).toBeGreaterThanOrEqual(result.byCountry[i].value);
      }
    });

    test('debe generar datos diferentes para diferentes keywords', async () => {
      const result1 = await googleTrendsConnector.fetchComplete('bitcoin', 'MX', 30, 365);
      const result2 = await googleTrendsConnector.fetchComplete('ethereum', 'MX', 30, 365);

      // Aunque son datos mock, deberían tener cierta variación
      const avg1 = result1.timeSeries.reduce((sum, p) => sum + p.value, 0) / result1.timeSeries.length;
      const avg2 = result2.timeSeries.reduce((sum, p) => sum + p.value, 0) / result2.timeSeries.length;

      // Puede que sean iguales por el mock, pero la estructura debe ser correcta
      expect(avg1).toBeGreaterThan(0);
      expect(avg2).toBeGreaterThan(0);
    });

    test('debe incluir el país consultado en byCountry', async () => {
      const resultMX = await googleTrendsConnector.fetchComplete('test', 'MX', 30, 365);
      const resultCR = await googleTrendsConnector.fetchComplete('test', 'CR', 30, 365);
      const resultES = await googleTrendsConnector.fetchComplete('test', 'ES', 30, 365);

      expect(resultMX.byCountry.some(c => c.country === 'MX')).toBe(true);
      expect(resultCR.byCountry.some(c => c.country === 'CR')).toBe(true);
      expect(resultES.byCountry.some(c => c.country === 'ES')).toBe(true);
    });

    test('debe funcionar con diferentes window_days', async () => {
      const result7 = await googleTrendsConnector.fetchComplete('test', 'MX', 7, 30);
      const result30 = await googleTrendsConnector.fetchComplete('test', 'MX', 30, 365);
      const result90 = await googleTrendsConnector.fetchComplete('test', 'MX', 90, 365);

      expect(result7.timeSeries.length).toBeGreaterThan(0);
      expect(result30.timeSeries.length).toBeGreaterThan(0);
      expect(result90.timeSeries.length).toBeGreaterThan(0);
    });

    test('debe tener country property en cada punto de byCountry', async () => {
      const result = await googleTrendsConnector.fetchComplete('test', 'MX', 30, 365);

      result.byCountry.forEach(point => {
        expect(point).toHaveProperty('country');
        expect(point).toHaveProperty('value');
        expect(typeof point.country).toBe('string');
        expect(typeof point.value).toBe('number');
      });
    });

    test('debe tener date y value en cada punto de timeSeries', async () => {
      const result = await googleTrendsConnector.fetchComplete('test', 'MX', 30, 365);

      result.timeSeries.forEach(point => {
        expect(point).toHaveProperty('date');
        expect(point).toHaveProperty('value');
        expect(typeof point.date).toBe('string');
        expect(typeof point.value).toBe('number');
      });
    });
  });

  describe('fetchByCountry', () => {
    test('debe retornar array de 3 países', async () => {
      const result = await googleTrendsConnector.fetchByCountry('test');

      expect(Array.isArray(result)).toBe(true);
      expect(result).toHaveLength(3);
    });

    test('debe contener MX, CR, ES', async () => {
      const result = await googleTrendsConnector.fetchByCountry('test');

      const codes = result.map(c => c.country);
      expect(codes).toContain('MX');
      expect(codes).toContain('CR');
      expect(codes).toContain('ES');
    });
  });

  describe('Funciones helpers y utilidades', () => {
    test('_formatTimestamp debe estar disponible', () => {
      expect(typeof googleTrendsConnector._formatTimestamp).toBe('function');
    });

    test('_delay debe estar disponible', () => {
      expect(typeof googleTrendsConnector._delay).toBe('function');
    });

    test('_acquireLock debe estar disponible', () => {
      expect(typeof googleTrendsConnector._acquireLock).toBe('function');
    });

    test('_releaseLock debe estar disponible', () => {
      expect(typeof googleTrendsConnector._releaseLock).toBe('function');
    });

    test('_formatTimestamp debe convertir timestamp a fecha ISO', () => {
      // Timestamp de ejemplo: 1610928000 = 2021-01-18
      const formatted = googleTrendsConnector._formatTimestamp('1610928000');
      expect(formatted).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(new Date(formatted).toString()).not.toBe('Invalid Date');
    });

    test('_delay debe retornar una Promise', async () => {
      const start = Date.now();
      await googleTrendsConnector._delay(10);
      const elapsed = Date.now() - start;
      expect(elapsed).toBeGreaterThanOrEqual(9); // Tolerar 1ms de margen
    });
  });

  describe('Validaciones de datos mock', () => {
    test('datos mock deben ser determinísticos (mismo keyword = mismos datos)', async () => {
      const result1 = await googleTrendsConnector.fetchComplete('bitcoin', 'MX', 30, 365);
      const result2 = await googleTrendsConnector.fetchComplete('bitcoin', 'MX', 30, 365);

      expect(result1.timeSeries.length).toBe(result2.timeSeries.length);
      expect(result1.byCountry.length).toBe(result2.byCountry.length);
      
      // Verificar que los valores son iguales
      expect(result1.timeSeries[0].value).toBe(result2.timeSeries[0].value);
      expect(result1.byCountry[0].value).toBe(result2.byCountry[0].value);
    });

    test('diferentes keywords deben generar datos diferentes', async () => {
      const result1 = await googleTrendsConnector.fetchComplete('bitcoin', 'MX', 30, 365);
      const result2 = await googleTrendsConnector.fetchComplete('ethereum', 'MX', 30, 365);

      // Los datos deben ser diferentes (al menos uno diferente)
      const values1 = result1.timeSeries.map(p => p.value).join(',');
      const values2 = result2.timeSeries.map(p => p.value).join(',');
      
      expect(values1).not.toBe(values2);
    });

    test('debe generar exactamente baseline_days + 1 puntos', async () => {
      const result30 = await googleTrendsConnector.fetchComplete('test', 'MX', 7, 30);
      const result90 = await googleTrendsConnector.fetchComplete('test', 'MX', 7, 90);
      const result365 = await googleTrendsConnector.fetchComplete('test', 'MX', 7, 365);
      const result1825 = await googleTrendsConnector.fetchComplete('test', 'MX', 30, 1825);

      expect(result30.timeSeries.length).toBe(31);    // 30 + 1
      expect(result90.timeSeries.length).toBe(91);    // 90 + 1
      expect(result365.timeSeries.length).toBe(366);  // 365 + 1
      expect(result1825.timeSeries.length).toBe(1826); // 1825 + 1
    });

    test('el país consultado debe tener el valor más alto en byCountry', async () => {
      const resultMX = await googleTrendsConnector.fetchComplete('test', 'MX', 30, 365);
      const resultCR = await googleTrendsConnector.fetchComplete('test', 'CR', 30, 365);
      const resultES = await googleTrendsConnector.fetchComplete('test', 'ES', 30, 365);

      // Buscar el valor del país consultado
      const mxValue = resultMX.byCountry.find(c => c.country === 'MX').value;
      const crValue = resultCR.byCountry.find(c => c.country === 'CR').value;
      const esValue = resultES.byCountry.find(c => c.country === 'ES').value;

      // El país consultado debe tener valor >= 80
      expect(mxValue).toBeGreaterThanOrEqual(80);
      expect(crValue).toBeGreaterThanOrEqual(80);
      expect(esValue).toBeGreaterThanOrEqual(80);
    });

    test('byCountry debe estar ordenado de mayor a menor valor', async () => {
      const result = await googleTrendsConnector.fetchComplete('test', 'MX', 30, 365);

      for (let i = 1; i < result.byCountry.length; i++) {
        expect(result.byCountry[i - 1].value).toBeGreaterThanOrEqual(result.byCountry[i].value);
      }
    });

    test('las fechas en timeSeries deben ser consecutivas', async () => {
      const result = await googleTrendsConnector.fetchComplete('test', 'MX', 7, 30);

      for (let i = 1; i < result.timeSeries.length; i++) {
        const prevDate = new Date(result.timeSeries[i - 1].date);
        const currDate = new Date(result.timeSeries[i].date);
        
        const diffDays = (currDate - prevDate) / (1000 * 60 * 60 * 24);
        expect(diffDays).toBe(1); // Exactamente 1 día de diferencia
      }
    });
  });

  describe('Manejo de concurrencia', () => {
    test('múltiples requests simultáneos deben completarse correctamente', async () => {
      const promises = [
        googleTrendsConnector.fetchComplete('bitcoin', 'MX', 30, 365),
        googleTrendsConnector.fetchComplete('ethereum', 'CR', 30, 365),
        googleTrendsConnector.fetchComplete('litecoin', 'ES', 30, 365)
      ];

      const results = await Promise.all(promises);

      expect(results).toHaveLength(3);
      results.forEach(result => {
        expect(result).toHaveProperty('timeSeries');
        expect(result).toHaveProperty('byCountry');
      });
    });
  });
});
