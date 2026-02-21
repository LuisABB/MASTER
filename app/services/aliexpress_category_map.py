"""AliExpress category map incremental builder (mode-based, no scraping)."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from loguru import logger

from app.connectors.aliexpress_connector import aliexpress_connector

CATEGORY_MAP_PATH = os.path.join('cache', 'category_map.json')
MAX_NEW_CATEGORIES_PER_REQUEST = 5
RESCRAPE_INTERVAL = timedelta(days=1)
CATEGORY_RESOLUTION_MODE = os.getenv('CATEGORY_RESOLUTION_MODE', 'none').strip().lower()

_API_AVAILABLE: Optional[bool] = None
_CATEGORY_TREE_CACHE: Dict[str, Any] = {"loaded_at": None, "by_id": None}
_CATEGORY_TREE_TTL_SECONDS = 6 * 60 * 60

MACRO_TAXONOMY: List[Tuple[str, List[str]]] = [
    ('Electrónica > Cargadores', ['cargador', 'charger', 'charge', 'usb', 'pd', 'fast charge']),
    ('Electrónica > Accesorios', ['cable', 'adaptador', 'adapter', 'hub', 'dock']),
    ('Telefonía > Fundas/Protección', ['funda', 'protector', 'case', 'screen', 'glass', 'vidrio']),
    ('Audio > Auriculares', ['auricular', 'earbud', 'headset', 'audifono', 'in-ear']),
    ('Outdoor > Óptica/Telescopios', ['telescopio', 'monocular', 'binocular', 'optica']),
    ('Hogar > Organizadores', ['organizador', 'brida', 'clip', 'holder', 'soporte'])
]

STOPWORDS = {
    'de', 'para', 'con', 'sin', 'y', 'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
    'the', 'and', 'or', 'for', 'with', 'without', 'a', 'an', 'to', 'of'
}


def load_category_map(path: str = CATEGORY_MAP_PATH) -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}
    except Exception as error:
        logger.error('Failed to read category_map.json', error=str(error))
        return {}


def save_category_map(category_map: Dict[str, Dict[str, Any]], path: str = CATEGORY_MAP_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(category_map, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def extract_unique_category_ids(competitors: Iterable[Dict[str, Any]]) -> Set[str]:
    ids: Set[str] = set()
    for item in competitors:
        cid = item.get('category_id')
        if cid is None:
            continue
        cid_str = str(cid).strip()
        if cid_str:
            ids.add(cid_str)
    return ids


def pick_product_title_for_category(category_id: str, competitors: Iterable[Dict[str, Any]]) -> str:
    for item in competitors:
        if str(item.get('category_id')) == str(category_id):
            return str(item.get('product_title') or '')
    return ''


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-zA-Záéíóúñü0-9]+", (text or '').lower())
    return [t for t in tokens if t and t not in STOPWORDS and len(t) > 2]


def infer_macro_category(title: str) -> Tuple[Optional[str], Optional[str]]:
    title_lower = (title or '').lower()
    for path, keywords in MACRO_TAXONOMY:
        if any(k in title_lower for k in keywords):
            return path.split(' > ')[-1], path
    return None, None


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _now_ts() -> float:
    return datetime.utcnow().timestamp()


def _normalize_cid(cid: Any) -> str:
    return str(cid).strip()


def _should_update(entry: Dict[str, Any]) -> bool:
    confidence = entry.get('confidence')
    if confidence == 'api_verified':
        return False
    fetched_at = _parse_iso(entry.get('updated_at'))
    if not fetched_at:
        return True
    return datetime.utcnow() - fetched_at >= RESCRAPE_INTERVAL


def _mark_api_unavailable(reason: str) -> None:
    global _API_AVAILABLE
    _API_AVAILABLE = False
    logger.warning('AliExpress category API unavailable', reason=reason)


def resolve_category_api(category_id: str) -> Optional[Tuple[str, str]]:
    def _load_category_tree_from_api() -> Optional[Dict[str, Dict[str, Any]]]:
        global _API_AVAILABLE

        if _API_AVAILABLE is False:
            return None

        loaded_at = _CATEGORY_TREE_CACHE["loaded_at"]
        by_id = _CATEGORY_TREE_CACHE["by_id"]
        if loaded_at and by_id and (_now_ts() - loaded_at) < _CATEGORY_TREE_TTL_SECONDS:
            return by_id

        try:
            resp = aliexpress_connector._call_api(
                'aliexpress.affiliate.category.get',
                {}
            )
            _API_AVAILABLE = True
        except Exception as error:
            msg = str(error)
            if any(k in msg.lower() for k in ['invalid method', 'method not found', 'no permission', 'unauthorized']):
                _mark_api_unavailable(msg)
            return None

        if not isinstance(resp, dict):
            return None

        node: Any = resp
        for key in [
            'aliexpress_affiliate_category_get_response',
            'resp_result',
            'result',
            'categories',
            'category'
        ]:
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                node = None
                break

        if not isinstance(node, list):
            return None

        by_id = {}
        for c in node:
            if not isinstance(c, dict):
                continue
            cid = c.get('category_id')
            name = c.get('category_name')
            parent = c.get('parent_category_id')
            if cid is None or not name:
                continue
            by_id[_normalize_cid(cid)] = {
                'name': str(name),
                'parent': _normalize_cid(parent) if parent is not None else None
            }

        _CATEGORY_TREE_CACHE["loaded_at"] = _now_ts()
        _CATEGORY_TREE_CACHE["by_id"] = by_id
        return by_id

    def _build_category_path(cid: str, by_id: Dict[str, Dict[str, Any]], max_depth: int = 10) -> Optional[str]:
        parts: List[str] = []
        cur = cid
        depth = 0
        while cur and depth < max_depth:
            node = by_id.get(cur)
            if not node:
                break
            parts.append(node['name'])
            cur = node.get('parent')
            depth += 1

        if not parts:
            return None

        parts.reverse()
        return ' > '.join(parts)

    cid = _normalize_cid(category_id)
    by_id = _load_category_tree_from_api()
    if not by_id:
        return None

    node = by_id.get(cid)
    if not node:
        return None

    name = node['name']
    path = _build_category_path(cid, by_id) or name
    return name, path


def update_category_map_from_competitors(competitors: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    category_map = load_category_map()
    mode = CATEGORY_RESOLUTION_MODE

    if mode not in {'none', 'api', 'hybrid'}:
        mode = 'none'

    unique_ids = [
        str(x).strip()
        for x in extract_unique_category_ids(competitors)
        if str(x).strip()
    ]
    missing: List[str] = []

    for cid in unique_ids:
        entry = category_map.get(cid)
        if entry is None or _should_update(entry):
            missing.append(cid)

    logger.info('Category map missing_before', missing_before=len(missing), mode=mode)

    scraped_now = 0
    for cid in missing[:MAX_NEW_CATEGORIES_PER_REQUEST]:
        if mode == 'none':
            continue

        title = pick_product_title_for_category(cid, competitors)
        tokens = _tokenize(title)

        if mode == 'api':
            api_result = resolve_category_api(cid)
            if api_result:
                name, path = api_result
                category_map[cid] = {
                    'labels': tokens[:10],
                    'macro_category': name or '',
                    'macro_path': path or name or '',
                    'updated_at': datetime.utcnow().isoformat(),
                    'confidence': 'api_verified'
                }
                scraped_now += 1
                continue

            if _API_AVAILABLE is False:
                continue

        if mode == 'hybrid':
            macro_category, macro_path = infer_macro_category(title)
            confidence = 'inferred' if macro_category else 'unknown'
            category_map[cid] = {
                'labels': tokens[:10],
                'macro_category': macro_category,
                'macro_path': macro_path,
                'updated_at': datetime.utcnow().isoformat(),
                'confidence': confidence
            }
            scraped_now += 1

    remaining_missing = [cid for cid in unique_ids if cid not in category_map]
    logger.info('Category map updated', scraped_now=scraped_now, missing_after=len(remaining_missing), mode=mode)

    save_category_map(category_map)
    return category_map


def enrich_competitors(competitors: List[Dict[str, Any]], category_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    for item in competitors:
        cid = str(item.get('category_id') or '').strip()
        entry = category_map.get(cid, {})
        macro_category = entry.get('macro_category')
        macro_path = entry.get('macro_path')
        confidence = entry.get('confidence') or 'unknown'

        item['category_name'] = macro_category or ''
        item['category_path'] = macro_path or ''
        item['macro_category'] = macro_category or ''
        item['macro_path'] = macro_path or ''
        item['category_resolution_confidence'] = confidence

    return competitors


def export_csv(competitors: List[Dict[str, Any]], csv_path: str) -> None:
    import csv

    file_exists = os.path.exists(csv_path)
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    with open(csv_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                'product_id',
                'product_title',
                'sale_price',
                'discount',
                'evaluate_rate',
                'lastest_volume',
                'product_detail_url',
                'shop_id',
                'shop_url',
                'promotion_link',
                'category_id',
                'category_name',
                'category_path',
                'macro_category',
                'macro_path',
                'category_resolution_confidence',
                'first_level_category_id',
                'sell_score'
            ])

        for item in competitors:
            writer.writerow([
                item.get('product_id', ''),
                item.get('product_title', ''),
                item.get('sale_price', ''),
                item.get('discount', ''),
                item.get('evaluate_rate', ''),
                item.get('lastest_volume', ''),
                item.get('product_detail_url', ''),
                item.get('shop_id', ''),
                item.get('shop_url', ''),
                item.get('promotion_link', ''),
                item.get('category_id', ''),
                item.get('category_name', ''),
                item.get('category_path', ''),
                item.get('macro_category', ''),
                item.get('macro_path', ''),
                item.get('category_resolution_confidence', 'unknown'),
                item.get('first_level_category_id', ''),
                item.get('sell_score', '')
            ])
