# =====================
# IMPORTS
# =====================
import json
import pandas as pd
from pymongo import MongoClient

# =====================
# LOGGING UTILS
# =====================
import traceback

def log(msg):
    """Imprime un mensaje de log formateado."""
    print(f"[LOG] {msg}")

def log_error(e):
    """Imprime un mensaje de error y el traceback."""
    print(f"[ERROR] {e}")
    traceback.print_exc()

# =====================
# INSERCIÓN POR COLECCIÓN
# =====================
def insert_fusion_requests(json_data, db):
    """Inserta el documento principal en fusion_requests."""
    ali_query = dict(json_data["aliexpress_query"])
    ali_query.pop("page", None)
    ali_query.pop("page_size", None)
    fusion_doc = {
        "request_id": json_data["request_id"],
        "generated_at": pd.to_datetime(json_data["generated_at"]),
        "keyword": json_data["keyword"],
        "country": json_data["country"],
        "region": json_data["region"],
        "language": json_data["lang"],
        "aliexpress_query": ali_query,
        "fusion": json_data["fusion"],
        "sources_used": ["google_trends", "youtube", "aliexpress"]
    }
    res = db["fusion_requests"].insert_one(fusion_doc)
    log(f"fusion_requests insertado con _id: {res.inserted_id}")

def insert_aliexpress_competitors(json_data, db):
    """Inserta los competidores de AliExpress en la colección correspondiente."""
    for idx, c in enumerate(json_data["aliexpress"]["competitors"]):
        comp_doc = {
            "request_id": json_data["request_id"],
            "generated_at": pd.to_datetime(json_data["generated_at"]),
            "product_id": c["product_id"],
            "title": c["product_title"],
            "pricing": {
                "sale_price": float(c["sale_price"]),
                "discount_pct": int(str(c["discount"]).replace("%", ""))
            },
            "metrics": {
                "evaluate_rate": float(str(c["evaluate_rate"]).replace("%", "") or 0),
                "sell_score": c["sell_score"],
                "latest_volume": c["lastest_volume"]
            },
            "category": {
                "id": c["category_id"],
                "name": c["category_name"],
                "first_level_id": c["first_level_category_id"]
            },
            "shop": {
                "id": c["shop_id"],
                "url": c["shop_url"]
            }
        }
        res = db["aliexpress_competitors"].insert_one(comp_doc)
        log(f"aliexpress_competitors #{idx+1} insertado con _id: {res.inserted_id}")

def insert_aliexpress_request_meta(json_data, db):
    """Inserta el meta de la petición de AliExpress."""
    meta_doc = {
        "request_id": json_data["request_id"],
        "competitors_count": json_data["aliexpress"]["competitors_count"]
    }
    res = db["aliexpress_request_meta"].insert_one(meta_doc)
    log(f"aliexpress_request_meta insertado con _id: {res.inserted_id}")

def insert_trends_series(json_data, db):
    """Inserta la serie temporal de tendencias."""
    for idx, s in enumerate(json_data["series"]):
        series_doc = {
            "request_id": json_data["request_id"],
            "date": pd.to_datetime(s["date"]),
            "value": s["value"]
        }
        res = db["trends_series"].insert_one(series_doc)
        log(f"trends_series #{idx+1} insertado con _id: {res.inserted_id}")

def insert_trends_summary(json_data, db):
    """Inserta el resumen de tendencias."""
    trends = json_data["google_trends"]
    summary_doc = {
        "request_id": json_data["request_id"],
        "series_count": trends["series_count"],
        "trend_score": trends["trend_score"],
        "signals": trends["signals"],
        "sources_used": trends["sources_used"]
    }
    res = db["trends_summary"].insert_one(summary_doc)
    log(f"trends_summary insertado con _id: {res.inserted_id}")

def insert_youtube_videos(json_data, db):
    """Inserta los videos de YouTube analizados."""
    yt = json_data["youtube"]
    for idx, v in enumerate(yt["videos"]):
        video_doc = {
            "request_id": json_data["request_id"],
            "query_used": yt["query_used"],
            "video_id": v["video_id"],
            "title": v["title"],
            "channel_title": v["channel_title"],
            "published_at": pd.to_datetime(v["published_at"]),
            "views": v["views"],
            "likes": v["likes"],
            "comments": v["comments"],
            "engagement_rate": v["engagement_rate"],
            "freshness": v["freshness"],
            "video_intent": v["video_intent"]
        }
        res = db["youtube_videos"].insert_one(video_doc)
        log(f"youtube_videos #{idx+1} insertado con _id: {res.inserted_id}")

def insert_youtube_summary(json_data, db):
    """Inserta el resumen de YouTube."""
    yt = json_data["youtube"]
    yt_summary_doc = {
        "request_id": json_data["request_id"],
        "query_used": yt["query_used"],
        "videos_analyzed": yt["videos_analyzed"],
        "total_views": yt["total_views"],
        "intent_score": yt["intent_score"]
    }
    res = db["youtube_summary"].insert_one(yt_summary_doc)
    log(f"youtube_summary insertado con _id: {res.inserted_id}")

def insertar_fusion_json_en_mongodb(json_data, db):
    """Orquesta la inserción de todos los datos en las colecciones avanzadas."""
    try:
        log("Iniciando inserción en fusion_requests...")
        insert_fusion_requests(json_data, db)
        log("Iniciando inserción en aliexpress_competitors...")
        insert_aliexpress_competitors(json_data, db)
        log("Iniciando inserción en aliexpress_request_meta...")
        insert_aliexpress_request_meta(json_data, db)
        log("Iniciando inserción en trends_series...")
        insert_trends_series(json_data, db)
        log("Iniciando inserción en trends_summary...")
        insert_trends_summary(json_data, db)
        log("Iniciando inserción en youtube_videos...")
        insert_youtube_videos(json_data, db)
        log("Iniciando inserción en youtube_summary...")
        insert_youtube_summary(json_data, db)
        log("Inserción completa en todas las colecciones.")
        log(f"Request ID insertado: {json_data['request_id']}")
    except Exception as e:
        log_error(e)

# ==========================================
# USO EJEMPLO: LLAMAR DESDE FLASK
# ==========================================
#
# from pymongo import MongoClient
# client = MongoClient(MI_URI)
# db = client[MI_BD]
# insertar_fusion_json_en_mongodb(response, db)
# client.close()

