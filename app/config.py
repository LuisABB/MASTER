"""Application configuration from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    
    # Server
    ENV = os.getenv('NODE_ENV', 'development')  # Mantener nombre por compatibilidad
    DEBUG = ENV == 'development'
    PORT = int(os.getenv('PORT', 3000))
    
    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
    
    # Cache
    CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL_SECONDS', 86400))  # 24 hours
    CACHE_STALE_TTL_SECONDS = int(os.getenv('CACHE_STALE_TTL_SECONDS', 172800))  # 48 hours
    
    # Rate Limiting
    RATE_LIMIT_WINDOW_MS = int(os.getenv('RATE_LIMIT_WINDOW_MS', 60000))
    RATE_LIMIT_MAX_REQUESTS = int(os.getenv('RATE_LIMIT_MAX_REQUESTS', 60))
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # Google Trends - Configuración anti-bloqueo agresiva
    GOOGLE_TRENDS_MAX_RETRIES = int(os.getenv('GOOGLE_TRENDS_MAX_RETRIES', 5))
    GOOGLE_TRENDS_RETRY_DELAY_MS = int(os.getenv('GOOGLE_TRENDS_RETRY_DELAY_MS', 15000))  # 15s
    GOOGLE_TRENDS_REQUEST_DELAY_MS = int(os.getenv('GOOGLE_TRENDS_REQUEST_DELAY_MS', 10000))  # 10s
    GOOGLE_TRENDS_TIMEOUT_MS = int(os.getenv('GOOGLE_TRENDS_TIMEOUT_MS', 90000))  # 90s
    GOOGLE_TRENDS_CONCURRENCY = int(os.getenv('GOOGLE_TRENDS_CONCURRENCY', 1))
    
    # YouTube API
    YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', '')
    
    # CORS
    CORS_ORIGIN = os.getenv('CORS_ORIGIN', '*')


class TestConfig(Config):
    """Test configuration."""
    TESTING = True
    ENV = 'test'
    DEBUG = True


# Config dictionary
config = {
    'development': Config,
    'test': TestConfig,
    'production': Config,
}
