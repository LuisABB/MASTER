"""AliExpress Routes - Direct TOP router integration."""
from flask import Blueprint, request, jsonify, g
from loguru import logger

from app.connectors.aliexpress_connector import aliexpress_connector
from app.services.aliexpress_category_map import (
    enrich_competitors,
    update_category_map_from_competitors
)

aliexpress_bp = Blueprint('aliexpress', __name__)


@aliexpress_bp.route('/aliexpress/search', methods=['POST'])
def aliexpress_search():
    """
    AliExpress Affiliate search via Portals gateway.

    POST /aliexpress/search
    Body (JSON):
    {
      "keywords": "phone",
      "ship_to_country": "MX",
      "target_currency": "MXN",
      "target_language": "ES",
      "page": 1,
      "page_size": 50
    }
    """
    try:
        data = request.get_json(silent=True) or {}

        keywords = str(data.get('keywords', '')).strip()
        if not keywords:
            return jsonify({'error': 'keywords is required'}), 400

        ship_to_country = str(data.get('ship_to_country', 'MX')).upper()
        target_currency = str(data.get('target_currency', 'MXN')).upper()
        target_language = str(data.get('target_language', 'ES')).upper()
        page = max(1, int(data.get('page', 1)))
        page_size = min(50, max(1, int(data.get('page_size', 50))))

        logger.info(
            'AliExpress search request',
            request_id=g.request_id,
            keywords=keywords,
            ship_to_country=ship_to_country,
            target_currency=target_currency,
            target_language=target_language,
            page=page,
            page_size=page_size
        )

        result = aliexpress_connector.product_query(
            keywords=keywords,
            ship_to_country=ship_to_country,
            target_currency=target_currency,
            target_language=target_language,
            page_no=page,
            page_size=page_size
        )

        competitors = result.get('competitors', [])

        try:
            category_map = update_category_map_from_competitors(competitors)
        except Exception as error:
            logger.error('Category map update failed', request_id=g.request_id, error=str(error))
            category_map = {}

        result['competitors'] = enrich_competitors(competitors, category_map)
        

        return jsonify(result), 200
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    except Exception as error:
        logger.error('AliExpress search failed', request_id=g.request_id, error=str(error))
        return jsonify({
            'error': 'AliExpress search failed',
            'details': str(error)
        }), 502


__all__ = ['aliexpress_bp']
