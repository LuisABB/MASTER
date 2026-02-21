"""AliExpress Routes - Direct TOP router integration."""
import csv
import os
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
        

        csv_file = _save_aliexpress_csv(result, request_id=g.request_id)
        result['csv_file'] = csv_file

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


def _save_aliexpress_csv(result: dict, request_id: str) -> str:
    """
    Save AliExpress results to CSV.

    Creates: results/aliexpress_data.csv
    """
    try:
        results_dir = 'results'
        os.makedirs(results_dir, exist_ok=True)

        csv_file = os.path.join(results_dir, 'aliexpress_data.csv')
        file_exists = os.path.exists(csv_file)

        query = result.get('query', {})
        paging = result.get('paging', {})
        competitors = result.get('competitors', [])
        generated_at = result.get('generated_at', '')

        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            if not file_exists:
                writer.writerow([
                    'request_id',
                    'generated_at',
                    'keywords',
                    'ship_to_country',
                    'target_currency',
                    'target_language',
                    'page',
                    'page_size',
                    'total',
                    'product_id',
                    'product_title',
                    'sale_price',
                    'discount',
                    'evaluate_rate',
                    'lastest_volume',
                    'product_detail_url',
                    'shop_id',
                    'shop_url',
                    'promotion_link',
                    'category_id',
                    'category_name',
                    'category_path',
                    'macro_category',
                    'macro_path',
                    'category_resolution_confidence',
                    'first_level_category_id',
                    'sell_score'
                ])

            for item in competitors:
                writer.writerow([
                    request_id,
                    generated_at,
                    query.get('keywords', ''),
                    query.get('ship_to_country', ''),
                    query.get('target_currency', ''),
                    query.get('target_language', ''),
                    paging.get('page', ''),
                    paging.get('page_size', ''),
                    paging.get('total', ''),
                    item.get('product_id', ''),
                    item.get('product_title', ''),
                    item.get('sale_price', ''),
                    item.get('discount', ''),
                    item.get('evaluate_rate', ''),
                    item.get('lastest_volume', ''),
                    item.get('product_detail_url', ''),
                    item.get('shop_id', ''),
                    item.get('shop_url', ''),
                    item.get('promotion_link', ''),
                    item.get('category_id', ''),
                    item.get('category_name', ''),
                    item.get('category_path', ''),
                    item.get('macro_category', ''),
                    item.get('macro_path', ''),
                    item.get('category_resolution_confidence', 'unknown'),
                    item.get('first_level_category_id', ''),
                    item.get('sell_score', '')
                ])

        logger.info('AliExpress CSV saved', csv_file=csv_file, request_id=request_id)
        return csv_file
    except Exception as error:
        logger.error('Failed to save AliExpress CSV', error=str(error))
        return ''
