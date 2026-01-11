/**
 * Supported countries mapping
 * Format: ISO 3166-1 alpha-2 country codes
 */
export const SUPPORTED_COUNTRIES = {
  'MX': 'México',
  'CR': 'Costa Rica',
  'ES': 'España'
};

/**
 * Check if country is supported
 */
export function isCountrySupported(country) {
  return country in SUPPORTED_COUNTRIES;
}

/**
 * Get all supported countries as array
 */
export function getSupportedCountries() {
  return Object.entries(SUPPORTED_COUNTRIES).map(([code, name]) => ({
    code,
    name
  }));
}

// Alias para retrocompatibilidad
export const isRegionSupported = isCountrySupported;
export const getSupportedRegions = getSupportedCountries;
