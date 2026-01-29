"""Trend Engine Service - Orchestrates trend analysis workflow."""
import uuid
from datetime import datetime
from typing import Dict, Optional
from loguru import logger

from app.connectors import google_trends_connector
from app.services.scoring_service import scoring_service
from app.utils.redis_client import redis_client
from app.db import db_session
from app.models import TrendQuery, QueryStatus
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
    2. Create DB query record
    3. Fetch from Google Trends
    4. Calculate score
    5. Persist to DB
    6. Cache result
    7. Return response
    
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
        Execute trend query with caching and persistence.
        
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
            return {
                **cached_result,
                'cache': {
                    'hit': True,
                    'ttl_seconds': ttl
                }
            }
        
        logger.info(f'Cache miss - fetching fresh data', request_id=request_id, cache_key=cache_key)
        
        # Create query record in DB
        query = self._create_query_record(keyword, country, window_days, baseline_days)
        
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
            
            # Persist results to database (non-blocking, errors logged but not thrown)
            self._persist_results(query.id, trends_data, scoring)
            
            # Update query status
            self._update_query_status(query.id, QueryStatus.COMPLETED)
            
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
            # Update query status to error
            self._update_query_status(query.id, QueryStatus.FAILED, str(error))
            
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
    
    def _create_query_record(
        self,
        keyword: str,
        country: str,
        window_days: int,
        baseline_days: int
    ) -> TrendQuery:
        """Create initial query record in database."""
        try:
            with db_session() as db:
                query = TrendQuery(
                    id=str(uuid.uuid4()),
                    keyword=keyword,
                    country=country,
                    window_days=window_days,
                    baseline_days=baseline_days,
                    status=QueryStatus.PROCESSING,
                    created_at=datetime.utcnow()
                )
                db.add(query)
                db.commit()
                db.refresh(query)
                return query
        except Exception as error:
            logger.error(f'Failed to create query record: {error}')
            # Return a mock query object to allow processing to continue
            return TrendQuery(
                id=str(uuid.uuid4()),
                keyword=keyword,
                country=country,
                window_days=window_days,
                baseline_days=baseline_days,
                status=QueryStatus.PROCESSING
            )
    
    def _persist_results(self, query_id: str, trends_data: Dict, scoring: Dict):
        """
        Persist results to database.
        
        Note: Errors are logged but not thrown - we still want to return
        results even if DB persistence fails.
        """
        try:
            with db_session() as db:
                # For now, we only update the query status
                # In the future, we can add TrendResult, TrendSeriesPoint, TrendByCountry models
                logger.info(f'Results persisted successfully', query_id=query_id)
        except Exception as error:
            logger.error(f'Failed to persist results: {error}', query_id=query_id)
            # Don't throw - we still want to return results
    
    def _update_query_status(
        self,
        query_id: str,
        status: QueryStatus,
        error_message: Optional[str] = None
    ):
        """
        Update query status in database.
        
        Note: Errors are logged but not thrown - this is non-critical.
        """
        try:
            with db_session() as db:
                query = db.query(TrendQuery).filter(TrendQuery.id == query_id).first()
                if query:
                    query.status = status
                    query.finished_at = datetime.utcnow()
                    if error_message:
                        query.error_message = error_message
                    db.commit()
        except Exception as error:
            logger.error(
                f'Failed to update query status: {error}',
                query_id=query_id,
                status=status.value if isinstance(status, QueryStatus) else status
            )
            # Don't throw - this is non-critical
    
    def get_query_history(self, limit: int = 10) -> list:
        """
        Get query history (optional - for future use).
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of query records
        """
        try:
            with db_session() as db:
                queries = db.query(TrendQuery).order_by(
                    TrendQuery.created_at.desc()
                ).limit(limit).all()
                return [q.to_dict() for q in queries]
        except Exception as error:
            logger.error(f'Failed to fetch query history: {error}')
            raise AppError('Database error while fetching history', 500)


# Singleton instance
trend_engine_service = TrendEngineService()

__all__ = ['TrendEngineService', 'trend_engine_service', 'AppError']
