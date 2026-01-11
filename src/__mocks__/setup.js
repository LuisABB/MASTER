/**
 * Setup global para tests
 * Mockea Google Trends Connector para TODOS los tests
 */

import { jest } from '@jest/globals';
import { generateMockTimeSeries, generateMockByCountry } from './googleTrends.mock.js';

// Mock global del googleTrends connector
jest.unstable_mockModule('../connectors/googleTrends.connector.js', () => ({
  default: {
    fetchComplete: jest.fn(async (keyword, country, windowDays, baselineDays) => {
      return {
        timeSeries: generateMockTimeSeries(keyword, country, windowDays, baselineDays),
        byCountry: generateMockByCountry(keyword, country)
      };
    }),
    
    _fetchTimeSeries: jest.fn(async (keyword, country, windowDays, baselineDays) => {
      return generateMockTimeSeries(keyword, country, windowDays, baselineDays);
    }),
    
    _fetchByCountry: jest.fn(async (keyword, country) => {
      return generateMockByCountry(keyword, country);
    }),
    
    fetchByCountry: jest.fn(async (keyword) => {
      return generateMockByCountry(keyword, 'MX');
    })
  }
}));

console.log('✅ Google Trends Connector mockeado - No se harán llamadas reales a la API');
