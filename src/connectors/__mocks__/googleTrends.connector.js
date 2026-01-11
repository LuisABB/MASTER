/**
 * Mock automático de Google Trends Connector
 * Jest usa este archivo automáticamente cuando se importa googleTrends.connector.js
 * 
 * Ubicación: src/connectors/__mocks__/googleTrends.connector.js
 * Mockea: src/connectors/googleTrends.connector.js
 */

import { generateMockTimeSeries, generateMockByCountry } from '../../__mocks__/googleTrends.mock.js';

const googleTrendsConnector = {
  /**
   * Fetch completo (timeSeries + byCountry)
   */
  fetchComplete: async (keyword, country, windowDays, baselineDays) => {
    // Simular delay de red (muy pequeño para tests)
    await new Promise(resolve => setTimeout(resolve, 5));
    
    return {
      timeSeries: generateMockTimeSeries(keyword, country, windowDays, baselineDays),
      byCountry: generateMockByCountry(keyword, country)
    };
  },

  /**
   * Fetch solo time series
   */
  _fetchTimeSeries: async (keyword, country, windowDays, baselineDays) => {
    await new Promise(resolve => setTimeout(resolve, 5));
    return generateMockTimeSeries(keyword, country, windowDays, baselineDays);
  },

  /**
   * Fetch solo by country
   */
  _fetchByCountry: async (keyword, country) => {
    await new Promise(resolve => setTimeout(resolve, 5));
    return generateMockByCountry(keyword, country);
  },

  /**
   * Fetch by country (alias)
   */
  fetchByCountry: async (keyword) => {
    await new Promise(resolve => setTimeout(resolve, 5));
    return generateMockByCountry(keyword, 'MX');
  }
};

export default googleTrendsConnector;
