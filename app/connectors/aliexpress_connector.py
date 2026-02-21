"""AliExpress Affiliate API Connector (Portals + TOP)."""
import os
import time
import json
import hashlib
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from loguru import logger


class AliExpressConnector:
    """
    AliExpress Affiliate connector (Portals gateway + TOP router).
    Portals Base URL: https://api-sg.aliexpress.com/sync
    TOP Base URL: https://eco.taobao.com/router/rest
    """

    BASE_URL = 'https://api-sg.aliexpress.com/sync'
    TOP_BASE_URL = 'https://eco.taobao.com/router/rest'
    CATEGORY_MAP_PATH = os.path.join('results', 'category_map.json')

    def __init__(self):
        self.app_key = os.getenv('ALIEXPRESS_APP_KEY', '')
        self.app_secret = os.getenv('ALIEXPRESS_APP_SECRET', '')
        self.tracking_id = os.getenv('ALIEXPRESS_TRACKING_ID', '')


        if not self.app_key or not self.app_secret:
            logger.warning('AliExpress credentials missing. Set ALIEXPRESS_APP_KEY and ALIEXPRESS_APP_SECRET in .env')


        # Simple in-memory cache with TTL (6 hours)
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 6 * 60 * 60

    def product_query(
        self,
        keywords: str,
        ship_to_country: str,
        target_currency: str,
        target_language: str,
        page_no: int,
        page_size: int
    ) -> Dict[str, Any]:
        """
        Call aliexpress.affiliate.product.query and return normalized data.
        """
        self._validate_credentials()

        cache_key = f"{keywords}|{ship_to_country}|{target_currency}|{target_language}|{page_no}|{page_size}"
        cached = self._cache_get(cache_key)
        if cached:
            cached['cache_hit'] = True
            return cached

        business_params = {
            'keywords': keywords,
            'ship_to_country': ship_to_country,
            'target_currency': target_currency,
            'target_language': target_language,
            'page_no': page_no,
            'page_size': page_size,
            'sort': 'LAST_VOLUME_DESC',
            'fields': 'product_id,product_title,sale_price,discount,evaluate_rate,lastest_volume,product_detail_url,shop_id,shop_url,promotion_link,category_id,first_level_category_id'
        }

        if self.tracking_id:
            business_params['tracking_id'] = self.tracking_id

        response = self._call_api('aliexpress.affiliate.product.query', business_params)
        normalized = self._normalize_response(response, keywords, ship_to_country, target_currency, target_language, page_no, page_size)

        self._cache_set(cache_key, normalized)
        return normalized

    def _call_api(self, method: str, business_params: Dict[str, Any]) -> Dict[str, Any]:
        public_params = {
            'method': method,
            'app_key': self.app_key,
            'sign_method': 'md5',
            'timestamp': self._timestamp(),
            'v': '2.0',
            'format': 'json'
        }

        all_params = {**public_params}
        for key, value in business_params.items():
            if value is not None:
                all_params[key] = str(value)

        sign = self._sign_params(all_params)
        all_params['sign'] = sign

        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        logger.info(
            'AliExpress request',
            method=method,
            app_key=self.app_key,
            timestamp=public_params['timestamp'],
            params={k: v for k, v in all_params.items() if k not in ['sign']}
        )
        logger.info(f'AliExpress request URL: {self.BASE_URL}')
        logger.info(f'AliExpress app_key in use: {self.app_key}')

        response = self._request_with_retry(all_params, headers)
        data = response.json()

        if 'error_response' in data:
            err = data['error_response']
            logger.error(f'AliExpress API error_response: {err}')
            msg = err.get('sub_msg') or err.get('msg') or 'AliExpress API error'
            raise Exception(msg)

        return data

    def _call_top_api(self, method: str, business_params: Dict[str, Any]) -> Dict[str, Any]:
        """Call TOP router API (eco.taobao.com)."""
        public_params = {
            'method': method,
            'app_key': self.app_key,
            'sign_method': 'md5',
            'timestamp': self._timestamp(),
            'v': '2.0',
            'format': 'json'
        }

        all_params = {**public_params}
        for key, value in business_params.items():
            if value is not None:
                all_params[key] = str(value)

        sign = self._sign_params(all_params)
        all_params['sign'] = sign

        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        logger.info(
            'AliExpress TOP category request',
            method=method,
            app_key=self.app_key,
            timestamp=public_params['timestamp'],
            params={k: v for k, v in all_params.items() if k not in ['sign']},
            url=self.TOP_BASE_URL
        )

        response = self._request_with_retry(all_params, headers, url=self.TOP_BASE_URL)
        data = response.json()

        if 'error_response' in data:
            err = data['error_response']
            logger.error(f'AliExpress TOP error_response: {err}')
            msg = err.get('sub_msg') or err.get('msg') or 'AliExpress TOP API error'
            raise Exception(msg)

        return data

    def _request_with_retry(self, params: Dict[str, str], headers: Dict[str, str], url: Optional[str] = None) -> requests.Response:
        max_attempts = 3
        base_delay = 0.5
        target_url = url or self.BASE_URL

        for attempt in range(max_attempts):
            try:
                response = requests.post(
                    target_url,
                    data=params,
                    headers=headers,
                    timeout=30
                )

                logger.info(
                    'AliExpress response',
                    status_code=response.status_code,
                    url=response.url
                )

                if response.status_code != 200:
                    logger.error(
                        'AliExpress error response body',
                        body=response.text
                    )

                if response.status_code >= 500 or response.status_code == 429:
                    raise requests.RequestException(f'HTTP {response.status_code}')

                response.raise_for_status()
                return response
            except Exception as error:
                if attempt == max_attempts - 1:
                    raise error
                time.sleep(base_delay * (2 ** attempt))

        raise Exception('AliExpress request failed after retries')

    def _sign_params(self, params: Dict[str, str]) -> str:
        sorted_keys = sorted(params.keys())
        canonical = ''.join([key + params[key] for key in sorted_keys])
        raw = f"{self.app_secret}{canonical}{self.app_secret}"
        digest = hashlib.md5(raw.encode('utf-8')).hexdigest()
        return digest.upper()

    def _timestamp(self) -> str:
        return str(int(time.time()))

    def _normalize_response(
        self,
        response: Dict[str, Any],
        keywords: str,
        ship_to_country: str,
        target_currency: str,
        target_language: str,
        page_no: int,
        page_size: int
    ) -> Dict[str, Any]:
        result = response.get('aliexpress_affiliate_product_query_response', {}).get('resp_result', {}).get('result', {})
        products = result.get('products', {}).get('product', [])
        if isinstance(products, dict):
            products = [products]

        competitors = [self._normalize_product(p) for p in products]

        return {
            'query': {
                'keywords': keywords,
                'ship_to_country': ship_to_country,
                'target_currency': target_currency,
                'target_language': target_language,
                'page': page_no,
                'page_size': page_size
            },
            'paging': {
                'page': page_no,
                'page_size': page_size,
                'total': result.get('total_record_count', 0)
            },
            'competitors': competitors,
            'generated_at': datetime.utcnow().isoformat()
        }

    def _normalize_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        volume = self._to_number(product.get('lastest_volume'))
        rate = self._to_rate(product.get('evaluate_rate'))
        sell_score = round(volume * rate)

        category_id = product.get('category_id') or product.get('first_level_category_id') or ''

        return {
            'product_id': product.get('product_id', ''),
            'product_title': product.get('product_title', ''),
            'sale_price': product.get('sale_price', ''),
            'discount': product.get('discount', ''),
            'evaluate_rate': product.get('evaluate_rate', ''),
            'lastest_volume': volume,
            'product_detail_url': product.get('product_detail_url', ''),
            'shop_id': product.get('shop_id', ''),
            'shop_url': product.get('shop_url', ''),
            'promotion_link': product.get('promotion_link', ''),
            'category_id': category_id,
            'first_level_category_id': product.get('first_level_category_id', ''),
            'sell_score': sell_score
        }

    def get_category_children(self, parent_id: int) -> List[Dict[str, Any]]:
        """
        Fetch child categories from TOP router.

        Uses: aliexpress.category.redefining.getchildrenpostcategorybyid (param0=parent_id)
        Returns list of raw category objects.
        """
        self._validate_credentials()

        business_params = {
            'param0': int(parent_id)
        }

        response = self._call_top_api('aliexpress.category.redefining.getchildrenpostcategorybyid', business_params)

        root = response.get('aliexpress_category_redefining_getchildrenpostcategorybyid_response', {})
        result = root.get('result', {})
        if not result.get('success'):
            return []

        lst = result.get('aeop_post_category_list', {}).get('aeop_post_category_dto', [])
        if isinstance(lst, dict):
            lst = [lst]
        return lst

    def build_category_tree(self, lang: str = 'es') -> Dict[str, Dict[str, Any]]:
        """
        Build full category tree and save it to results/category_map.json.
        Returns a map: { category_id: { name, path, level, is_leaf } }
        """
        self._validate_credentials()

        category_map: Dict[str, Dict[str, Any]] = {}
        visited: set[int] = set()

        queue: List[tuple[int, str, int]] = []

        logger.info('Building AliExpress category tree...')

        roots = self.get_category_children(0)
        for category in roots:
            cid = int(category.get('id'))
            name = self._pick_name(category.get('names'), lang=lang)
            level = int(category.get('level', 1))
            is_leaf = bool(category.get('isleaf', False))

            path = name
            category_map[str(cid)] = {
                'name': name,
                'path': path,
                'level': level,
                'is_leaf': is_leaf
            }

            visited.add(cid)
            queue.append((cid, path, level))

        while queue:
            parent_id, parent_path, parent_level = queue.pop(0)
            children = self.get_category_children(parent_id)
            for category in children:
                cid = int(category.get('id'))
                if cid in visited:
                    continue

                name = self._pick_name(category.get('names'), lang=lang)
                level = int(category.get('level', parent_level + 1))
                is_leaf = bool(category.get('isleaf', False))

                path = f"{parent_path} > {name}" if parent_path else name
                category_map[str(cid)] = {
                    'name': name,
                    'path': path,
                    'level': level,
                    'is_leaf': is_leaf
                }

                visited.add(cid)
                queue.append((cid, path, level))

        os.makedirs(os.path.dirname(self.CATEGORY_MAP_PATH), exist_ok=True)
        with open(self.CATEGORY_MAP_PATH, 'w', encoding='utf-8') as f:
            json.dump(category_map, f, ensure_ascii=False, indent=2)

        logger.info('AliExpress category map saved', total=len(category_map), path=self.CATEGORY_MAP_PATH)
        return category_map

    def _pick_name(self, names_field: Any, lang: str = 'es') -> str:
        """Pick localized name from names map or JSON string."""
        if not names_field:
            return ''

        if isinstance(names_field, str):
            try:
                names = json.loads(names_field)
            except Exception:
                return names_field
        else:
            names = names_field

        return (
            names.get(lang)
            or names.get(lang.lower())
            or names.get('en')
            or next(iter(names.values()), '')
        )

    def get_category_name(self, category_id: int) -> Optional[str]:
        """Return category name or path from category_map.json."""
        try:
            if not os.path.exists(self.CATEGORY_MAP_PATH):
                return None
            with open(self.CATEGORY_MAP_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            entry = data.get(str(category_id))
            if not entry:
                return None
            return entry.get('name') or entry.get('path')
        except Exception as error:
            logger.error('Failed to read category_map.json', error=str(error))
            return None

    def _to_number(self, value: Any) -> int:
        if value is None:
            return 0
        try:
            cleaned = ''.join([c for c in str(value) if c.isdigit() or c == '.'])
            return int(float(cleaned)) if cleaned else 0
        except Exception:
            return 0

    def _to_rate(self, value: Any) -> float:
        if value is None:
            return 0.0
        try:
            s = str(value).replace('%', '')
            num = float(s)
            return num / 100 if num > 1 else num
        except Exception:
            return 0.0

    def _cache_get(self, key: str) -> Dict[str, Any] | None:
        entry = self.cache.get(key)
        if not entry:
            return None
        if time.time() > entry['expires_at']:
            self.cache.pop(key, None)
            return None
        return entry['value']

    def _cache_set(self, key: str, value: Dict[str, Any]) -> None:
        self.cache[key] = {
            'value': value,
            'expires_at': time.time() + self.cache_ttl
        }

    def _validate_credentials(self) -> None:
        if not self.app_key or not self.app_secret:
            raise ValueError('Missing ALIEXPRESS_APP_KEY or ALIEXPRESS_APP_SECRET in .env')



aliexpress_connector = AliExpressConnector()

__all__ = ['aliexpress_connector', 'AliExpressConnector']