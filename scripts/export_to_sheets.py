"""
Exporta gold_opportunity_ranking_by_category (MongoDB) → CSV

Prerequisitos:
  1. kubectl port-forward svc/mongodb 27017:27017 &
  2. pip install pymongo

Uso:
  python export_to_sheets.py
  → genera category_ranking.csv en la misma carpeta
"""

import csv
from pymongo import MongoClient
import os

# ── Configuración ──────────────────────────────────────────────────────────────
MONGO_URI   = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME     = "analytics_db"
COLLECTION  = "gold_opportunity_ranking_by_category"
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "category_ranking.csv")

# ── Leer MongoDB ───────────────────────────────────────────────────────────────
print(f"Conectando a MongoDB: {MONGO_URI}")
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[DB_NAME]
docs = list(db[COLLECTION].find({}, {"_id": 0}).sort("avg_POS", -1))

if not docs:
    print("ERROR: No se encontraron documentos en la colección.")
    exit(1)

print(f"  → {len(docs)} categorías leídas")

# ── Aplanar documentos (Google Sheets no soporta objetos anidados) ─────────────
rows = []
for doc in docs:
    tier  = doc.get("tier_distribution", {})
    cluster = doc.get("cluster_distribution", {})
    top   = doc.get("top_products", [])

    row = {
        "category_name":        doc.get("category_name", ""),
        "total_products":       doc.get("total_products", 0),
        "avg_POS":              round(doc.get("avg_POS", 0), 4),
        "max_POS":              round(doc.get("max_POS", 0), 4),
        "avg_success_proba":    round(doc.get("avg_success_proba", 0), 4),
        "avg_trend_quality":    round(doc.get("avg_trend_quality", 0), 4),
        "avg_social_velocity":  round(doc.get("avg_social_velocity", 0), 4),
        "avg_xgb_prob_high":    round(doc.get("avg_xgb_prob_high", 0), 4),
        "tier_HIGH":            tier.get("HIGH", 0),
        "tier_MEDIUM":          tier.get("MEDIUM", 0),
        "tier_LOW":             tier.get("LOW", 0),
        "cluster_viral":        cluster.get("Viral/Premium", 0),
        "cluster_barato":       cluster.get("Barato masivo", 0),
        "cluster_estable":      cluster.get("Estable", 0),
        "cluster_muerto":       cluster.get("Muerto", 0),
        "top_product_1":        top[0]["keyword"] if len(top) > 0 else "",
        "top_product_1_POS":    round(top[0].get("POS", 0), 4) if len(top) > 0 else "",
        "top_product_2":        top[1]["keyword"] if len(top) > 1 else "",
        "top_product_2_POS":    round(top[1].get("POS", 0), 4) if len(top) > 1 else "",
        "top_product_3":        top[2]["keyword"] if len(top) > 2 else "",
        "top_product_3_POS":    round(top[2].get("POS", 0), 4) if len(top) > 2 else "",
        "computed_at":          str(doc.get("computed_at", "")),
    }
    rows.append(row)

headers = list(rows[0].keys())

# ── Escribir CSV ───────────────────────────────────────────────────────────────
print(f"Escribiendo CSV: {OUTPUT_FILE}")
with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)

print(f"\n✓ Exportación completada: {os.path.abspath(OUTPUT_FILE)}")
print(f"  {len(rows)} categorías exportadas, {len(headers)} columnas")
print(f"\nSigue estos pasos para conectar a Looker Studio:")
print(f"  1. Sube {OUTPUT_FILE} a Google Sheets (File → Import)")
print(f"  2. En Looker Studio → Add data → Google Sheets → selecciona la hoja")
