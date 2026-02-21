"""YouTube API Connector for fetching video data and statistics."""
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
import requests


class YouTubeConnector:
    """
    YouTube Data API v3 Connector.
    
    Fetches video search results and detailed statistics.
    """
    
    def __init__(self):
        """Initialize connector with API key from environment."""
        self.api_key = os.getenv('YOUTUBE_API_KEY')
        if not self.api_key:
            logger.warning('⚠️  YOUTUBE_API_KEY not set - YouTube features disabled')
        
        self.search_url = 'https://www.googleapis.com/youtube/v3/search'
        self.videos_url = 'https://www.googleapis.com/youtube/v3/videos'
    
    def search_videos(
        self,
        keyword: str,
        region: str = 'MX',
        lang: str = 'es',
        window_days: int = 30,
        max_results: int = 25
    ) -> List[Dict]:
        """
        Search for videos matching keyword.
        
        Args:
            keyword: Search query
            region: ISO 2-letter country code (MX, CR, ES)
            lang: Language code (es, en)
            window_days: Look back period in days
            max_results: Number of results (max 50)
            
        Returns:
            List of video items with id and snippet
        """
        if not self.api_key:
            raise Exception('YOUTUBE_API_KEY not configured')
        
        # YouTube API limits: max 365 days for publishedAfter
        window_days = min(365, window_days)
        
        # Calculate publishedAfter date
        published_after = (datetime.utcnow() - timedelta(days=window_days)).isoformat() + 'Z'
        
        # Build search query - simpler query for better results
        # Use keyword directly, YouTube's algorithm will find relevant content
        query = keyword
        
        params = {
            'part': 'snippet',
            'q': query,
            'type': 'video',
            'maxResults': min(50, max(1, max_results)),
            'publishedAfter': published_after,
            'regionCode': region.upper(),
            'relevanceLanguage': lang.lower(),
            'order': 'viewCount',
            'key': self.api_key
        }
        
        logger.info(
            f'🔍 Searching YouTube videos',
            keyword=keyword,
            region=region,
            window_days=window_days,
            max_results=max_results
        )
        
        try:
            response = requests.get(self.search_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            items = data.get('items', [])
            logger.info(f'✅ Found {len(items)} videos', keyword=keyword)
            
            return items
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.error('❌ YouTube API quota exceeded or invalid key')
                raise Exception('YouTube API quota exceeded or invalid API key')
            raise
        except Exception as error:
            logger.error(f'❌ YouTube search failed: {error}')
            raise
    
    def get_video_details(self, video_ids: List[str]) -> List[Dict]:
        """
        Get detailed statistics for videos (batch call, max 50 ids).
        
        Args:
            video_ids: List of YouTube video IDs
            
        Returns:
            List of video items with statistics and contentDetails
        """
        if not self.api_key:
            raise Exception('YOUTUBE_API_KEY not configured')
        
        if not video_ids:
            return []
        
        # YouTube API allows max 50 ids per request
        video_ids = video_ids[:50]
        
        params = {
            'part': 'snippet,statistics,contentDetails',
            'id': ','.join(video_ids),
            'key': self.api_key
        }
        
        logger.info(f'📊 Fetching details for {len(video_ids)} videos')
        
        try:
            response = requests.get(self.videos_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            items = data.get('items', [])
            logger.info(f'✅ Retrieved details for {len(items)} videos')
            
            return items
            
        except Exception as error:
            logger.error(f'❌ YouTube video details failed: {error}')
            raise
    
    def fetch_complete(
        self,
        keyword: str,
        region: str = 'MX',
        lang: str = 'es',
        window_days: int = 30,
        max_results: int = 25
    ) -> Dict:
        """
        Complete workflow: search + get details.
        
        Returns:
            Dictionary with videos list and metadata
        """
        # Step 1: Search
        search_items = self.search_videos(keyword, region, lang, window_days, max_results)
        
        # Extract video IDs
        video_ids = [
            item['id']['videoId']
            for item in search_items
            if item.get('id', {}).get('videoId')
        ]
        
        if not video_ids:
            logger.warning('No videos found', keyword=keyword)
            return {
                'videos': [],
                'query_used': keyword,
                'videos_count': 0
            }
        
        # Step 2: Get details
        detail_items = self.get_video_details(video_ids)
        
        return {
            'videos': detail_items,
            'query_used': keyword,
            'videos_count': len(detail_items)
        }


# Singleton instance
youtube_connector = YouTubeConnector()

__all__ = ['YouTubeConnector', 'youtube_connector']
