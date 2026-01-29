"""Date utilities for trend analysis."""
from datetime import datetime, timedelta
from typing import Tuple


def get_date_range(window_days: int, baseline_days: int) -> Tuple[datetime, datetime]:
    """
    Calculate start and end dates for trend analysis.
    
    Args:
        window_days: Recent window for analysis (e.g., 30 days)
        baseline_days: Historical baseline period (e.g., 365 days)
        
    Returns:
        Tuple of (start_date, end_date)
        
    Example:
        >>> get_date_range(30, 365)
        (datetime(2025, 1, 28), datetime(2026, 1, 28))
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=baseline_days)
    
    return start_date, end_date


def format_date(date: datetime) -> str:
    """Format datetime to YYYY-MM-DD string."""
    return date.strftime('%Y-%m-%d')


def parse_date(date_str: str) -> datetime:
    """Parse YYYY-MM-DD string to datetime."""
    return datetime.strptime(date_str, '%Y-%m-%d')


__all__ = ['get_date_range', 'format_date', 'parse_date']
