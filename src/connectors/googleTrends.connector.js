import googleTrends from 'google-trends-api';
import logger from '../utils/logger.js';
import { getDateRange } from '../utils/dates.js';

/**
 * Detectar si estamos en modo test
 */
const IS_TEST_MODE = process.env.NODE_ENV === 'test';

/**
 * Mock data generator para tests (evita llamadas a Google Trends API)
 */
function generateMockTimeSeries(keyword, baselineDays) {
  const totalDays = baselineDays + 1;
  const series = [];
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - baselineDays);

  const seed = keyword.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  
  for (let i = 0; i < totalDays; i++) {
    const date = new Date(startDate);
    date.setDate(date.getDate() + i);
    
    const dayOffset = i / totalDays;
    const baseValue = 30 + (seed % 40);
    const trend = Math.sin(dayOffset * Math.PI * 4) * 20;
    const noise = ((seed * (i + 1)) % 30) - 15;
    
    const value = Math.max(0, Math.min(100, Math.round(baseValue + trend + noise)));
    
    series.push({
      date: date.toISOString().split('T')[0],
      value
    });
  }

  return series;
}

function generateMockByCountry(keyword, country) {
  const seed = keyword.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const countries = ['MX', 'CR', 'ES'];
  
  return countries.map(countryCode => {
    let value;
    if (countryCode === country) {
      value = 80 + (seed % 21);
    } else {
      const offset = countryCode.charCodeAt(0) + countryCode.charCodeAt(1);
      value = Math.max(0, Math.min(79, (seed + offset) % 80));
    }
    
    return { country: countryCode, value };
  }).sort((a, b) => b.value - a.value);
}

/**
 * Google Trends Connector - REAL API IMPLEMENTATION
 * 
 * Uses google-trends-api npm package to fetch real data from Google Trends.
 * 
 * IMPORTANT: Google may block requests if:
 * - Too many requests in short time (rate limiting)
 * - Unusual traffic patterns detected
 * 
 * Recommendations:
 * - Use delays between requests (2-5 seconds)
 * - Implement exponential backoff on errors
 * - Consider caching results for 12-24 hours
 * - For high-volume production, use SerpAPI instead
 * 
 * TEST MODE: When NODE_ENV=test, returns mock data instead of calling Google API
 */
class GoogleTrendsConnector {
  constructor() {
    this.maxRetries = parseInt(process.env.GOOGLE_TRENDS_MAX_RETRIES || '3', 10);
    this.retryDelay = parseInt(process.env.GOOGLE_TRENDS_RETRY_DELAY_MS || '5000', 10);
    this.requestDelay = parseInt(process.env.GOOGLE_TRENDS_REQUEST_DELAY_MS || '4000', 10);
    this.concurrency = parseInt(process.env.GOOGLE_TRENDS_CONCURRENCY || '1', 10);
    
    // Lock para garantizar concurrencia 1
    this.requestLock = null;
    this.lockQueue = [];
    
    if (IS_TEST_MODE) {
      logger.info('🧪 Google Trends Connector - MOCK MODE (No API calls will be made)');
    } else {
      logger.info({ 
        maxRetries: this.maxRetries,
        retryDelay: this.retryDelay,
        requestDelay: this.requestDelay,
        concurrency: this.concurrency
      }, 'Google Trends Connector initialized with REAL API - MVP Configuration');
    }
  }

  /**
   * Fetch complete trend data: time series + regional comparison
   */
  async fetchComplete(keyword, country, windowDays, baselineDays) {
    // Si estamos en modo test, retornar mock data inmediatamente
    if (IS_TEST_MODE) {
      await new Promise(resolve => setTimeout(resolve, 5)); // Simular delay mínimo
      return {
        timeSeries: generateMockTimeSeries(keyword, baselineDays),
        byCountry: generateMockByCountry(keyword, country)
      };
    }

    // Adquirir lock antes de hacer request
    await this._acquireLock();

    try {
      logger.info({ keyword, country, windowDays, baselineDays }, 
        'Fetching complete trend data from Google Trends API');

      const { startDate, endDate } = getDateRange(windowDays, baselineDays);

      // Fetch time series with retry logic
      const timeSeries = await this._fetchWithRetry(() =>
        this._fetchTimeSeries(keyword, country, startDate, endDate)
      );

      // Add delay before second request to avoid rate limiting
      await this._delay(this.requestDelay);

      // Fetch country comparison (global view - last 12 months)
      const byCountry = await this._fetchWithRetry(() =>
        this._fetchByCountry(keyword)
      );

      logger.info({ keyword, country, dataPoints: timeSeries.length }, 
        'Successfully fetched Google Trends data');

      return {
        timeSeries,
        byCountry,
        source: 'google_trends',
        fetchedAt: new Date().toISOString()
      };
    } catch (error) {
      logger.error({ error: error.message, keyword, country }, 
        'Failed to fetch Google Trends data');
      throw error;
    } finally {
      // Siempre liberar el lock
      this._releaseLock();
    }
  }

