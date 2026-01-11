import { describe, test, expect } from '@jest/globals';
import { isCountrySupported, getSupportedCountries, isRegionSupported, getSupportedRegions } from './regionMap.js';

describe('Utils: regionMap.js', () => {
  describe('isCountrySupported', () => {
    test('debe retornar true para países válidos', () => {
      const validCountries = ['MX', 'CR', 'ES'];

      validCountries.forEach(country => {
        expect(isCountrySupported(country)).toBe(true);
      });
    });

    test('debe retornar false para países inválidos', () => {
      const invalidCountries = [
        'US',       // USA (no soportado)
        'AR',       // Argentina (no soportado)
        'CO',       // Colombia (no soportado)
        'MX-CMX',   // Código de estado (viejo formato)
        'Mexico',   // Nombre completo
        '',         // Vacío
        null,       // Null
        undefined   // Undefined
      ];

      invalidCountries.forEach(country => {
        expect(isCountrySupported(country)).toBe(false);
      });
    });

    test('debe ser case-sensitive', () => {
      expect(isCountrySupported('mx')).toBe(false); // minúsculas
      expect(isCountrySupported('MX')).toBe(true);  // mayúsculas
      expect(isCountrySupported('Mx')).toBe(false); // mixtas
    });

    test('debe validar los 3 países soportados', () => {
      const allSupportedCountries = ['MX', 'CR', 'ES'];

      allSupportedCountries.forEach(country => {
        expect(isCountrySupported(country)).toBe(true);
      });

      expect(allSupportedCountries.length).toBe(3);
    });
  });

  describe('getSupportedCountries', () => {
    test('debe retornar array de 3 países', () => {
      const countries = getSupportedCountries();
      
      expect(Array.isArray(countries)).toBe(true);
      expect(countries.length).toBe(3);
    });

    test('cada país debe tener code y name', () => {
      const countries = getSupportedCountries();
      
      countries.forEach(country => {
        expect(country).toHaveProperty('code');
        expect(country).toHaveProperty('name');
        expect(typeof country.code).toBe('string');
        expect(typeof country.name).toBe('string');
        expect(country.code).toMatch(/^[A-Z]{2}$/); // Formato ISO 2 letras
        expect(country.name.length).toBeGreaterThan(0);
      });
    });

    test('códigos deben ser únicos', () => {
      const countries = getSupportedCountries();
      const codes = countries.map(c => c.code);
      const uniqueCodes = new Set(codes);
      
      expect(uniqueCodes.size).toBe(codes.length);
    });

    test('nombres deben ser únicos', () => {
      const countries = getSupportedCountries();
      const names = countries.map(c => c.name);
      const uniqueNames = new Set(names);
      
      expect(uniqueNames.size).toBe(names.length);
    });

    test('debe incluir los 3 países correctos', () => {
      const countries = getSupportedCountries();
      const codes = countries.map(c => c.code);
      
      expect(codes).toContain('MX'); // México
      expect(codes).toContain('CR'); // Costa Rica
      expect(codes).toContain('ES'); // España
    });

    test('México debe tener nombre correcto', () => {
      const countries = getSupportedCountries();
      const mexico = countries.find(c => c.code === 'MX');
      
      expect(mexico).toBeDefined();
      expect(mexico.name).toBe('México');
    });

    test('Costa Rica debe tener nombre correcto', () => {
      const countries = getSupportedCountries();
      const costaRica = countries.find(c => c.code === 'CR');
      
      expect(costaRica).toBeDefined();
      expect(costaRica.name).toBe('Costa Rica');
    });

    test('España debe tener nombre correcto', () => {
      const countries = getSupportedCountries();
      const spain = countries.find(c => c.code === 'ES');
      
      expect(spain).toBeDefined();
      expect(spain.name).toBe('España');
    });
  });

  describe('Aliases de retrocompatibilidad', () => {
    test('isRegionSupported debe funcionar como alias', () => {
      expect(isRegionSupported('MX')).toBe(true);
      expect(isRegionSupported('US')).toBe(false);
    });

    test('getSupportedRegions debe funcionar como alias', () => {
      const regions = getSupportedRegions();
      
      expect(Array.isArray(regions)).toBe(true);
      expect(regions.length).toBe(3);
      expect(regions[0]).toHaveProperty('code');
      expect(regions[0]).toHaveProperty('name');
    });
  });
});

