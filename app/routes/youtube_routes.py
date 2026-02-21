"""YouTube Routes - Endpoints for YouTube video analysis."""
import csv
import os
import uuid
from datetime import datetime
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
        "window_days": 30,   // Optional, default 30
        "maxResults": 25     // Optional, default 25, max 50
    }
    
    Returns:
        JSON with videos, intent_score, and CSV file path
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
        window_days = min(90, max(1, int(data.get('window_days', 30))))
        max_results = min(50, max(1, int(data.get('maxResults', 25))))
        
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
            max_results=max_results
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
        
        response = {
            'request_id': request_id,
            'generated_at': generated_at,
            'keyword': keyword,
            'country': country,
            'lang': lang,
            'window_days': window_days,
            'published_after': (datetime.utcnow().replace(microsecond=0).isoformat() + 'Z').replace('+00:00', ''),
            'query_used': youtube_data['query_used'],
            'videos_analyzed': result['videos_analyzed'],
            'total_views': result['total_views'],
            'intent_score': result['intent_score'],
            'videos': result['videos']
        }
        
        # Save to CSV
        csv_file = _save_youtube_csv(response)
        response['csv_file'] = csv_file
        
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


def _save_youtube_csv(response: dict) -> str:
    """
    Save YouTube results to CSV file.
    
    Args:
        response: Complete YouTube response dictionary
        
    Returns:
        Path to generated CSV file
    """
    try:
        # Create results directory
        results_dir = 'results'
        os.makedirs(results_dir, exist_ok=True)
        
        csv_file = os.path.join(results_dir, 'youtube_data.csv')
        
        # Check if file exists
        file_exists = os.path.exists(csv_file)
        
        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header if file is new
            if not file_exists:
                writer.writerow([
                    'request_id',
                    'generated_at',
                    'keyword',
                    'country',
                    'lang',
                    'window_days',
                    'query_used',
                    'video_id',
                    'title',
                    'channel_title',
                    'published_at',
                    'url',
                    'duration',
                    'views',
                    'likes',
                    'comments',
                    'engagement_rate',
                    'days_since_publish',
                    'freshness',
                    'video_intent'
                ])
            
            # Write one row per video
            for video in response['videos']:
                writer.writerow([
                    response['request_id'],
                    response['generated_at'],
                    response['keyword'],
                    response['country'],
                    response['lang'],
                    response['window_days'],
                    response['query_used'],
                    video['video_id'],
                    video['title'],
                    video['channel_title'],
                    video['published_at'],
                    video['url'],
                    video['duration'],
                    video['views'],
                    video['likes'],
                    video['comments'],
                    video['engagement_rate'],
                    video['days_since_publish'],
                    video['freshness'],
                    video['video_intent']
                ])
        
        logger.info(
            f'📊 YouTube results saved to CSV',
            csv_file=csv_file,
            keyword=response['keyword'],
            rows=len(response['videos'])
        )
        
        return csv_file
        
    except Exception as error:
        logger.error(f'Failed to save YouTube CSV: {error}')
        return ''


__all__ = ['youtube_bp']
