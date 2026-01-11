/**
 * Mock de Google Trends API para tests
 * Evita llamadas reales a la API durante los tests
 */

/**
 * Genera datos de series temporales mock
 */
export function generateMockTimeSeries(keyword, country, windowDays, baselineDays) {
  const totalDays = baselineDays + 1; // +1 para incluir día actual
  const series = [];
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - baselineDays);

  // Generar patrón determinístico basado en keyword
  const seed = keyword.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  
  for (let i = 0; i < totalDays; i++) {
    const date = new Date(startDate);
    date.setDate(date.getDate() + i);
    
    // Generar valor pseudo-aleatorio pero determinístico
    const dayOffset = i / totalDays;
    const baseValue = 30 + (seed % 40);
    const trend = Math.sin(dayOffset * Math.PI * 4) * 20; // Onda senoidal
    const noise = ((seed * (i + 1)) % 30) - 15; // Ruido determinístico
    
    const value = Math.max(0, Math.min(100, Math.round(baseValue + trend + noise)));
    
    series.push({
      date: date.toISOString().split('T')[0],
      value
    });
  }

  return series;
}

/**
 * Genera datos de comparación por país mock
 */
export function generateMockByCountry(keyword, country) {
  const seed = keyword.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  
  // El país consultado siempre tiene valor alto (80-100)
  const countries = ['MX', 'CR', 'ES'];
  
  return countries.map(countryCode => {
    let value;
    if (countryCode === country) {
      // País consultado: 80-100
      value = 80 + (seed % 21);
    } else {
      // Otros países: valores más bajos pero determinísticos
      const offset = countryCode.charCodeAt(0) + countryCode.charCodeAt(1);
      value = Math.max(0, Math.min(79, (seed + offset) % 80));
    }
    
    return {
      country: countryCode,
      value
    };
  }).sort((a, b) => b.value - a.value); // Ordenar por valor descendente
}

/**
 * Mock completo del connector de Google Trends
 */
export const mockGoogleTrendsConnector = {
  /**
   * Fetch completo (timeSeries + byCountry)
   */
  fetchComplete: jest.fn(async (keyword, country, windowDays, baselineDays) => {
    // Simular delay de red
    await new Promise(resolve => setTimeout(resolve, 10));
    
    const timeSeries = generateMockTimeSeries(keyword, country, windowDays, baselineDays);
    const byCountry = generateMockByCountry(keyword, country);
    
    return {
      timeSeries,
      byCountry
    };
  }),

  /**
   * Fetch solo time series
   */
  _fetchTimeSeries: jest.fn(async (keyword, country, windowDays, baselineDays) => {
    await new Promise(resolve => setTimeout(resolve, 10));
    return generateMockTimeSeries(keyword, country, windowDays, baselineDays);
  }),

  /**
   * Fetch solo by country
   */
  _fetchByCountry: jest.fn(async (keyword, country) => {
    await new Promise(resolve => setTimeout(resolve, 10));
    return generateMockByCountry(keyword, country);
  })
};

/**
 * Factory para crear un nuevo mock (útil para resetear entre tests)
 */
export function createMockGoogleTrendsConnector() {
  return {
    fetchComplete: jest.fn(async (keyword, country, windowDays, baselineDays) => {
      await new Promise(resolve => setTimeout(resolve, 10));
      return {
        timeSeries: generateMockTimeSeries(keyword, country, windowDays, baselineDays),
        byCountry: generateMockByCountry(keyword, country)
      };
    }),
    
    _fetchTimeSeries: jest.fn(async (keyword, country, windowDays, baselineDays) => {
      await new Promise(resolve => setTimeout(resolve, 10));
      return generateMockTimeSeries(keyword, country, windowDays, baselineDays);
    }),
    
    _fetchByCountry: jest.fn(async (keyword, country) => {
      await new Promise(resolve => setTimeout(resolve, 10));
      return generateMockByCountry(keyword, country);
    })
  };
}

export default mockGoogleTrendsConnector;
