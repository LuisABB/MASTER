import { clamp, average, max } from '../utils/normalize.js';
import logger from '../utils/logger.js';

/**
 * Scoring Service
 * Calculates trend score and generates explanations
 */
class ScoringService {
  /**
   * Calculate trend score and signals from time series data
   */
  calculateScore(timeSeries, keyword, region) {
    if (!timeSeries || timeSeries.length === 0) {
      throw new Error('Time series data is empty');
    }

    logger.info({ 
      keyword, 
      region, 
      dataPoints: timeSeries.length 
    }, 'Calculating trend score');

    // Extract values only
    const values = timeSeries.map(point => point.value);

    // Calculate signals
    const signals = {
      growth_7_vs_30: this._calculateGrowth7vs30(values),
      slope_14d: this._calculateSlope14d(values),
      recent_peak_30d: this._calculateRecentPeak30d(values)
    };

    // Calculate final score (0-100)
    const trendScore = this._calculateFinalScore(signals);

    // Generate explanations
    const explain = this._generateExplanations(signals, keyword, region);

    logger.info({ 
      keyword, 
      region, 
      trendScore, 
      signals 
    }, 'Trend score calculated');

    return {
      trendScore: parseFloat(trendScore.toFixed(2)),
      signals: {
        growth_7_vs_30: parseFloat(signals.growth_7_vs_30.toFixed(2)),
        slope_14d: parseFloat(signals.slope_14d.toFixed(4)),
        recent_peak_30d: parseFloat(signals.recent_peak_30d.toFixed(2))
      },
      explain
    };
  }

  /**
   * Calculate growth: avg(last 7 days) / avg(last 30 days)
   */
  _calculateGrowth7vs30(values) {
    const last7 = values.slice(-7);
    const last30 = values.slice(-30);

    if (last7.length === 0 || last30.length === 0) {
      return 1.0; // Neutral if not enough data
    }

    const avg7 = average(last7);
    const avg30 = average(last30);

    // Avoid division by zero
    return avg30 > 0 ? avg7 / avg30 : 1.0;
  }

  /**
   * Calculate slope of last 14 days using linear regression
   */
  _calculateSlope14d(values) {
    const last14 = values.slice(-14);

    if (last14.length < 2) {
      return 0; // Not enough data for slope
    }

    const n = last14.length;
    const x = Array.from({ length: n }, (_, i) => i); // [0, 1, 2, ..., n-1]
    const y = last14;

    // Calculate means
    const meanX = average(x);
    const meanY = average(y);

    // Calculate slope: Σ((x - meanX) * (y - meanY)) / Σ((x - meanX)²)
    let numerator = 0;
    let denominator = 0;

    for (let i = 0; i < n; i++) {
      const dx = x[i] - meanX;
      const dy = y[i] - meanY;
      numerator += dx * dy;
      denominator += dx * dx;
    }

    if (denominator === 0) {
      return 0;
    }

    // Normalize slope by dividing by mean value to make it scale-independent
    const slope = numerator / denominator;
    const normalizedSlope = meanY > 0 ? slope / meanY : slope;

    return normalizedSlope;
  }

  /**
   * Calculate recent peak: max(last 30 days) / 100
   */
  _calculateRecentPeak30d(values) {
    const last30 = values.slice(-30);

    if (last30.length === 0) {
      return 0;
    }

    const maxValue = max(last30);
    return maxValue / 100.0; // Normalize to 0-1 (Google Trends is 0-100)
  }

  /**
   * Calculate final trend score (0-100)
   * Formula: 100 * clamp(0.5*G + 0.3*S + 0.2*P, 0, 1)
   */
  _calculateFinalScore(signals) {
    // Normalize growth to 0-1 range
    // Growth 0.7-1.7 maps to 0-1
    const G = clamp((signals.growth_7_vs_30 - 0.7) / (1.7 - 0.7), 0, 1);

    // Normalize slope to 0-1 range
    // Slope -0.5 to +0.5 maps to 0-1
    const S = clamp((signals.slope_14d + 0.5) / 1.0, 0, 1);

    // Peak is already normalized (0-1)
    const P = signals.recent_peak_30d;

    // Weighted combination
    const score = 0.5 * G + 0.3 * S + 0.2 * P;

    // Scale to 0-100
    return clamp(score, 0, 1) * 100;
  }

  /**
   * Generate human-readable explanations
   */
  _generateExplanations(signals, keyword, region) {
    const explanations = [];

    // Growth explanation
    const growthPercent = ((signals.growth_7_vs_30 - 1) * 100).toFixed(1);
    if (signals.growth_7_vs_30 > 1.1) {
      explanations.push(
        `El interés en los últimos 7 días creció ${Math.abs(growthPercent)}% vs los últimos 30 días.`
      );
    } else if (signals.growth_7_vs_30 < 0.9) {
      explanations.push(
        `El interés en los últimos 7 días cayó ${Math.abs(growthPercent)}% vs los últimos 30 días.`
      );
    } else {
      explanations.push(
        'El interés en los últimos 7 días se mantiene estable respecto a los últimos 30 días.'
      );
    }

    // Slope explanation
    if (signals.slope_14d > 0.01) {
      explanations.push('La tendencia de los últimos 14 días es positiva (creciente).');
    } else if (signals.slope_14d < -0.01) {
      explanations.push('La tendencia de los últimos 14 días es negativa (decreciente).');
    } else {
      explanations.push('La tendencia de los últimos 14 días es plana (sin cambios significativos).');
    }

    // Peak explanation
    if (signals.recent_peak_30d > 0.8) {
      explanations.push(
        `El interés reciente alcanzó ${(signals.recent_peak_30d * 100).toFixed(0)}% del máximo posible.`
      );
    } else if (signals.recent_peak_30d > 0.5) {
      explanations.push(
        `El interés está en niveles moderados (${(signals.recent_peak_30d * 100).toFixed(0)}% del máximo).`
      );
    } else {
      explanations.push(
        `El interés está en niveles bajos (${(signals.recent_peak_30d * 100).toFixed(0)}% del máximo).`
      );
    }

    // Region context
    explanations.push(`Los datos corresponden a la región ${region}.`);

    return explanations;
  }
}

export default new ScoringService();