  /**
   * Fetch time series data for a keyword in a specific country
   */
  async _fetchTimeSeries(keyword, country, startDate, endDate) {
    logger.info({ keyword, country, startDate, endDate }, 
      'Fetching time series from Google Trends');

    const results = await googleTrends.interestOverTime({
      keyword,
      startTime: new Date(startDate),
      endTime: new Date(endDate),
      geo: country
    });

    const parsed = JSON.parse(results);

    if (!parsed.default || !parsed.default.timelineData) {
      throw new Error('Invalid response format from Google Trends');
    }

    // Transform Google Trends format to our format
    const timeSeries = parsed.default.timelineData.map(point => ({
      date: this._formatTimestamp(point.time),
      value: point.value[0] || 0
    }));

    logger.info({ keyword, country, dataPoints: timeSeries.length }, 
      'Time series fetched successfully');

    return timeSeries;
  }

  /**
   * Fetch regional comparison for a keyword across MX, CR, ES
   * Note: Uses last 12 months (Google Trends default) for global comparison
   * This is intentionally different from time series date range
   */
  async _fetchByCountry(keyword) {
    logger.info({ keyword }, 'Fetching country comparison from Google Trends');

    try {
      // Single request for all countries (more efficient, less likely to be blocked)
      const data = await googleTrends.interestByRegion({
        keyword,
        startTime: new Date(Date.now() - 365 * 24 * 60 * 60 * 1000), // Last year
        resolution: 'COUNTRY'
        // No geo parameter = global comparison
      });

      const parsed = JSON.parse(data);
      const results = [];

      // Extract values for our target countries
      const targetCountries = ['MX', 'CR', 'ES'];
      
      if (parsed.default && parsed.default.geoMapData) {
        for (const countryCode of targetCountries) {
          const countryData = parsed.default.geoMapData.find(d => d.geoCode === countryCode);
          const value = countryData?.value?.[0] || 0;
          
          results.push({
            country: countryCode,
            value
          });

          logger.info({ country: countryCode, value }, 
            'Country data extracted successfully');
        }
      } else {
        // Fallback: return zeros if no data
        logger.warn('No geoMapData found, using zeros');
        targetCountries.forEach(code => {
          results.push({ country: code, value: 0 });
        });
      }

      // Sort by value descending
      results.sort((a, b) => b.value - a.value);

      logger.info({ keyword, countries: results.length }, 
        'Country comparison fetched successfully');

      return results;
    } catch (error) {
      logger.error({ error: error.message, keyword }, 
        'Failed to fetch country comparison');
      
      // Return zeros on error
      return ['MX', 'CR', 'ES'].map(code => ({ country: code, value: 0 }));
    }
  }

  /**
   * Wrapper for fetchByCountry to maintain API compatibility
   */
  async fetchByCountry(keyword) {
    return this._fetchByCountry(keyword);
  }

  /**
   * Retry wrapper with exponential backoff
   */
  async _fetchWithRetry(fn) {
    let lastError;

    for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error;
        
        // Detectar si Google devolvió HTML (bloqueo anti-bot)
        const isBlocked = error.message && (
          error.message.includes('Unexpected token') ||
          error.message.includes('is not valid JSON') ||
          error.message.includes('html') ||
          error.message.includes('DOCTYPE')
        );

        logger.warn({ 
          attempt, 
          maxRetries: this.maxRetries,
          error: error.message,
          isBlocked,
          nextDelay: attempt < this.maxRetries ? this.retryDelay * Math.pow(2, attempt - 1) : 0
        }, isBlocked ? 'Google blocked request (returned HTML), retrying...' : 'Request failed, retrying...');

        if (attempt < this.maxRetries) {
          // Exponential backoff: 5s, 10s, 20s
          const delay = this.retryDelay * Math.pow(2, attempt - 1);
          
          // Si fue bloqueado, agregar delay extra
          const extraDelay = isBlocked ? 3000 : 0;
          
          await this._delay(delay + extraDelay);
        }
      }
    }

    throw new Error(`Failed after ${this.maxRetries} attempts: ${lastError.message}`);
  }

  /**
   * Delay helper
   */
  _delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Adquirir lock para garantizar concurrencia 1
   */
  async _acquireLock() {
    return new Promise((resolve) => {
      if (!this.requestLock) {
        // No hay lock activo, adquirir inmediatamente
        this.requestLock = true;
        logger.debug('Lock acquired');
        resolve();
      } else {
        // Ya hay un request en curso, agregar a la cola
        logger.debug({ queueLength: this.lockQueue.length }, 'Waiting for lock...');
        this.lockQueue.push(resolve);
      }
    });
  }

  /**
   * Liberar lock y procesar siguiente en cola
   */
  _releaseLock() {
    if (this.lockQueue.length > 0) {
      // Hay requests esperando, dar lock al siguiente
      const next = this.lockQueue.shift();
      logger.debug({ remainingInQueue: this.lockQueue.length }, 'Lock passed to next in queue');
      next();
    } else {
      // No hay nadie esperando, liberar completamente
      this.requestLock = null;
      logger.debug('Lock released');
    }
  }

  /**
   * Format Google Trends timestamp to YYYY-MM-DD
   */
  _formatTimestamp(timestamp) {
    // Google Trends returns timestamps in seconds (sometimes as string)
    const ts = typeof timestamp === 'string' ? parseInt(timestamp) : timestamp;
    const date = new Date(ts * 1000);
    return date.toISOString().split('T')[0];
  }
}

export default new GoogleTrendsConnector();
