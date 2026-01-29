"""Scoring Service - Calculate trend scores and signals."""
from typing import List, Dict, Tuple
from loguru import logger


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp value between min and max."""
    return max(min_val, min(max_val, value))


def average(values: List[float]) -> float:
    """Calculate average of array values."""
    if not values or len(values) == 0:
        return 0.0
    return sum(values) / len(values)


def max_value(values: List[float]) -> float:
    """Calculate max of array values."""
    if not values or len(values) == 0:
        return 0.0
    return max(values)


class ScoringService:
    """
    Scoring Service - Calculates trend score and generates explanations.
    
    The trend score (0-100) is calculated based on three signals:
    - Growth: Recent 7 days vs last 30 days average (50% weight)
    - Slope: 14-day linear regression trend (30% weight)
    - Peak: Recent peak in last 30 days (20% weight)
    """
    
    def calculate_score(
        self,
        time_series: List[Dict],
        keyword: str,
        country: str,
        window_days: int = 7,
        baseline_days: int = 30
    ) -> Dict:
        """
        Calculate trend score and signals from time series data.
        
        Args:
            time_series: List of {'date': str, 'value': int} dicts
            keyword: Search keyword
            country: Country code
            window_days: Recent window period in days (default: 7)
            baseline_days: Baseline comparison period in days (default: 30)
            
        Returns:
            Dictionary with trendScore, signals, and explain
        """
        if not time_series or len(time_series) == 0:
            raise ValueError('Time series data is empty')
        
        logger.info(
            f'Calculating trend score',
            keyword=keyword,
            country=country,
            data_points=len(time_series)
        )
        
        # Extract values only
        values = [point['value'] for point in time_series]
        
        # Calculate signals
        signals = {
            'growth_7_vs_30': self._calculate_growth_7vs30(values),
            'slope_14d': self._calculate_slope_14d(values),
            'recent_peak_30d': self._calculate_recent_peak_30d(values)
        }
        
        # Calculate final score (0-100)
        trend_score = self._calculate_final_score(signals)
        
        # Generate explanations
        explain = self._generate_explanations(
            signals,
            keyword,
            country,
            window_days,
            baseline_days
        )
        
        logger.info(
            f'Trend score calculated',
            keyword=keyword,
            country=country,
            trend_score=trend_score,
            signals=signals
        )
        
        return {
            'trendScore': round(trend_score, 2),
            'signals': {
                'growth_7_vs_30': round(signals['growth_7_vs_30'], 2),
                'slope_14d': round(signals['slope_14d'], 4),
                'recent_peak_30d': round(signals['recent_peak_30d'], 2)
            },
            'explain': explain
        }
    
    def _calculate_growth_7vs30(self, values: List[float]) -> float:
        """
        Calculate growth: avg(last 7 days) / avg(last 30 days).
        
        Returns ratio (1.0 = no change, >1.0 = growth, <1.0 = decline)
        """
        last_7 = values[-7:] if len(values) >= 7 else values
        last_30 = values[-30:] if len(values) >= 30 else values
        
        if len(last_7) == 0 or len(last_30) == 0:
            return 1.0  # Neutral if not enough data
        
        avg_7 = average(last_7)
        avg_30 = average(last_30)
        
        # Avoid division by zero
        return avg_7 / avg_30 if avg_30 > 0 else 1.0
    
    def _calculate_slope_14d(self, values: List[float]) -> float:
        """
        Calculate slope of last 14 days using linear regression.
        
        Returns normalized slope (scale-independent)
        """
        last_14 = values[-14:] if len(values) >= 14 else values
        
        if len(last_14) < 2:
            return 0.0  # Not enough data for slope
        
        n = len(last_14)
        x = list(range(n))  # [0, 1, 2, ..., n-1]
        y = last_14
        
        # Calculate means
        mean_x = average(x)
        mean_y = average(y)
        
        # Calculate slope: Σ((x - meanX) * (y - meanY)) / Σ((x - meanX)²)
        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denominator = sum((x[i] - mean_x) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        
        # Normalize slope by dividing by mean value to make it scale-independent
        slope = numerator / denominator
        normalized_slope = slope / mean_y if mean_y > 0 else slope
        
        return normalized_slope
    
    def _calculate_recent_peak_30d(self, values: List[float]) -> float:
        """
        Calculate recent peak: max(last 30 days) / 100.
        
        Returns normalized peak (0-1, where 1 = maximum Google Trends value)
        """
        last_30 = values[-30:] if len(values) >= 30 else values
        
        if len(last_30) == 0:
            return 0.0
        
        max_val = max_value(last_30)
        return max_val / 100.0  # Normalize to 0-1 (Google Trends is 0-100)
    
    def _calculate_final_score(self, signals: Dict) -> float:
        """
        Calculate final trend score (0-100).
        
        Formula: 100 * clamp(0.5*G + 0.3*S + 0.2*P, 0, 1)
        
        Where:
        - G: Growth signal (normalized to 0-1)
        - S: Slope signal (normalized to 0-1)
        - P: Peak signal (already 0-1)
        """
        # Normalize growth to 0-1 range
        # Growth 0.7-1.7 maps to 0-1
        G = clamp((signals['growth_7_vs_30'] - 0.7) / (1.7 - 0.7), 0, 1)
        
        # Normalize slope to 0-1 range
        # Slope -0.5 to +0.5 maps to 0-1
        S = clamp((signals['slope_14d'] + 0.5) / 1.0, 0, 1)
        
        # Peak is already normalized (0-1)
        P = signals['recent_peak_30d']
        
        # Weighted combination
        score = 0.5 * G + 0.3 * S + 0.2 * P
        
        # Scale to 0-100
        return clamp(score, 0, 1) * 100
    
    def _generate_explanations(
        self,
        signals: Dict,
        keyword: str,
        country: str,
        window_days: int,
        baseline_days: int
    ) -> List[str]:
        """Generate human-readable explanations in Spanish."""
        explanations = []
        
        # Helper function to format days into human-readable text
        def format_period(days: int) -> str:
            if days >= 365:
                years = round(days / 365, 1)
                return f'{years} años' if years != 1 else '1 año'
            elif days >= 30:
                months = round(days / 30, 1)
                return f'{months} meses' if months != 1 else '1 mes'
            else:
                return f'{days} días' if days != 1 else '1 día'
        
        window_text = format_period(window_days)
        baseline_text = format_period(baseline_days)
        
        # Growth explanation
        growth_percent = abs(round((signals['growth_7_vs_30'] - 1) * 100, 1))
        
        if signals['growth_7_vs_30'] > 1.1:
            explanations.append(
                f'El interés en los últimos {window_text} creció {growth_percent}% vs los últimos {baseline_text}.'
            )
        elif signals['growth_7_vs_30'] < 0.9:
            explanations.append(
                f'El interés en los últimos {window_text} cayó {growth_percent}% vs los últimos {baseline_text}.'
            )
        else:
            explanations.append(
                f'El interés en los últimos {window_text} se mantiene estable respecto a los últimos {baseline_text}.'
            )
        
        # Slope explanation (uses last 14 days or 2*window_days, whichever is smaller)
        slope_period = min(14, window_days * 2)
        slope_text = format_period(slope_period)
        
        if signals['slope_14d'] > 0.01:
            explanations.append(f'La tendencia de los últimos {slope_text} es positiva (creciente).')
        elif signals['slope_14d'] < -0.01:
            explanations.append(f'La tendencia de los últimos {slope_text} es negativa (decreciente).')
        else:
            explanations.append(f'La tendencia de los últimos {slope_text} es plana (sin cambios significativos).')
        
        # Peak explanation (uses last 30 days or window_days, whichever is larger)
        peak_period = max(30, window_days)
        peak_text = format_period(peak_period)
        peak_percent = round(signals['recent_peak_30d'] * 100)
        
        if signals['recent_peak_30d'] > 0.8:
            explanations.append(
                f'El interés en los últimos {peak_text} alcanzó {peak_percent}% del máximo posible.'
            )
        elif signals['recent_peak_30d'] > 0.5:
            explanations.append(
                f'El interés está en niveles moderados ({peak_percent}% del máximo en los últimos {peak_text}).'
            )
        else:
            explanations.append(
                f'El interés está en niveles bajos ({peak_percent}% del máximo en los últimos {peak_text}).'
            )
        
        # Country context
        explanations.append(f'Los datos corresponden al país {country}.')
        
        return explanations


# Singleton instance
scoring_service = ScoringService()

__all__ = ['ScoringService', 'scoring_service']
