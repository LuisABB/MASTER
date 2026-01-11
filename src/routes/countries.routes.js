import express from 'express';
import { getSupportedCountries } from '../utils/regionMap.js';

const router = express.Router();

/**
 * GET /v1/countries
 * Get list of supported countries
 */
router.get('/', (req, res) => {
  const countries = getSupportedCountries();
  
  res.json({
    count: countries.length,
    countries
  });
});

export default router;
