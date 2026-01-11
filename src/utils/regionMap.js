/**
 * Supported regions mapping
 * Format: ISO 3166-2 codes for Mexican states
 */
export const SUPPORTED_REGIONS = {
  'MX-CMX': 'Ciudad de México',
  'MX-JAL': 'Jalisco',
  'MX-NLE': 'Nuevo León',
  'MX-PUE': 'Puebla',
  'MX-GUA': 'Guanajuato',
  'MX-VER': 'Veracruz',
  'MX-CHH': 'Chihuahua',
  'MX-BCN': 'Baja California',
  'MX-SON': 'Sonora',
  'MX-TAM': 'Tamaulipas',
  'MX-SIN': 'Sinaloa',
  'MX-COA': 'Coahuila',
  'MX-QUE': 'Querétaro',
  'MX-YUC': 'Yucatán',
  'MX-MEX': 'Estado de México'
};

/**
 * Check if region is supported
 */
export function isRegionSupported(region) {
  return region in SUPPORTED_REGIONS;
}

/**
 * Get all supported regions as array
 */
export function getSupportedRegions() {
  return Object.entries(SUPPORTED_REGIONS).map(([code, name]) => ({
    code,
    name
  }));
}
