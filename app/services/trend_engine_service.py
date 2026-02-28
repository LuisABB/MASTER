"""Trend Engine Service - Orchestrates trend analysis workflow."""
from datetime import datetime
from typing import Dict, Optional
from loguru import logger

from app.connectors import google_trends_connector
from app.services.scoring_service import scoring_service
from app.utils.redis_client import redis_client
from app.config import Config


class AppError(Exception):
    """Custom application error."""
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class TrendEngineService:
    """
    Trend Engine Service - Orchestrates the complete trend analysis workflow.
    
    Flow:
    1. Check cache
    2. Fetch from Google Trends
    3. Calculate score
    4. Cache result
    5. Return response
    
    Fallback: If API fails, try to return stale cached data
    """
    
    def execute_trend_query(
        self,
        keyword: str,
        country: str,
        window_days: int,
        baseline_days: int,
        request_id: str
    ) -> Dict:
        """
        Execute trend query with caching.
        
        Args:
            keyword: Search keyword
            country: Country code (MX, CR, ES)
            window_days: Recent window for analysis
            baseline_days: Historical baseline period
            request_id: Request ID for tracking
            
        Returns:
            Dictionary with trend analysis results
            
        Raises:
            AppError: If query fails and no fallback available
        """
        logger.info(
            f'Executing trend query',
            request_id=request_id,
            keyword=keyword,
            country=country,
            window_days=window_days,
            baseline_days=baseline_days
        )
        
        # Check cache first
        cache_key = redis_client.generate_key(keyword, country, window_days, baseline_days)
        cached_result = redis_client.get(cache_key)
        
        if cached_result:
            logger.info(f'Cache hit', request_id=request_id, cache_key=cache_key)
            ttl = redis_client.get_ttl(cache_key)
            response = {
                **cached_result,
                'cache': {
                    'hit': True,
                    'ttl_seconds': ttl
                }
            }
            return response
        
        logger.info(f'Cache miss - fetching fresh data', request_id=request_id, cache_key=cache_key)
        
        try:
            # Fetch data from Google Trends
            trends_data = google_trends_connector.fetch_complete(
                keyword,
                country,
                window_days,
                baseline_days
            )
            
            # Calculate score and signals
            scoring = scoring_service.calculate_score(
                trends_data['timeSeries'],
                keyword,
                country,
                window_days,
                baseline_days
            )
            
            # Build response
            response = {
                'keyword': keyword,
                'country': country,
                'window_days': window_days,
                'baseline_days': baseline_days,
                'generated_at': datetime.utcnow().isoformat(),
                'sources_used': [trends_data.get('source', 'google_trends')],
                'trend_score': scoring['trendScore'],
                'signals': scoring['signals'],
                'series': trends_data['timeSeries'],
                'by_country': trends_data['byCountry'],
                'explain': scoring['explain'],
                'cache': {
                    'hit': False,
                    'ttl_seconds': Config.CACHE_TTL_SECONDS
                },
                'request_id': request_id
            }
            
            # Cache the result
            redis_client.set(cache_key, response)
            
            
            logger.info(
                f'Trend query completed successfully',
                request_id=request_id,
                keyword=keyword,
                country=country,
                trend_score=scoring['trendScore']
            )
            
            return response
            
        except Exception as error:
            logger.error(
                f'Trend query failed - attempting stale cache fallback',
                request_id=request_id,
                error=str(error),
                keyword=keyword,
                country=country
            )
            
            # 🔥 FALLBACK: Try to return stale cached data
            stale_data = redis_client.get_stale(cache_key)
            
            if stale_data:
                age_hours = round(stale_data['age'] / 3600)
                logger.warning(
                    f'Returning stale cached data due to API failure',
                    request_id=request_id,
                    keyword=keyword,
                    country=country,
                    stale_age_hours=age_hours
                )
                
                # Remove age and cachedAt from response
                stale_age = stale_data.pop('age', 0)
                stale_data.pop('cachedAt', None)
                
                return {
                    **stale_data,
                    'cache': {
                        'hit': True,
                        'stale': True,
                        'age_hours': age_hours,
                        'ttl_seconds': 0
                    },
                    'warning': 'Data may be outdated due to temporary API issues',
                    'sources_used': ['stale_cache']
                }
            
            # If no stale data available, raise error
            logger.error(
                f'No stale cache available, failing request',
                request_id=request_id,
                keyword=keyword,
                country=country
            )
            
            # Determine error type
            error_msg = str(error)
            if 'Invalid response' in error_msg or 'No data' in error_msg:
                raise AppError(
                    f'No trend data available for keyword "{keyword}" in country "{country}"',
                    404,
                    {'keyword': keyword, 'country': country}
                )
            
            raise AppError(
                f'Failed to fetch trend data: {error_msg}',
                500,
                {'originalError': error_msg}
            )


# Singleton instance
trend_engine_service = TrendEngineService()

__all__ = ['TrendEngineService', 'trend_engine_service', 'AppError']
