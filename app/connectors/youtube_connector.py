"""YouTube API Connector for fetching video data and statistics."""
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
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
        self.channels_url = 'https://www.googleapis.com/youtube/v3/channels'
    
    def search_videos(
        self,
        keyword: str,
        region: str = 'MX',
        lang: str = 'es',
        window_days: int = 30,
        max_results: int = 25,
        page_token: Optional[str] = None,
        published_after: Optional[datetime] = None,
        published_before: Optional[datetime] = None,
        order: str = 'viewCount'
    ) -> Dict[str, Any]:
        """
        Search for videos matching keyword.
        
        Args:
            keyword: Search query
            region: ISO 2-letter country code (MX, CR, ES)
            lang: Language code (es, en)
            window_days: Look back period in days
            max_results: Number of results (max 50)
            order: Sorting order (default: viewCount)
            
        Returns:
            Dict with items and next_page_token
        """
        if not self.api_key:
            raise Exception('YOUTUBE_API_KEY not configured')
        
        # Allow up to 5 years of lookback
        window_days = min(1825, window_days)
        
        # Calculate publishedAfter/Before dates
        published_after_dt = published_after or (datetime.utcnow() - timedelta(days=window_days))
        published_after_value = published_after_dt.replace(microsecond=0).isoformat() + 'Z'
        published_before_value = None
        if published_before is not None:
            published_before_value = published_before.replace(microsecond=0).isoformat() + 'Z'
        
        # Build search query - simpler query for better results
        # Use keyword directly, YouTube's algorithm will find relevant content
        query = keyword
        
        params = {
            'part': 'snippet',
            'q': query,
            'type': 'video',
            'maxResults': min(50, max(1, max_results)),
            'publishedAfter': published_after_value,
            'regionCode': region.upper(),
            'relevanceLanguage': lang.lower(),
            'order': order,
            'key': self.api_key
        }
        if page_token:
            params['pageToken'] = page_token
        if published_before_value:
            params['publishedBefore'] = published_before_value
        
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
            next_page_token = data.get('nextPageToken')
            logger.info(f'✅ Found {len(items)} videos', keyword=keyword)

            return {
                'items': items,
                'next_page_token': next_page_token
            }
            
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
        Get detailed statistics for videos (batched calls, max 50 ids per request).
        
        Args:
            video_ids: List of YouTube video IDs
            
        Returns:
            List of video items with statistics and contentDetails
        """
        if not self.api_key:
            raise Exception('YOUTUBE_API_KEY not configured')
        
        if not video_ids:
            return []
        
        all_items: List[Dict] = []
        
        try:
            for i in range(0, len(video_ids), 50):
                batch = video_ids[i:i + 50]
                params = {
                    'part': 'snippet,statistics,contentDetails',
                    'id': ','.join(batch),
                    'key': self.api_key
                }
                
                logger.info(f'📊 Fetching details for {len(batch)} videos')
                response = requests.get(self.videos_url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                items = data.get('items', [])
                all_items.extend(items)
                logger.info(f'✅ Retrieved details for {len(items)} videos')
            
            return all_items
            
        except Exception as error:
            logger.error(f'❌ YouTube video details failed: {error}')
            raise

    def get_channel_details(self, channel_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get channel metadata (batched calls, max 50 ids per request).

        Returns:
            Mapping of channel_id -> channel snippet
        """
        if not self.api_key:
            raise Exception('YOUTUBE_API_KEY not configured')

        if not channel_ids:
            return {}

        channel_map: Dict[str, Dict[str, Any]] = {}

        try:
            for i in range(0, len(channel_ids), 50):
                batch = channel_ids[i:i + 50]
                params = {
                    'part': 'snippet',
                    'id': ','.join(batch),
                    'key': self.api_key
                }
                response = requests.get(self.channels_url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                items = data.get('items', [])
                for item in items:
                    cid = item.get('id')
                    snippet = item.get('snippet') or {}
                    if cid:
                        channel_map[cid] = snippet

            return channel_map

        except Exception as error:
            logger.error(f'❌ YouTube channel details failed: {error}')
            return {}

    @staticmethod
    def _normalize_lang(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        return value.lower().split('-')[0]

    def _filter_videos_by_locale(self, videos: List[Dict], region: str, lang: str) -> List[Dict]:
        if not videos:
            return videos

        requested_country = (region or '').upper().strip()
        requested_lang = (lang or '').lower().strip()

        channel_ids = [
            v.get('snippet', {}).get('channelId')
            for v in videos
            if v.get('snippet', {}).get('channelId')
        ]
        channel_map = self.get_channel_details(list(set(channel_ids)))

        filtered: List[Dict] = []
        for video in videos:
            snippet = video.get('snippet') or {}
            channel_id = snippet.get('channelId')
            channel_snippet = channel_map.get(channel_id, {}) if channel_id else {}

            channel_country = (channel_snippet.get('country') or '').upper().strip()
            video_lang = self._normalize_lang(snippet.get('defaultLanguage') or snippet.get('defaultAudioLanguage'))
            channel_lang = self._normalize_lang(
                channel_snippet.get('defaultLanguage') or channel_snippet.get('defaultAudioLanguage')
            )

            country_ok = True

            lang_ok = True
            if requested_lang:
                if video_lang or channel_lang:
                    lang_ok = requested_lang in {video_lang, channel_lang}

            if country_ok and lang_ok:
                filtered.append(video)

        logger.info(
            '🌎 Filtered videos by locale',
            before=len(videos),
            after=len(filtered),
            country=requested_country,
            lang=requested_lang
        )
        return filtered
    
    def fetch_complete(
        self,
        keyword: str,
        region: str = 'MX',
        lang: str = 'es',
        window_days: int = 30,
        max_results: int = 25,
        max_pages: int = 1,
        segment_days: int = 365,
        order: str = 'date'
    ) -> Dict:
        """
        Complete workflow: search + get details.
        
        Returns:
            Dictionary with videos list and metadata
        """
        # Step 1: Search with segmentation + pagination
        window_days = min(1825, max(1, int(window_days)))
        max_pages = max(1, int(max_pages))
        segment_days = min(365, window_days)

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=window_days)

        segments: List[Tuple[datetime, datetime]] = []
        cur_end = end_date
        while cur_end > start_date:
            cur_start = max(start_date, cur_end - timedelta(days=segment_days))
            segments.append((cur_start, cur_end))
            cur_end = cur_start

        items: List[Dict] = []
        for seg_start, seg_end in segments:
            result = self.search_videos(
                keyword=keyword,
                region=region,
                lang=lang,
                window_days=(seg_end - seg_start).days,
                max_results=max_results,
                page_token=None,
                published_after=seg_start,
                published_before=seg_end,
                order=order
            )
            items.extend(result.get('items', []))

        # Extract unique video IDs
        seen_ids: set[str] = set()
        video_ids: List[str] = []
        for item in items:
            vid = item.get('id', {}).get('videoId')
            if not vid or vid in seen_ids:
                continue
            seen_ids.add(vid)
            video_ids.append(vid)
        
        if not video_ids:
            logger.warning('No videos found', keyword=keyword)
            return {
                'videos': [],
                'query_used': keyword,
                'videos_count': 0
            }
        
        # Step 2: Get details
        detail_items = self.get_video_details(video_ids)
        detail_items = self._filter_videos_by_locale(detail_items, region, lang)
        
        return {
            'videos': detail_items,
            'query_used': keyword,
            'videos_count': len(detail_items)
        }


# Singleton instance
youtube_connector = YouTubeConnector()

__all__ = ['YouTubeConnector', 'youtube_connector']
