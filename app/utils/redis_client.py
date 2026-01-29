"""Redis client for caching."""
import json
import time
import redis
from typing import Optional, Any
from loguru import logger
from app.config import Config


class RedisClient:
    """Redis client wrapper for caching trend data."""
    
    def __init__(self):
        """Initialize Redis connection."""
        self.redis_url = Config.REDIS_URL
        self.client: Optional[redis.Redis] = None
        self.connected = False
        self.cache_ttl = Config.CACHE_TTL_SECONDS
        self.stale_ttl = Config.CACHE_STALE_TTL_SECONDS
        
    def connect(self):
        """Connect to Redis server."""
        try:
            self.client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5
            )
            # Test connection
            self.client.ping()
            self.connected = True
            logger.info('✅ Redis connected successfully')
        except Exception as error:
            logger.error(f'❌ Redis connection failed: {error}')
            self.connected = False
            self.client = None
    
    def generate_key(
        self,
        keyword: str,
        region: str,
        window_days: int,
        baseline_days: int,
        version: str = 'v4'
    ) -> str:
        """
        Generate cache key for trend query.
        
        Args:
            keyword: Search keyword
            region: Country code
            window_days: Window days
            baseline_days: Baseline days
            version: Cache version (default: v4)
            
        Returns:
            Cache key string
        """
        return f'trend:{version}:{keyword.lower()}:{region}:{window_days}:{baseline_days}'
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value (parsed from JSON) or None
        """
        if not self.connected or not self.client:
            return None
        
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as error:
            logger.error(f'Redis GET error: {error}', key=key)
            return None
    
    def get_stale(self, key: str) -> Optional[dict]:
        """
        Get stale cached data (even if expired).
        Useful as fallback when API fails.
        
        Args:
            key: Cache key
            
        Returns:
            Dictionary with data and age, or None
        """
        if not self.connected or not self.client:
            return None
        
        try:
            stale_key = f'{key}:stale'
            value = self.client.get(stale_key)
            
            if not value:
                return None
            
            parsed = json.loads(value)
            now = int(time.time() * 1000)  # Current time in ms
            age = (now - parsed['cachedAt']) // 1000  # Age in seconds
            
            return {
                **parsed['data'],
                'age': age,
                'cachedAt': parsed['cachedAt']
            }
        except Exception as error:
            logger.error(f'Redis GET_STALE error: {error}', key=key)
            return None
    
    def get_ttl(self, key: str) -> int:
        """
        Get TTL (time to live) of a key in seconds.
        
        Args:
            key: Cache key
            
        Returns:
            TTL in seconds, or 0 if key doesn't exist or no expiry
        """
        if not self.connected or not self.client:
            return 0
        
        try:
            ttl = self.client.ttl(key)
            return max(0, ttl) if ttl >= 0 else 0
        except Exception as error:
            logger.error(f'Redis TTL error: {error}', key=key)
            return 0
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache with optional TTL.
        Also stores a stale copy for fallback.
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (optional, uses Config.CACHE_TTL_SECONDS if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.connected or not self.client:
            return False
        
        try:
            serialized = json.dumps(value)
            cache_ttl = ttl if ttl is not None else self.cache_ttl
            
            # Set main cache with TTL
            self.client.setex(key, cache_ttl, serialized)
            
            # Set stale copy with longer TTL (for fallback)
            stale_key = f'{key}:stale'
            stale_data = {
                'data': value,
                'cachedAt': int(time.time() * 1000)  # Current time in ms
            }
            self.client.setex(stale_key, self.stale_ttl, json.dumps(stale_data))
            
            return True
        except Exception as error:
            logger.error(f'Redis SET error: {error}', key=key)
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        if not self.connected or not self.client:
            return False
        
        try:
            self.client.delete(key)
            return True
        except Exception as error:
            logger.error(f'Redis DELETE error: {error}', key=key)
            return False
    
    def close(self):
        """Close Redis connection."""
        if self.client:
            self.client.close()
            self.connected = False
            logger.info('Redis connection closed')


# Singleton instance
redis_client = RedisClient()

__all__ = ['redis_client', 'RedisClient']
