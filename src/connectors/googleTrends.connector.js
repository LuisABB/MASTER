import logger from '../utils/logger.js';
import { getDateRange } from '../utils/dates.js';

/**
 * Google Trends Connector - MOCK DATA IMPLEMENTATION
 * 
 * NOTE: This is a mock implementation for testing purposes.
 * Google Trends API has anti-bot protections that require browser-like requests.
 * 
 * For production, consider:
 * - SerpAPI (https://serpapi.com) - $50/month for 5k searches
 * - Python microservice with pytrends library
 * - Puppeteer-based scraping service
 */
class GoogleTrendsConnector {
  constructor() {
    this.maxRetries = parseInt(process.env.GOOGLE_TRENDS_MAX_RETRIES || '3', 10);
    this.retryDelay = parseInt(process.env.GOOGLE_TRENDS_RETRY_DELAY_MS || '2000', 10);
    
    logger.warn('Google Trends Connector initialized with MOCK DATA. See connector for production options.');
  }

  /**
   * Generate realistic time series data
   * Creates a trend curve with growth, peak, and decline patterns
   */
  _generateTimeSeries(keyword, startDate, endDate) {
    const timeSeries = [];
    const start = new Date(startDate);
    const end = new Date(endDate);
    const daysDiff = Math.ceil((end - start) / (1000 * 60 * 60 * 24));
    
    // Seed random number generator based on keyword for consistency
    let seed = 0;
    for (let i = 0; i < keyword.length; i++) {
      seed += keyword.charCodeAt(i);
    }
    
    // Random generator with seed
    const seededRandom = (min = 0, max = 1) => {
      seed = (seed * 9301 + 49297) % 233280;
      const rnd = seed / 233280;
      return min + rnd * (max - min);
    };

    // Generate trend parameters
    const baseValue = Math.floor(seededRandom(20, 40));
    const peakDay = Math.floor(daysDiff * seededRandom(0.3, 0.7)); // Peak somewhere in middle
    const peakValue = Math.floor(seededRandom(70, 100));
    const growthRate = (peakValue - baseValue) / peakDay;
    const declineRate = (peakValue - baseValue) / (daysDiff - peakDay);

    for (let i = 0; i <= daysDiff; i++) {
      const currentDate = new Date(start);
      currentDate.setDate(start.getDate() + i);
      
      let value;
      if (i < peakDay) {
        // Growth phase
        value = baseValue + (growthRate * i);
      } else {
        // Decline phase
        value = peakValue - (declineRate * (i - peakDay));
      }
      
      // Add noise (±10%)
      const noise = seededRandom(-value * 0.1, value * 0.1);
      value = Math.max(0, Math.min(100, Math.round(value + noise)));
      
      timeSeries.push({
        date: currentDate.toISOString().split('T')[0],
        value
      });
    }

    return timeSeries;
  }

  /**
   * Generate regional data for Mexican states
   */
  _generateRegionalData(keyword) {
    const mexicanRegions = [
      'MX-CMX', 'MX-JAL', 'MX-NLE', 'MX-PUE', 'MX-GUA',
      'MX-CHH', 'MX-TAM', 'MX-BCN', 'MX-VER', 'MX-SON',
      'MX-COA', 'MX-SIN', 'MX-MIC', 'MX-OAX', 'MX-QUE'
    ];

    // Seed for consistency
    let seed = 0;
    for (let i = 0; i < keyword.length; i++) {
      seed += keyword.charCodeAt(i);
    }
    
    const seededRandom = (min = 0, max = 1) => {
      seed = (seed * 9301 + 49297) % 233280;
      return min + (seed / 233280) * (max - min);
    };

    return mexicanRegions.map(region => ({
      region,
      value: Math.floor(seededRandom(10, 100))
    })).sort((a, b) => b.value - a.value); // Sort by value descending
  }

  /**
   * Fetch interest over time for a keyword (MOCK)
   */
  async fetchTimeSeries(keyword, region, windowDays, baselineDays) {
    const { startDate, endDate } = getDateRange(windowDays, baselineDays);
    
    logger.info({ 
      keyword, 
      region, 
      startDate, 
      endDate,
      mode: 'MOCK' 
    }, 'Generating mock Google Trends time series');

    // Simulate API delay
    await this._sleep(this.seededRandom(keyword, 300, 800));

    const timeSeries = this._generateTimeSeries(keyword, startDate, endDate);
    
    logger.info({ 
      keyword, 
      region, 
      dataPoints: timeSeries.length,
      mode: 'MOCK'
    }, 'Successfully generated mock time series');

    return timeSeries;
  }

  /**
   * Fetch interest by region for a keyword (MOCK)
   */
  async fetchByRegion(keyword, country, windowDays, baselineDays) {
    const { startDate, endDate } = getDateRange(windowDays, baselineDays);
    
    logger.info({ 
      keyword, 
      country, 
      startDate, 
      endDate,
      mode: 'MOCK'
    }, 'Generating mock Google Trends regional data');

    // Simulate API delay
    await this._sleep(this.seededRandom(keyword, 300, 800));

    const regionalData = this._generateRegionalData(keyword);
    
    logger.info({ 
      keyword, 
      country, 
      regions: regionalData.length,
      mode: 'MOCK'
    }, 'Successfully generated mock regional data');

    return regionalData;
  }

  /**
   * Fetch both time series and regional data (MOCK)
   */
  async fetchComplete(keyword, region, windowDays, baselineDays) {
    try {
      // Fetch both in parallel
      const [timeSeries, byRegion] = await Promise.all([
        this.fetchTimeSeries(keyword, region, windowDays, baselineDays),
        this.fetchByRegion(keyword, 'MX', windowDays, baselineDays)
      ]);

      return {
        timeSeries,
        byRegion,
        source: 'mock_data', // Changed from 'google_trends'
        fetchedAt: new Date().toISOString()
      };
    } catch (error) {
      logger.error({ error, keyword, region }, 'Failed to generate mock Google Trends data');
      throw error;
    }
  }

  /**
   * Seeded random helper for consistent mock data
   */
  seededRandom(keyword, min = 0, max = 1) {
    let seed = 0;
    for (let i = 0; i < keyword.length; i++) {
      seed += keyword.charCodeAt(i);
    }
    seed = (seed * 9301 + 49297) % 233280;
    const rnd = seed / 233280;
    return min + rnd * (max - min);
  }

  /**
   * Sleep helper
   */
  _sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

export default new GoogleTrendsConnector();
