"""Google Trends Connector using pytrends library."""
import os
import re
import time
import math
import random
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests as _requests_lib  # kept for potential future proxy checks
from pytrends.request import TrendReq
from loguru import logger

# Global lock — serializes ALL pytrends requests across threads/greenlets
_GLOBAL_REQUEST_LOCK = threading.Lock()

# Detect test mode
IS_TEST_MODE = os.getenv('NODE_ENV') == 'test'

# User agents más realistas para evitar bloqueos
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15',
]


def generate_mock_time_series(keyword: str, baseline_days: int) -> List[Dict]:
    """
    Generate mock time series data for testing.
    Deterministic based on keyword to ensure consistency.
    """
    total_days = baseline_days + 1
    series = []
    start_date = datetime.now() - timedelta(days=baseline_days)
    
    # Generate seed from keyword
    seed = sum(ord(char) for char in keyword)
    
    for i in range(total_days):
        date = start_date + timedelta(days=i)
        
        # Generate deterministic but varied values
        day_offset = i / total_days
        base_value = 30 + (seed % 40)
        trend = math.sin(day_offset * math.pi * 4) * 20
        noise = ((seed * (i + 1)) % 30) - 15
        
        value = max(0, min(100, round(base_value + trend + noise)))
        
        series.append({
            'date': date.strftime('%Y-%m-%d'),
            'value': value
        })
    
    return series


def generate_mock_by_country(keyword: str, country: str) -> List[Dict]:
    """
    Generate mock country comparison data for testing.
    Deterministic based on keyword to ensure consistency.
    """
    seed = sum(ord(char) for char in keyword)
    countries = ['MX', 'CR', 'ES']
    
    result = []
    for country_code in countries:
        if country_code == country:
            value = 80 + (seed % 21)
        else:
            offset = ord(country_code[0]) + ord(country_code[1])
            value = max(0, min(79, (seed + offset) % 80))
        
        result.append({'country': country_code, 'value': value})
    
    # Sort by value descending
    result.sort(key=lambda x: x['value'], reverse=True)
    return result


