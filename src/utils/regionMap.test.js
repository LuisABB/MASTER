import { describe, test, expect } from '@jest/globals';
import { isRegionSupported, getSupportedRegions } from './regionMap.js';

describe('Utils: regionMap.js', () => {
  describe('isRegionSupported', () => {
    test('debe retornar true para regiones válidas de México', () => {
      const validRegions = [
        'MX-CMX', // Ciudad de México
        'MX-JAL', // Jalisco
        'MX-NLE', // Nuevo León
        'MX-PUE', // Puebla
        'MX-GUA', // Guanajuato
      ];

      validRegions.forEach(region => {
        expect(isRegionSupported(region)).toBe(true);
      });
    });

    test('debe retornar false para regiones inválidas', () => {
      const invalidRegions = [
        'US-CA',    // California, USA
        'MX-XXX',   // Código inexistente
        'CDMX',     // Formato incorrecto
        'Mexico',   // Nombre completo
        '',         // Vacío
        null,       // Null
        undefined   // Undefined
      ];

      invalidRegions.forEach(region => {
        expect(isRegionSupported(region)).toBe(false);
      });
    });

    test('debe ser case-sensitive', () => {
      expect(isRegionSupported('mx-cmx')).toBe(false); // minúsculas
      expect(isRegionSupported('MX-CMX')).toBe(true);  // mayúsculas
    });

    test('debe validar todos los 15 estados mexicanos', () => {
      const allMexicanStates = [
        'MX-CMX', 'MX-JAL', 'MX-NLE', 'MX-PUE', 'MX-GUA',
        'MX-VER', 'MX-CHH', 'MX-BCN', 'MX-SON', 'MX-TAM',
        'MX-SIN', 'MX-COA', 'MX-QUE', 'MX-YUC', 'MX-MEX'
      ];

      allMexicanStates.forEach(region => {
        expect(isRegionSupported(region)).toBe(true);
      });

      expect(allMexicanStates.length).toBe(15);
    });
  });

  describe('getSupportedRegions', () => {
    test('debe retornar array de 15 regiones', () => {
      const regions = getSupportedRegions();
      
      expect(Array.isArray(regions)).toBe(true);
      expect(regions.length).toBe(15);
    });

    test('cada región debe tener code y name', () => {
      const regions = getSupportedRegions();
      
      regions.forEach(region => {
        expect(region).toHaveProperty('code');
        expect(region).toHaveProperty('name');
        expect(typeof region.code).toBe('string');
        expect(typeof region.name).toBe('string');
        expect(region.code).toMatch(/^MX-[A-Z]{3}$/); // Formato MX-XXX
        expect(region.name.length).toBeGreaterThan(0);
      });
    });

    test('códigos deben ser únicos', () => {
      const regions = getSupportedRegions();
      const codes = regions.map(r => r.code);
      const uniqueCodes = new Set(codes);
      
      expect(uniqueCodes.size).toBe(codes.length);
    });

    test('nombres deben ser únicos', () => {
      const regions = getSupportedRegions();
      const names = regions.map(r => r.name);
      const uniqueNames = new Set(names);
      
      expect(uniqueNames.size).toBe(names.length);
    });

    test('debe incluir las regiones principales', () => {
      const regions = getSupportedRegions();
      const codes = regions.map(r => r.code);
      
      expect(codes).toContain('MX-CMX'); // Ciudad de México
      expect(codes).toContain('MX-JAL'); // Jalisco
      expect(codes).toContain('MX-NLE'); // Nuevo León
    });

    test('Ciudad de México debe tener nombre correcto', () => {
      const regions = getSupportedRegions();
      const cdmx = regions.find(r => r.code === 'MX-CMX');
      
      expect(cdmx).toBeDefined();
      expect(cdmx.name).toBe('Ciudad de México');
    });
  });
});
