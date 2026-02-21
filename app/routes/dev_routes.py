"""Development routes (mock data)."""
from flask import Blueprint, request, jsonify
from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime

from app.connectors import generate_mock_time_series, generate_mock_by_country
from app.utils.redis_client import redis_client

dev_bp = Blueprint('dev', __name__)


class MockTrendSchema(Schema):
    """Schema for mock trend request."""
    keyword = fields.Str(required=True)
    country = fields.Str(required=True, validate=validate.OneOf(['MX', 'CR', 'ES']))
    window_days = fields.Int(missing=30)
    baseline_days = fields.Int(missing=365)


@dev_bp.route('/mock-trends', methods=['POST'])
def mock_trends():
    """
    Get mock trend data for development (when Google blocks API).
    
    POST /dev/mock-trends
    Body: {
        "keyword": "viva mexico",
        "country": "ES",
        "window_days": 30,
        "baseline_days": 1795
    }
    """
    try:
        schema = MockTrendSchema()
        data = schema.load(request.json or {})
        
        total_days = data['baseline_days'] + data['window_days']
        
        return jsonify({
            'timeSeries': generate_mock_time_series(data['keyword'], total_days),
            'byCountry': generate_mock_by_country(data['keyword'], data['country']),
            'keyword': data['keyword'],
            'country': data['country'],
            'window_days': data['window_days'],
            'baseline_days': data['baseline_days'],
            'source': 'MOCK_DATA',
            'warning': '⚠️  This is MOCK data for development. Real API is blocked by Google.',
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except ValidationError as err:
        return jsonify({
            'error': 'Validation failed',
            'details': err.messages
        }), 400


@dev_bp.route('/clear-cache', methods=['POST'])
def clear_cache():
    """
    Clear Redis cache (all keys or specific pattern).
    
    POST /dev/clear-cache
    Body (optional): {
        "pattern": "trend:*"  // Optional: clear specific pattern, default: all trend keys
    }
    """
    try:
        # Handle both JSON and no-body requests
        pattern = 'trend:*'
        if request.is_json and request.json:
            pattern = request.json.get('pattern', 'trend:*')
        
        # Get all matching keys
        keys = redis_client.client.keys(pattern)
        
        if not keys:
            return jsonify({
                'message': f'No keys found matching pattern: {pattern}',
                'deleted': 0
            })
        
        # Delete all matching keys
        deleted = redis_client.client.delete(*keys)
        
        return jsonify({
            'message': f'Cache cleared successfully',
            'pattern': pattern,
            'deleted': deleted,
            'keys': [k.decode('utf-8') if isinstance(k, bytes) else k for k in keys]
        })
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to clear cache',
            'details': str(e)
        }), 500


@dev_bp.route('/cache-info', methods=['GET'])
def cache_info():
    """
    Get information about cached keys.
    
    GET /dev/cache-info?pattern=trend:*
    """
    try:
        pattern = request.args.get('pattern', 'trend:*')
        
        # Get all matching keys
        keys = redis_client.client.keys(pattern)
        
        cache_data = []
        for key in keys:
            if isinstance(key, bytes):
                key = key.decode('utf-8')
            
            ttl = redis_client.get_ttl(key)
            value = redis_client.get(key)
            
            cache_data.append({
                'key': key,
                'ttl': ttl,
                'has_value': value is not None,
                'size': len(str(value)) if value else 0
            })
        
        return jsonify({
            'pattern': pattern,
            'total_keys': len(keys),
            'keys': cache_data
        })
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to get cache info',
            'details': str(e)
        }), 500
