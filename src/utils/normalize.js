/**
 * Normalize time series data to standard format
 */
export function normalizeTimeSeries(rawData) {
  if (!Array.isArray(rawData)) {
    return [];
  }

  return rawData
    .filter(point => point && point.value !== undefined)
    .map(point => ({
      date: point.formattedTime || point.date,
      value: parseInt(point.value, 10) || 0
    }))
    .sort((a, b) => new Date(a.date) - new Date(b.date));
}

/**
 * Normalize country comparison data to standard format
 */
export function normalizeRegionalData(rawData) {
  if (!Array.isArray(rawData)) {
    return [];
  }

  return rawData
    .filter(point => point && point.value !== undefined)
    .map(point => ({
      country: point.geoCode || point.country || 'UNKNOWN',
      value: parseInt(point.value, 10) || 0
    }))
    .sort((a, b) => b.value - a.value); // Sort by value descending
}

/**
 * Clamp value between min and max
 */
export function clamp(value, min = 0, max = 1) {
  return Math.max(min, Math.min(max, value));
}

/**
 * Calculate average of array values
 */
export function average(values) {
  if (!values || values.length === 0) return 0;
  const sum = values.reduce((acc, val) => acc + val, 0);
  return sum / values.length;
}

/**
 * Calculate max of array values
 */
export function max(values) {
  if (!values || values.length === 0) return 0;
  return Math.max(...values);
}
