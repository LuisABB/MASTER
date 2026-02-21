"""Main Flask application."""
from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from loguru import logger
import uuid

from app.config import config
from app.utils.redis_client import redis_client


def create_app(config_name='development'):
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # CORS
    CORS(app, origins=app.config['CORS_ORIGIN'])
    
    # Rate Limiting
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[f"{app.config['RATE_LIMIT_MAX_REQUESTS']} per minute"],
        storage_uri=app.config['REDIS_URL']
    )
    
    # Request ID middleware
    @app.before_request
    def add_request_id():
        from flask import g, request
        g.request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
    
    # Logging middleware
    @app.after_request
    def log_response(response):
        from flask import g, request
        logger.info(
            f'{request.method} {request.path} - {response.status_code}',
            request_id=getattr(g, 'request_id', 'unknown')
        )
        return response
    
    # Root endpoint
    @app.route('/')
    def root():
        return jsonify({
            'name': 'Trends API (Python/Flask)',
            'version': '2.0.0',
            'status': 'running',
            'endpoints': {
                'health': '/health',
                'trends': '/v1/trends/query',
                'countries': '/v1/regions',
                'youtube': '/v1/sources/youtube/query',
                'fusion': '/v1/insights/fusion/query',
                'aliexpress_search': '/aliexpress/search',
                'dev_mock': '/dev/mock-trends'
            }
        })
    
    # Health check
    @app.route('/health')
    def health():
        return jsonify({
            'status': 'ok',
            'timestamp': datetime.utcnow().isoformat(),
            'redis': 'connected' if redis_client.connected else 'disconnected'
        })
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        from flask import g
        return jsonify({
            'error': 'Not found',
            'message': 'The requested resource was not found',
            'request_id': getattr(g, 'request_id', 'unknown')
        }), 404
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        from flask import g
        return jsonify({
            'error': 'Too many requests',
            'message': 'Rate limit exceeded. Please try again later.',
            'request_id': getattr(g, 'request_id', 'unknown')
        }), 429
    
    @app.errorhandler(500)
    def internal_error(error):
        from flask import g
        logger.error(f'Internal server error: {error}')
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred',
            'request_id': getattr(g, 'request_id', 'unknown')
        }), 500
    
    # Initialize connections
    with app.app_context():
        redis_client.connect()
    
    # Register blueprints
    from app.routes.trends_routes import trends_bp
    from app.routes.countries_routes import countries_bp
    from app.routes.dev_routes import dev_bp
    from app.routes.youtube_routes import youtube_bp
    from app.routes.fusion_routes import fusion_bp
    from app.routes.aliexpress_routes import aliexpress_bp
    
    app.register_blueprint(trends_bp, url_prefix='/v1/trends')
    app.register_blueprint(countries_bp, url_prefix='/v1')
    app.register_blueprint(youtube_bp, url_prefix='/v1/sources/youtube')
    app.register_blueprint(fusion_bp, url_prefix='/v1/insights/fusion')
    app.register_blueprint(aliexpress_bp, url_prefix='')
    
    if app.config['ENV'] == 'development':
        app.register_blueprint(dev_bp, url_prefix='/dev')
    
    return app


# Import datetime for health check
from datetime import datetime

__all__ = ['create_app']
