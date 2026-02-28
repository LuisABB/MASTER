"""Fusion Routes - Combined insights from multiple sources."""
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from loguru import logger

from app.services.trend_engine_service import trend_engine_service
from app.connectors.youtube_connector import youtube_connector
from app.services.youtube_intent_service import youtube_intent_service
from app.connectors.aliexpress_connector import aliexpress_connector
from app.services.aliexpress_category_map import (
    update_category_map_from_competitors,
    enrich_competitors
)

fusion_bp = Blueprint('fusion', __name__)


@fusion_bp.route('/query', methods=['POST'])
def fusion_query():
    """
    Combined insights from Google Trends + YouTube + AliExpress.
    
    POST /v1/insights/fusion/query
    Body: {
        "keyword": "zapatillas",
        "country": "CR",     // For Google Trends and YouTube
        "window_days": 365,
        "lang": "es",        // Optional, default es (used for YouTube and AliExpress)
        "maxResults": 25,    // Optional for YouTube
        "target_currency": "MXN",     // Optional for AliExpress
        "page": 1,                   // Optional for AliExpress
        "page_size": 10              // Optional for AliExpress
    }
    
    Returns:
        Unified JSON with google_trends, youtube, and fusion metrics
    """
    try:
        logger.info(
            f'Processing fusion query request',
            request_id=g.request_id
        )
        
        # Validate and parse input
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        keyword = str(data.get('keyword', '')).strip()
        if not keyword:
            return jsonify({'error': 'keyword is required'}), 400
        
        country = str(data.get('country', 'MX')).upper()
        region = country  # Use country for YouTube region to avoid duplicate params
        window_days = min(90, max(1, int(data.get('window_days', 30))))
        baseline_days = window_days
        lang = str(data.get('lang', 'es')).lower()
        max_results = min(50, max(1, int(data.get('maxResults', 25))))

        ship_to_country = country
        target_currency = str(data.get('target_currency', 'MXN')).upper()
        target_language = lang.upper()
        ae_page = max(1, int(data.get('page', 1)))
        ae_page_size = min(50, max(1, int(data.get('page_size', 10))))
        
        request_id = str(uuid.uuid4())
        generated_at = datetime.utcnow().isoformat()
        
        logger.info(
            f'Executing fusion query',
            request_id=request_id,
            keyword=keyword,
            country=country,
            region=region
        )
        
        # === 1. Google Trends ===
        logger.info(f'Fetching Google Trends data...', request_id=request_id)
        trends_result = trend_engine_service.execute_trend_query(
            keyword=keyword,
            country=country,
            window_days=window_days,
            baseline_days=baseline_days,
            request_id=request_id
        )
        
        # === 2. YouTube ===
        logger.info(f'Fetching YouTube data...', request_id=request_id)
        try:
            youtube_data = youtube_connector.fetch_complete(
                keyword=keyword,
                region=region,
                lang=lang,
                window_days=window_days,
                max_results=max_results
            )
            
            youtube_result = youtube_intent_service.calculate_intent_score(
                videos=youtube_data['videos'],
                keyword=keyword,
                region=region,
                window_days=window_days,
                lang=lang
            )
        except Exception as yt_error:
            logger.warning(f'YouTube fetch failed, continuing without it: {yt_error}', request_id=request_id)
            youtube_result = {
                'videos': [],
                'intent_score': 0,
                'total_views': 0,
                'videos_analyzed': 0,
                'error': str(yt_error)
            }
            youtube_data = {'query_used': ''}
        
        # === 3. AliExpress ===
        logger.info(f'Fetching AliExpress data...', request_id=request_id)
        try:
            aliexpress_result = aliexpress_connector.product_query(
                keywords=keyword,
                ship_to_country=ship_to_country,
                target_currency=target_currency,
                target_language=target_language,
                page_no=ae_page,
                page_size=ae_page_size
            )
            competitors = aliexpress_result.get('competitors', [])
            if competitors:
                category_map = update_category_map_from_competitors(competitors)
                aliexpress_result['competitors'] = enrich_competitors(competitors, category_map)
        except Exception as ae_error:
            logger.warning(f'AliExpress fetch failed, continuing without it: {ae_error}', request_id=request_id)
            aliexpress_result = {
                'query': {
                    'keywords': keyword,
                    'ship_to_country': ship_to_country,
                    'target_currency': target_currency,
                    'target_language': target_language,
                    'page': ae_page,
                    'page_size': ae_page_size
                },
                'paging': {
                    'page': ae_page,
                    'page_size': ae_page_size,
                    'total': 0
                },
                'competitors': [],
                'generated_at': generated_at,
                'error': str(ae_error)
            }

        # === 4. Fusion Metrics ===
        fusion_score = _calculate_fusion_score(
            trends_score=trends_result['trend_score'],
            youtube_intent=youtube_result['intent_score'],
            youtube_videos=youtube_result['videos_analyzed']
        )
        
        # === 5. Build unified response ===
        response = {
            'request_id': request_id,
            'generated_at': generated_at,
            'keyword': keyword,
            'country': country,
            'region': region,
            'window_days': window_days,
            'baseline_days': baseline_days,
            'lang': lang,
            'aliexpress_query': {
                'ship_to_country': ship_to_country,
                'target_currency': target_currency,
                'target_language': target_language,
                'page': ae_page,
                'page_size': ae_page_size
            },
            # Google Trends data
            'google_trends': {
                'trend_score': trends_result['trend_score'],
                'signals': trends_result['signals'],
                'sources_used': trends_result['sources_used'],
                'cache_hit': trends_result['cache']['hit'],
                'series_count': len(trends_result['series']),
                'by_country': trends_result['by_country']
            },
            # YouTube data
            'youtube': {
                'intent_score': youtube_result['intent_score'],
                'videos_analyzed': youtube_result['videos_analyzed'],
                'total_views': youtube_result['total_views'],
                'query_used': youtube_data.get('query_used', ''),
                'videos': youtube_result['videos']
            },
            # AliExpress data
            'aliexpress': {
                'paging': aliexpress_result.get('paging', {}),
                'competitors_count': len(aliexpress_result.get('competitors', [])),
                'competitors': aliexpress_result.get('competitors', []),
                'error': aliexpress_result.get('error')
            },
            # Fusion metrics
            'fusion': {
                'combined_score': fusion_score['combined_score'],
                'weight_trends': fusion_score['weight_trends'],
                'weight_youtube': fusion_score['weight_youtube'],
                'recommendation': fusion_score['recommendation']
            },
            # Time series (from Trends)
            'series': trends_result['series']
        }

        # === Inserción automática en MongoDB ===
        try:
            from app.utils.mongodb_fusion_insert import insertar_fusion_json_en_mongodb
            from pymongo import MongoClient
            MI_URI = "mongodb+srv://David:Mysehna123@cluster0.2lyc7x2.mongodb.net/?retryWrites=true&w=majority"
            MI_BD = "ecommerce_metrics"
            client = MongoClient(MI_URI)
            db = client[MI_BD]
            insertar_fusion_json_en_mongodb(response, db)
            client.close()
        except Exception as mongo_err:
            logger.error(f'Error al insertar en MongoDB: {mongo_err}', request_id=request_id)
        
        logger.info(
            f'Fusion query completed successfully',
            request_id=request_id,
            keyword=keyword,
            trends_score=trends_result['trend_score'],
            youtube_intent=youtube_result['intent_score'],
            fusion_score=fusion_score['combined_score']
        )
        
        return jsonify(response), 200
        
    except Exception as err:
        logger.error(f'Fusion query failed', request_id=g.request_id, error=str(err))
        return jsonify({
            'error': 'Failed to process fusion query',
            'details': str(err)
        }), 500


def _calculate_fusion_score(trends_score: float, youtube_intent: float, youtube_videos: int) -> dict:
    """
    Calculate combined score from Trends + YouTube.
    
    Weights:
    - If no YouTube data: 100% Trends
    - If YouTube available: 70% Trends + 30% YouTube
    """
    if youtube_videos == 0:
        weight_trends = 1.0
        weight_youtube = 0.0
    else:
        weight_trends = 0.7
        weight_youtube = 0.3
    
    combined_score = (trends_score * weight_trends) + (youtube_intent * weight_youtube)
    
    # Generate recommendation
    if combined_score >= 70:
        recommendation = 'HIGH_OPPORTUNITY'
    elif combined_score >= 50:
        recommendation = 'MODERATE_OPPORTUNITY'
    elif combined_score >= 30:
        recommendation = 'LOW_OPPORTUNITY'
    else:
        recommendation = 'NOT_RECOMMENDED'
    
    return {
        'combined_score': round(combined_score, 2),
        'weight_trends': weight_trends,
        'weight_youtube': weight_youtube,
        'recommendation': recommendation
    }

__all__ = ['fusion_bp']