class GoogleTrendsConnector:
    """
    Google Trends Connector using pytrends library.
    
    Features:
    - Mock mode for testing (when NODE_ENV=test)
    - Retry logic with exponential backoff
    - Anti-blocking delays between requests
    - Concurrency control (locks)
    
    PyTrends is more stable than google-trends-api (Node.js),
    but Google can still block requests if too frequent.
    """
    
    def __init__(self):
        """Initialize connector with configuration from environment."""
        self.max_retries = int(os.getenv('GOOGLE_TRENDS_MAX_RETRIES', 5))
        self.retry_delay = int(os.getenv('GOOGLE_TRENDS_RETRY_DELAY_MS', 15000)) / 1000  # Convert to seconds
        self.request_delay = int(os.getenv('GOOGLE_TRENDS_REQUEST_DELAY_MS', 10000)) / 1000
        self.timeout = int(os.getenv('GOOGLE_TRENDS_TIMEOUT_MS', 90000)) / 1000
        self.concurrency = int(os.getenv('GOOGLE_TRENDS_CONCURRENCY', 1))

        # Proxy support (respects standard env vars or custom GOOGLE_TRENDS_PROXY)
        self.proxy = (
            os.getenv('GOOGLE_TRENDS_PROXY') or
            os.getenv('HTTPS_PROXY') or
            os.getenv('HTTP_PROXY') or
            ''
        )

        # Cookie support — paste browser cookies here to bypass 429 IP bans
        # Get from DevTools → Network → trends.google.com → request headers → Cookie
        raw_cookies = os.getenv('GOOGLE_TRENDS_COOKIES', '')
        self.cookies = self._parse_cookies(raw_cookies) if raw_cookies else {}

        # Lock for concurrency control (uses the module-level global lock)
        self.request_lock = _GLOBAL_REQUEST_LOCK
        self.pytrends = None  # Will be initialized per request
        
        if IS_TEST_MODE:
            logger.info('🧪 Google Trends Connector - MOCK MODE (No API calls will be made)')
        else:
            logger.info(
                f'🌐 Google Trends Connector - REAL API MODE (Enhanced Anti-block)\n'
                f'   Max Retries: {self.max_retries}\n'
                f'   Retry Delay: {self.retry_delay}s\n'
                f'   Request Delay: {self.request_delay}s\n'
                f'   Timeout: {self.timeout}s\n'
                f'   Concurrency: {self.concurrency}\n'
                f'   User Agents: {len(USER_AGENTS)} rotating agents'
            )
    
    def _parse_cookies(self, cookie_string: str) -> Dict[str, str]:
        """Parse a raw Cookie header string into a name→value dict.

        Non-latin-1 characters (e.g. the Unicode ellipsis '…' that DevTools
        inserts when truncating a long value) are stripped so that the
        requests library never hits a UnicodeEncodeError when building headers.
        """
        # Remove any character that HTTP headers cannot carry (must be latin-1)
        safe_string = cookie_string.encode('latin-1', errors='ignore').decode('latin-1')
        cookies: Dict[str, str] = {}
        for part in safe_string.split(';'):
            part = part.strip()
            if '=' in part:
                name, _, value = part.partition('=')
                cookies[name.strip()] = value.strip()
        if safe_string != cookie_string:
            logger.warning(
                '🍪 Cookie string contained non-latin-1 characters (likely DevTools truncation). '
                'Re-copy the full cookie value from DevTools for best results.'
            )
        return cookies

    def _get_fresh_client(self):
        """Create a fresh pytrends client with random user agent to avoid blocks.

        pytrends already calls GetGoogleCookie() in __init__, which visits
        trends.google.com/explore to obtain the NID cookie automatically.
        We just need to set realistic headers and inject any user-provided cookies.
        """
        user_agent = random.choice(USER_AGENTS)
        logger.debug(f'🔧 Creating fresh pytrends client')
        logger.debug(f'📱 User-Agent: {user_agent[:80]}...')

        # Mimic a real browser as closely as possible
        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        }

        requests_args: Dict = {'headers': headers}

        if self.proxy:
            requests_args['proxies'] = {'http': self.proxy, 'https': self.proxy}
            logger.debug(f'🌐 Routing through proxy: {self.proxy[:50]}')

        # TrendReq.__init__ calls GetGoogleCookie() which visits
        # trends.google.com/explore — so client.cookies already has NID on return.
        client = TrendReq(
            hl='en-US',
            tz=360,
            timeout=(self.timeout, self.timeout),
            retries=0,
            backoff_factor=0,
            requests_args=requests_args
        )

        nid_from_pytrends = 'NID' in (client.cookies or {})
        logger.debug(f'🍪 pytrends GetGoogleCookie NID present: {nid_from_pytrends} | cookies={list((client.cookies or {}).keys())}')

        # Inject user-provided cookies on top (override if same key)
        if self.cookies:
            client.cookies = {**(client.cookies or {}), **self.cookies}
            logger.debug(f'🍪 Merged user-provided cookies: {list(self.cookies.keys())}')

        return client
    
    def fetch_complete(
        self,
        keyword: str,
        country: str,
        window_days: int,
        baseline_days: int
    ) -> Dict:
        """
        Fetch complete trend data: time series + country comparison.
        
        Args:
            keyword: Search keyword
            country: ISO 2-letter country code (MX, CR, ES)
            window_days: Recent window for analysis
            baseline_days: Historical baseline period
            
        Returns:
            Dictionary with timeSeries and byCountry data
        """
        # Test mode: return mocks immediately
        if IS_TEST_MODE:
            time.sleep(0.005)  # Simulate minimal delay
            return {
                'timeSeries': generate_mock_time_series(keyword, baseline_days),
                'byCountry': generate_mock_by_country(keyword, country),
                'source': 'mock',
                'fetchedAt': datetime.utcnow().isoformat()
            }
        
        try:
            logger.info(
                f'🔍 Fetching complete trend data from Google Trends API',
                keyword=keyword,
                country=country,
                window_days=window_days,
                baseline_days=baseline_days
            )
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=baseline_days)
            
            # Longer initial delay (5-10s) to appear more human and reduce IP bans
            initial_delay = 5 + random.random() * 5
            logger.info(f'⏳ Initial delay: {round(initial_delay, 1)}s (anti-bot measure)')
            time.sleep(initial_delay)

            # Create ONE shared client — GetGoogleCookie() is called only once per fetch_complete()
            client = self._get_fresh_client()
            logger.debug(f'🔑 Shared client NID present: {"NID" in (client.cookies or {})}')

            # Fetch time series with retry logic (reuses the same client)
            time_series = self._fetch_with_retry(
                lambda: self._fetch_time_series(keyword, country, start_date, end_date, client)
            )

            # Longer delay between the two calls (30-45s) — fresh quota window
            delay_between_requests = 30 + random.random() * 15
            logger.info(
                f'⏳ Waiting {round(delay_between_requests, 1)}s before fetching country data (rate-limit window)...'
            )
            time.sleep(delay_between_requests)

            # Fetch country comparison — graceful: if 429, return empty and keep time series
            by_country = []
            try:
                by_country = self._fetch_with_retry(
                    lambda: self._fetch_by_country(keyword, client)
                )
            except Exception as country_err:
                err_msg = str(country_err)
                is_rate_limit = '429' in err_msg or 'TooManyRequests' in type(country_err).__name__
                if is_rate_limit:
                    logger.warning(
                        f'⚠️  Country comparison skipped (Google 429 on by_region endpoint) '
                        f'— returning time series only. Try again in a few minutes.',
                        keyword=keyword
                    )
                else:
                    logger.warning(
                        f'⚠️  Country comparison failed ({type(country_err).__name__}: {err_msg[:200]}) '
                        f'— returning time series only.',
                        keyword=keyword
                    )

            logger.info(
                f'✅ Successfully fetched Google Trends data',
                keyword=keyword,
                country=country,
                data_points=len(time_series),
                by_country_available=len(by_country) > 0
            )

            return {
                'timeSeries': time_series,
                'byCountry': by_country,
                'source': 'google_trends',
                'fetchedAt': datetime.utcnow().isoformat()
            }
            
        except Exception as error:
            logger.error(
                f'❌ Failed to fetch Google Trends data',
                error=str(error),
                keyword=keyword,
                country=country
            )
            raise
    
    def _fetch_time_series(
        self,
        keyword: str,
        country: str,
        start_date: datetime,
        end_date: datetime,
        client: Optional[TrendReq] = None
    ) -> List[Dict]:
        """Fetch time series data for a keyword in a specific country."""
        logger.info(
            f'Fetching time series from Google Trends',
            keyword=keyword,
            country=country,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )

        pytrends = client or self._get_fresh_client()
        
        # Build payload for pytrends
        timeframe = f'{start_date.strftime("%Y-%m-%d")} {end_date.strftime("%Y-%m-%d")}'
        
        logger.debug(f'📦 Building payload: keyword={keyword}, timeframe={timeframe}, geo={country}')
        
        pytrends.build_payload(
            kw_list=[keyword],
            cat=0,
            timeframe=timeframe,
            geo=country,
            gprop=''
        )
        
        logger.debug(f'🌐 Calling pytrends.interest_over_time()...')
        
        # Get interest over time
        try:
            df = pytrends.interest_over_time()
            logger.debug(f'✅ Got response from Google Trends, checking data...')
        except Exception as e:
            logger.error(f'❌ Exception from pytrends: {type(e).__name__}: {str(e)[:500]}')
            raise
        
        if df.empty:
            logger.warning(f'No data returned from Google Trends for {keyword}')
            return []
        
        # Convert to list of dictionaries
        result = []
        for date_index, row in df.iterrows():
            result.append({
                'date': date_index.strftime('%Y-%m-%d'),
                'value': int(row[keyword]) if keyword in row else 0
            })
        
        logger.info(f'Successfully fetched time series ({len(result)} data points)')
        return result
    
    def _fetch_by_country(self, keyword: str, client: Optional[TrendReq] = None) -> List[Dict]:
        """Fetch country comparison data for a keyword (global, last 12 months)."""
        logger.info(f'Fetching country comparison from Google Trends', keyword=keyword)

        pytrends = client or self._get_fresh_client()

        # Log active cookie names (not values) so we can verify session state
        cookie_names = list(pytrends.cookies.keys()) if hasattr(pytrends, 'cookies') else []
        logger.debug(f'🍪 Active cookie names in session: {cookie_names}')

        timeframe = 'today 12-m'
        logger.debug(f'📦 Building payload: keyword={keyword}, timeframe={timeframe}, geo=(worldwide)')

        # Build payload for last 12 months, worldwide
        pytrends.build_payload(
            kw_list=[keyword],
            cat=0,
            timeframe=timeframe,
            geo='',
            gprop=''
        )

        logger.debug(f'🌐 Calling pytrends.interest_by_region()...')
        try:
            df = pytrends.interest_by_region(resolution='COUNTRY', inc_low_vol=True)
            logger.debug(f'✅ Got interest_by_region response — shape: {df.shape}, columns: {list(df.columns)}')
        except Exception as e:
            # Try to capture the HTTP response code if available
            resp_info = ''
            if hasattr(e, 'response') and e.response is not None:
                resp_info = f' | HTTP {e.response.status_code} | headers: {dict(e.response.headers)}'
            logger.error(f'❌ Exception from interest_by_region: {type(e).__name__}: {str(e)[:500]}{resp_info}')
            raise

        if df.empty:
            logger.warning(f'No country data returned from Google Trends for {keyword}')
            return []

        # Filter for supported countries and convert to list
        supported_countries = ['MX', 'CR', 'ES']
        result = []

        for country_code, row in df.iterrows():
            if country_code in supported_countries:
                result.append({
                    'country': country_code,
                    'value': int(row[keyword]) if keyword in row else 0
                })

        # Sort by value descending
        result.sort(key=lambda x: x['value'], reverse=True)

        logger.info(f'Successfully fetched country comparison ({len(result)} countries)')
        return result
    
    def _fetch_with_retry(self, fetch_fn):
        """
        Retry wrapper with exponential backoff.
        
        Args:
            fetch_fn: Function to execute (no arguments)
            
        Returns:
            Result from fetch_fn
            
        Raises:
            Exception after all retries exhausted
        """
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f'🔄 Attempt {attempt}/{self.max_retries} (waiting for global lock...)')
                with self.request_lock:
                    logger.debug(f'🔓 Lock acquired — running request')
                    return fetch_fn()
            except Exception as error:
                last_error = error

                # Detect if Google blocked with HTML response
                error_message = str(error)
                error_type = type(error).__name__

                # Log the FULL error for debugging
                logger.debug(f'🐛 Full error type: {error_type}')
                logger.debug(f'🐛 Full error message (first 1000 chars): {error_message[:1000]}')

                # Log HTTP response details and auto-refresh NID cookie from Set-Cookie header
                if hasattr(error, 'response') and error.response is not None:
                    r = error.response
                    retry_after = r.headers.get('Retry-After', 'not set')
                    logger.debug(
                        f'🔎 HTTP response details | status={r.status_code} '
                        f'| Retry-After={retry_after} '
                        f'| Content-Type={r.headers.get("Content-Type", "?")} '
                        f'| body_preview={r.text[:300]!r}'
                    )
                    # Google often sends a fresh NID in the 429 Set-Cookie — use it next attempt
                    set_cookie = r.headers.get('Set-Cookie', '')
                    nid_match = re.search(r'NID=([^;]+)', set_cookie)
                    if nid_match:
                        new_nid = nid_match.group(1)
                        self.cookies['NID'] = new_nid
                        logger.info(f'🍪 Auto-refreshed NID cookie from 429 response (will use on next attempt)')

                is_rate_limited = 'TooManyRequests' in error_type or '429' in error_message
                is_blocked = (
                    is_rate_limited or
                    'Unexpected token' in error_message or
                    'is not valid JSON' in error_message or
                    '<html' in error_message.lower() or
                    '<!doctype' in error_message.lower() or
                    'Invalid JSON' in error_message or
                    'The request failed' in error_message or
                    'JSONDecodeError' in error_type
                )

                if attempt < self.max_retries:
                    # Exponential backoff con factor aleatorio: base * 1.5^attempt + random(0-5s)
                    # Para 429 usa un delay extra largo (mínimo 30s)
                    base_delay = max(self.retry_delay, 30) if is_rate_limited else self.retry_delay
                    delay_time = round(base_delay * math.pow(1.5, attempt - 1) + random.random() * 5, 1)

                    logger.warning(
                        f'{"🚫 Google rate-limited (429)" if is_rate_limited else ("🚫 Google BLOCKED request" if is_blocked else "⚠️  Request failed")} '
                        f'- waiting {delay_time}s before retry...',
                        attempt=attempt,
                        max_retries=self.max_retries,
                        error_type=error_type,
                        error=error_message[:150],
                        is_blocked=is_blocked,
                        next_delay_seconds=delay_time
                    )

                    time.sleep(delay_time)
                else:
                    logger.error(
                        f'❌ All retry attempts exhausted',
                        attempt=attempt,
                        max_retries=self.max_retries,
                        error_type=error_type,
                        error=error_message[:500]
                    )

        raise Exception(f'Failed after {self.max_retries} attempts: {str(last_error)}')


# Singleton instance
google_trends_connector = GoogleTrendsConnector()


# Export for testing
__all__ = [
    'GoogleTrendsConnector',
    'google_trends_connector',
    'generate_mock_time_series',
    'generate_mock_by_country'
]
