import express from 'express';
import { getSupportedRegions } from '../utils/regionMap.js';

const router = express.Router();

/**
 * GET /v1/regions
 * Get list of supported regions
 */
router.get('/', (req, res) => {
  const regions = getSupportedRegions();
  
  res.json({
    count: regions.length,
    regions
  });
});

export default router;
