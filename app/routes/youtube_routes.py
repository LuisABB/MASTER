"""YouTube Routes - Endpoints for YouTube video analysis."""
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g
from loguru import logger

from app.connectors.youtube_connector import youtube_connector
from app.services.youtube_intent_service import youtube_intent_service

youtube_bp = Blueprint('youtube', __name__)


@youtube_bp.route('/query', methods=['POST'])
def youtube_query():
    """
    Query YouTube videos and calculate intent scores.
    
    POST /v1/sources/youtube/query
    Body: {
        "keyword": "maletas",
        "country": "MX",     // Optional, default MX
        "lang": "es",        // Optional, default es
        "window_days": 30,   // Optional, default 30 (max 1825)
        "maxResults": 25     // Optional, default 25, max 50
    }
    
    Returns:
        JSON with videos and intent_score
    """
    try:
        logger.info(
            f'Processing YouTube query request',
            request_id=g.request_id
        )
        
        # Validate and parse input
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'Request body is required'
            }), 400
        
        keyword = str(data.get('keyword', '')).strip()
        if not keyword:
            return jsonify({
                'error': 'keyword is required'
            }), 400
        
        country = str(data.get('country', 'MX')).upper()
        lang = str(data.get('lang', 'es')).lower()
        window_days = min(1825, max(1, int(data.get('window_days', 30))))
        max_results = min(50, max(1, int(data.get('maxResults', 25))))
        order = 'viewcount'
        
        logger.info(
            f'Executing YouTube query',
            request_id=g.request_id,
            keyword=keyword,
            country=country,
            window_days=window_days
        )
        
        # Fetch from YouTube
        youtube_data = youtube_connector.fetch_complete(
            keyword=keyword,
            region=country,
            lang=lang,
            window_days=window_days,
            max_results=max_results,
            max_pages=1,
            segment_days=window_days,
            order=order
        )
        
        # Calculate intent scores
        result = youtube_intent_service.calculate_intent_score(
            videos=youtube_data['videos'],
            keyword=keyword,
            region=country,
            window_days=window_days,
            lang=lang
        )
        
        # Build response
        request_id = str(uuid.uuid4())
        generated_at = datetime.utcnow().isoformat()
        
        published_after = (datetime.utcnow() - timedelta(days=window_days)).replace(microsecond=0).isoformat() + 'Z'

        response = {
            'request_id': request_id,
            'generated_at': generated_at,
            'keyword': keyword,
            'country': country,
            'lang': lang,
            'window_days': window_days,
            'published_after': published_after,
            'query_used': youtube_data['query_used'],
            'videos_analyzed': result['videos_analyzed'],
            'total_views': result['total_views'],
            'intent_score': result['intent_score'],
            'videos': result['videos']
        }
        
        logger.info(
            f'YouTube query completed successfully',
            request_id=request_id,
            keyword=keyword,
            country=country,
            intent_score=result['intent_score'],
            videos=result['videos_analyzed']
        )
        
        return jsonify(response), 200
        
    except ValueError as err:
        logger.error(f'Validation error', request_id=g.request_id, error=str(err))
        return jsonify({
            'error': 'Validation failed',
            'details': str(err)
        }), 400
        
    except Exception as err:
        logger.error(f'Unexpected error processing YouTube query', request_id=g.request_id, error=str(err))
        return jsonify({
            'error': 'Failed to process YouTube query',
            'details': str(err)
        }), 500
__all__ = ['youtube_bp']
