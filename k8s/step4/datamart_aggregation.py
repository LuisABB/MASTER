# -*- coding: utf-8 -*-
"""
datamart_aggregation.py — Paso 4: Data Mart
═════════════════════════════════════════════
Lee analytics_db.gold_opportunity_ranking
→ Materializa analytics_db.gold_opportunity_ranking_by_category

Estructura del documento de salida por categoría:
  {
    category_name      : str,
    total_products     : int,
    avg_POS            : float,
    max_POS            : float,
    avg_success_proba  : float,
    avg_trend_quality  : float,
    avg_social_velocity: float,
    tier_distribution  : { HIGH: int, MEDIUM: int, LOW: int },
    cluster_distribution: { "Viral/Premium": int, ... },
    top_products       : [ { keyword, POS, tier, cluster, success_proba }, ... ],
    computed_at        : ISO datetime
  }
"""

import os
from pymongo import MongoClient, DESCENDING
from datetime import datetime, timezone

MONGO_URI   = os.getenv("MONGO_URI", "mongodb://mongodb:27017/")
DB_NAME     = "analytics_db"
SRC_COL     = "gold_opportunity_ranking"
DST_COL     = "gold_opportunity_ranking_by_category"

print("=" * 60)
print("[Job 4] Data Mart: agregación por categoría")
print("=" * 60)

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
client.admin.command("ping")
print(f"  ✓ Conectado a MongoDB")

db = client[DB_NAME]
computed_at = datetime.now(timezone.utc).isoformat()

# ── Pipeline de agregación ────────────────────────────────────────────────────
pipeline = [
    # ── 0. Filtrar productos sin categoría ────────────────────────────────────
    {"$match": {"category_name": {"$ne": None, "$exists": True, "$type": "string"}}},

    # ── 1. Agrupar por categoría ──────────────────────────────────────────────
    {"$group": {
        "_id": "$category_name",

        # Métricas numéricas
        "total_products":      {"$sum": 1},
        "avg_POS":             {"$avg": "$POS"},
        "max_POS":             {"$max": "$POS"},
        "avg_success_proba":   {"$avg": "$success_proba"},
        "avg_trend_quality":   {"$avg": "$trend_quality"},
        "avg_social_velocity": {"$avg": "$social_velocity"},
        "avg_xgb_prob_high":   {"$avg": "$xgb_prob_high"},

        # Distribución de tier (contadores condicionales)
        "tier_HIGH":   {"$sum": {"$cond": [{"$eq": ["$tier", "HIGH"]},   1, 0]}},
        "tier_MEDIUM": {"$sum": {"$cond": [{"$eq": ["$tier", "MEDIUM"]}, 1, 0]}},
        "tier_LOW":    {"$sum": {"$cond": [{"$eq": ["$tier", "LOW"]},    1, 0]}},

        # Distribución de clusters
        "cluster_viral":   {"$sum": {"$cond": [{"$eq": ["$cluster", "Viral/Premium"]}, 1, 0]}},
        "cluster_barato":  {"$sum": {"$cond": [{"$eq": ["$cluster", "Barato masivo"]}, 1, 0]}},
        "cluster_estable": {"$sum": {"$cond": [{"$eq": ["$cluster", "Estable"]},       1, 0]}},
        "cluster_muerto":  {"$sum": {"$cond": [{"$eq": ["$cluster", "Muerto"]},        1, 0]}},

        # Acumular todos los productos para luego extraer el top 3
        "all_products": {"$push": {
            "keyword":       "$keyword",
            "POS":           "$POS",
            "tier":          "$tier",
            "cluster":       "$cluster",
            "success_proba": "$success_proba",
            "xgb_prob_high": "$xgb_prob_high",
        }},
    }},

    # ── 2. Reshape del documento ──────────────────────────────────────────────
    {"$project": {
        "_id":           0,
        "category_name": "$_id",
        "total_products": 1,
        "avg_POS":            {"$round": ["$avg_POS",            4]},
        "max_POS":            {"$round": ["$max_POS",            4]},
        "avg_success_proba":  {"$round": ["$avg_success_proba",  4]},
        "avg_trend_quality":  {"$round": ["$avg_trend_quality",  4]},
        "avg_social_velocity":{"$round": ["$avg_social_velocity",4]},
        "avg_xgb_prob_high":  {"$round": ["$avg_xgb_prob_high",  4]},

        "tier_distribution": {
            "HIGH":   "$tier_HIGH",
            "MEDIUM": "$tier_MEDIUM",
            "LOW":    "$tier_LOW",
        },
        "cluster_distribution": {
            "Viral/Premium": "$cluster_viral",
            "Barato masivo": "$cluster_barato",
            "Estable":       "$cluster_estable",
            "Muerto":        "$cluster_muerto",
        },

        # Ordenar all_products por POS desc y tomar los 3 primeros
        "top_products": {
            "$slice": [
                {"$sortArray": {"input": "$all_products", "sortBy": {"POS": -1}}},
                3
            ]
        },
    }},

    # ── 3. Ordenar categorías por avg_POS desc ────────────────────────────────
    {"$sort": {"avg_POS": -1}},

    # ── 4. Añadir timestamp de cómputo ────────────────────────────────────────
    {"$addFields": {"computed_at": computed_at}},

    # ── 5. Materializar en colección destino ──────────────────────────────────
    {"$out": DST_COL},
]

print(f"\n▶ Ejecutando pipeline de agregación sobre {SRC_COL} ...")
db[SRC_COL].aggregate(pipeline)
print(f"  ✓ Colección '{DST_COL}' materializada")

# ── Índices para consultas rápidas ────────────────────────────────────────────
db[DST_COL].create_index([("avg_POS",        DESCENDING)])
db[DST_COL].create_index([("category_name",  1)], unique=True)
db[DST_COL].create_index([("tier_distribution.HIGH", DESCENDING)])
print(f"  ✓ Índices creados")

# ── Verificación ──────────────────────────────────────────────────────────────
total = db[DST_COL].count_documents({})
print(f"\n▶ Verificación: {total} categorías en {DST_COL}")
print()

for doc in db[DST_COL].find({}, {"_id": 0}).sort("avg_POS", DESCENDING):
    tier  = doc["tier_distribution"]
    print(f"  {doc['category_name']:<35} "
          f"avg_POS={doc['avg_POS']:.4f}  "
          f"products={doc['total_products']:>3}  "
          f"HIGH={tier['HIGH']} MED={tier['MEDIUM']} LOW={tier['LOW']}")
    for p in doc["top_products"]:
        print(f"      ↳ {p['keyword']:<28} POS={p['POS']:.4f}  {p['tier']}  {p['cluster']}")

client.close()

print("\n" + "=" * 60)
print("[Job 4] COMPLETADO")
print(f"  Base de datos : {DB_NAME}")
print(f"  Colección     : {DST_COL}")
print(f"  Categorías    : {total}")
print("=" * 60)
