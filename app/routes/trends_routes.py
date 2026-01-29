"""Trends routes."""
from flask import Blueprint, request, jsonify, g
from marshmallow import Schema, fields, validate, ValidationError
from loguru import logger

from app.services import trend_engine_service, AppError

trends_bp = Blueprint('trends', __name__)


class TrendQuerySchema(Schema):
    """Schema for trend query validation."""
    keyword = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    country = fields.Str(required=True, validate=validate.OneOf(['MX', 'CR', 'ES']))
    window_days = fields.Int(missing=30, validate=validate.Range(min=1, max=90))
    baseline_days = fields.Int(missing=365, validate=validate.Range(min=7, max=1825))


@trends_bp.route('/query', methods=['POST'])
def query_trend():
    """
    Query Google Trends for a keyword.
    
    POST /v1/trends/query
    Body: {
        "keyword": "viva mexico",
        "country": "ES",
        "window_days": 30,
        "baseline_days": 1795
    }
    """
    try:
        # Validate request
        schema = TrendQuerySchema()
        data = schema.load(request.json or {})
        
        logger.info(
            f'Processing trend query request',
            request_id=g.request_id,
            params=data
        )
        
        # Execute trend query
        result = trend_engine_service.execute_trend_query(
            keyword=data['keyword'],
            country=data['country'],
            window_days=data['window_days'],
            baseline_days=data['baseline_days'],
            request_id=g.request_id
        )
        
        return jsonify(result), 200
        
    except ValidationError as err:
        logger.warning(f'Validation error', request_id=g.request_id, errors=err.messages)
        return jsonify({
            'error': 'Validation failed',
            'details': err.messages,
            'request_id': g.request_id
        }), 400
    except AppError as err:
        logger.error(f'Application error', request_id=g.request_id, error=str(err))
        return jsonify({
            'error': err.message,
            'request_id': g.request_id,
            'details': err.details
        }), err.status_code
    except Exception as err:
        logger.error(f'Unexpected error processing trend query', request_id=g.request_id, error=str(err))
        return jsonify({
            'error': 'Failed to process trend query',
            'message': str(err),
            'request_id': g.request_id
        }), 500
