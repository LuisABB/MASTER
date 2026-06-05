# -*- coding: utf-8 -*-
"""
loader_s3_to_mongo.py — Paso 3: Serving Layer
═══════════════════════════════════════════════
Lee el Parquet gold desde LocalStack S3
→ inserta en MongoDB analytics_db

Colecciones creadas:
  · gold_opportunity_ranking  — todos los productos con POS, tier, cluster, scores
"""

import io
import os
import boto3
import pandas as pd
from pymongo import MongoClient, DESCENDING
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
S3_ENDPOINT  = os.getenv("S3_ENDPOINT",          "http://localstack:4566")
S3_KEY       = os.getenv("AWS_ACCESS_KEY_ID",     "test")
S3_SECRET    = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
MONGO_URI    = os.getenv("MONGO_URI",             "mongodb://mongodb:27017/")
GOLD_BUCKET  = "gold-data"
GOLD_KEY     = "dashboard_final/dashboard_final.snappy.parquet"
DB_NAME      = "analytics_db"
COLLECTION   = "gold_opportunity_ranking"

print("=" * 60)
print("[Job 3] Loader: S3 Parquet → MongoDB analytics_db")
print("=" * 60)

# ── 1. Leer Parquet desde S3 ──────────────────────────────────────────────────
print(f"\n▶ Leyendo s3://{GOLD_BUCKET}/{GOLD_KEY} ...")
s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_KEY,
    aws_secret_access_key=S3_SECRET,
    region_name="us-east-1",
)

obj = s3.get_object(Bucket=GOLD_BUCKET, Key=GOLD_KEY)
df  = pd.read_parquet(io.BytesIO(obj["Body"].read()), engine="pyarrow")

print(f"  Filas  : {len(df)}")
print(f"  Columnas: {list(df.columns)}")

# ── 2. Preparar documentos ────────────────────────────────────────────────────
# Convertir a tipos nativos Python (para que BSON los serialice bien)
df = df.where(pd.notnull(df), None)   # NaN → None
df["tier"]    = df["tier"].astype(str)
df["cluster"] = df["cluster"].astype(str)

# Añadir metadatos de carga
loaded_at = datetime.now(timezone.utc).isoformat()
docs = df.to_dict(orient="records")
for doc in docs:
    doc["_loaded_at"] = loaded_at
    # Convertir numpy types a Python nativos (pymongo los rechaza)
    for k, v in doc.items():
        if hasattr(v, "item"):          # numpy scalar
            doc[k] = v.item()

print(f"\n▶ {len(docs)} documentos preparados")

# ── 3. Insertar en MongoDB ────────────────────────────────────────────────────
print(f"\n▶ Conectando a MongoDB ({MONGO_URI}) ...")
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
client.admin.command("ping")
print("  ✓ Conexión establecida")

db  = client[DB_NAME]
col = db[COLLECTION]

# Reemplazar colección completa en cada carga (idempotente)
col.drop()
result = col.insert_many(docs)
print(f"  ✓ Insertados {len(result.inserted_ids)} documentos en {DB_NAME}.{COLLECTION}")

# ── 4. Crear índices para consultas rápidas ───────────────────────────────────
col.create_index([("POS", DESCENDING)])
col.create_index([("tier", 1)])
col.create_index([("cluster", 1)])
col.create_index([("category_name", 1)])
col.create_index([("country", 1)])
print("  ✓ Índices creados: POS, tier, cluster, category_name, country")

# ── 5. Verificación rápida ────────────────────────────────────────────────────
total = col.count_documents({})
print(f"\n▶ Verificación:")
print(f"  Total documentos: {total}")

print("\n  Top 5 productos por POS:")
for doc in col.find({}, {"keyword": 1, "category_name": 1, "POS": 1, "tier": 1, "cluster": 1, "_id": 0}).sort("POS", DESCENDING).limit(5):
    print(f"    {doc['keyword']:<30} POS={doc['POS']:.4f}  tier={doc['tier']}  cluster={doc['cluster']}")

print("\n  Distribución por tier:")
for t in col.distinct("tier"):
    n = col.count_documents({"tier": t})
    print(f"    {t}: {n}")

print("\n  Distribución por cluster:")
for c in col.distinct("cluster"):
    n = col.count_documents({"cluster": c})
    print(f"    {c}: {n}")

client.close()

print("\n" + "=" * 60)
print("[Job 3] COMPLETADO")
print(f"  Base de datos : {DB_NAME}")
print(f"  Colección     : {COLLECTION}")
print(f"  Documentos    : {total}")
print("=" * 60)
