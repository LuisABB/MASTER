"""YouTube Intent Service - Calculate video intent scores and metrics."""
import math
from datetime import datetime
from typing import Dict, List
from loguru import logger


class YouTubeIntentService:
    """
    Service for calculating YouTube video intent scores.
    
    Metrics:
    - engagement_rate: (likes + 2*comments) / views
    - freshness: exp(-days_since_publish / half_life)
    - video_intent: log10(views+1) * engagement_rate * freshness
    - intent_score: weighted_avg(video_intent, weight=views)
    """
    
    def _get_half_life_days(self, window_days: int) -> int:
        """Get half-life decay parameter based on window."""
        if window_days <= 7:
            return 4
        elif window_days <= 14:
            return 7
        return 14
    
    def _safe_number(self, value, fallback=0) -> float:
        """Safely convert to number."""
        try:
            n = float(value)
            return n if math.isfinite(n) else fallback
        except (TypeError, ValueError):
            return fallback
    
    def compute_video_features(
        self,
        views: int,
        likes: int,
        comments: int,
        published_at: str,
        window_days: int
    ) -> Dict:
        """
        Compute engagement, freshness and intent for a single video.
        
        Args:
            views: View count
            likes: Like count
            comments: Comment count
            published_at: ISO timestamp
            window_days: Analysis window in days
            
        Returns:
            Dict with days_since_publish, freshness, engagement_rate, video_intent
        """
        # Calculate days since publish
        try:
            published_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            days_since = max(0, (datetime.utcnow() - published_date.replace(tzinfo=None)).days)
        except:
            days_since = 0
        
        # Freshness decay
        half_life = self._get_half_life_days(window_days)
        freshness = math.exp(-days_since / half_life)
        
        # Engagement rate
        engagement_rate = (likes + 2 * comments) / views if views > 0 else 0
        
        # Video intent score
        video_intent = math.log10(views + 1) * engagement_rate * freshness
        
        return {
            'days_since_publish': days_since,
            'freshness': round(freshness, 4),
            'engagement_rate': round(engagement_rate, 6),
            'video_intent': round(video_intent, 4)
        }
    
    def calculate_intent_score(
        self,
        videos: List[Dict],
        keyword: str,
        region: str,
        window_days: int,
        lang: str
    ) -> Dict:
        """
        Calculate intent scores for all videos and aggregate metrics.
        
        Args:
            videos: List of video detail items from YouTube API
            keyword: Search keyword
            region: Country code
            window_days: Window in days
            lang: Language code
            
        Returns:
            Dictionary with processed videos, intent_score, and aggregates
        """
        logger.info(
            f'Calculating YouTube intent scores',
            keyword=keyword,
            region=region,
            videos_count=len(videos)
        )
        
        processed_videos = []
        total_views = 0
        weighted_intent_sum = 0
        
        for video in videos:
            # Extract base fields
            video_id = video.get('id', '')
            snippet = video.get('snippet', {})
            statistics = video.get('statistics', {})
            content_details = video.get('contentDetails', {})
            
            views = self._safe_number(statistics.get('viewCount', 0))
            likes = self._safe_number(statistics.get('likeCount', 0))
            comments = self._safe_number(statistics.get('commentCount', 0))
            published_at = snippet.get('publishedAt', datetime.utcnow().isoformat())
            
            # Compute features
            features = self.compute_video_features(
                int(views),
                int(likes),
                int(comments),
                published_at,
                window_days
            )
            
            # Build processed video object
            processed_video = {
                'video_id': video_id,
                'title': snippet.get('title', ''),
                'channel_title': snippet.get('channelTitle', ''),
                'published_at': published_at,
                'url': f'https://www.youtube.com/watch?v={video_id}' if video_id else '',
                'duration': content_details.get('duration', ''),
                'views': int(views),
                'likes': int(likes),
                'comments': int(comments),
                **features
            }
            
            processed_videos.append(processed_video)
            
            # Aggregate for intent_score
            total_views += views
            weighted_intent_sum += features['video_intent'] * views
        
        # Calculate weighted average intent score
        intent_score = (weighted_intent_sum / total_views) if total_views > 0 else 0
        
        logger.info(
            f'YouTube intent calculated',
            keyword=keyword,
            videos_analyzed=len(processed_videos),
            intent_score=round(intent_score, 4),
            total_views=int(total_views)
        )
        
        return {
            'videos': processed_videos,
            'intent_score': round(intent_score, 4),
            'total_views': int(total_views),
            'videos_analyzed': len(processed_videos)
        }


# Singleton instance
youtube_intent_service = YouTubeIntentService()

__all__ = ['YouTubeIntentService', 'youtube_intent_service']
