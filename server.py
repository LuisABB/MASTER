"""Server entry point."""
import os
from app import create_app
from loguru import logger

# Get environment
env = os.getenv('NODE_ENV', 'development')

# Create app
app = create_app(env)

if __name__ == '__main__':
    port = app.config['PORT']
    debug = app.config['DEBUG']
    
    logger.info(f'''
🚀 Trends API (Python/Flask) is running!
📍 Environment: {env}
🔗 URL: http://localhost:{port}

📚 Available endpoints:
    GET  /health                            - Health check
    POST /v1/trends/query                   - Query trends
    GET  /v1/regions                        - List supported regions
    POST /v1/sources/youtube/query          - YouTube data
    POST /v1/insights/fusion/query          - Combined insights (Trends + YouTube)
    GET  /aliexpress/search                 - AliExpress Affiliate (proxy)
    POST /dev/mock-trends                   - Mock data (dev only)
    POST /dev/clear-cache                   - Clear Redis cache (dev only)
    GET  /dev/cache-info                    - View cache info (dev only)

💡 Press Ctrl+C to stop
    ''')
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
