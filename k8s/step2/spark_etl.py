"""
spark_etl.py — Paso 2: ETL PySpark
════════════════════════════════════
Lee CSV crudo desde LocalStack S3 (s3://raw-data/)
→ limpieza de nulos
→ agrega por category_name + country
→ guarda Parquet en s3://gold-data/category_performance/

S3 I/O vía boto3 (evita configurar hadoop-aws JARs).
PySpark corre en modo local[*] dentro del contenedor.
"""

import io
import sys
import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

# ── Configuración ──────────────────────────────────────────────────────────────
S3_ENDPOINT  = "http://localstack:4566"
S3_KEY       = "test"
S3_SECRET    = "test"
RAW_BUCKET   = "raw-data"
GOLD_BUCKET  = "gold-data"
RAW_KEY      = "dataset_validated.csv"
GOLD_PREFIX  = "category_performance"

KEY_COLS = ["keyword", "country", "category_name"]

FILL_ZERO = [
    "trends_slope", "trends_mean", "trends_max", "trends_min", "trends_std",
    "trends_first_value", "trends_last_value",
    "yt_total_views", "yt_total_likes", "yt_total_comments", "yt_videos_count",
    "ali_avg_sale_price", "ali_avg_evaluate_rate",
]

# ── Cliente boto3 → LocalStack ─────────────────────────────────────────────────
s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_KEY,
    aws_secret_access_key=S3_SECRET,
    region_name="us-east-1",
)

print("=" * 60)
print("[Job 2] PySpark ETL: raw CSV → gold Parquet")
print("=" * 60)

# ══════════════════════════════════════════════════════════════
# PASO A — Leer CSV desde S3 con boto3
# ══════════════════════════════════════════════════════════════
print(f"\n▶ Leyendo s3://{RAW_BUCKET}/{RAW_KEY} ...")
obj = s3.get_object(Bucket=RAW_BUCKET, Key=RAW_KEY)
df_pandas = pd.read_csv(io.BytesIO(obj["Body"].read()))

# Sanear nombres de columna (puntos → guiones bajos) para Spark
df_pandas.columns = [c.replace(".", "_") for c in df_pandas.columns]

print(f"  Filas leídas  : {len(df_pandas)}")
print(f"  Columnas      : {len(df_pandas.columns)}")

# ══════════════════════════════════════════════════════════════
# PASO B — Iniciar SparkSession (local)
# ══════════════════════════════════════════════════════════════
spark = (
    SparkSession.builder
    .appName("ETL-Gold-Layer")
    .master("local[*]")
    .config("spark.sql.shuffle.partitions", "4")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")

df = spark.createDataFrame(df_pandas)
print(f"\n▶ DataFrame Spark creado: {df.count()} filas × {len(df.columns)} cols")

# ══════════════════════════════════════════════════════════════
# PASO C — Limpieza de nulos
# ══════════════════════════════════════════════════════════════
print("\n▶ Limpieza de nulos...")
df_clean = df.dropna(subset=KEY_COLS)

fill_dict = {c: 0.0 for c in FILL_ZERO if c in df_clean.columns}
df_clean = df_clean.fillna(fill_dict)

dropped = df.count() - df_clean.count()
print(f"  Filas eliminadas (nulos en clave): {dropped}")
print(f"  Filas limpias                    : {df_clean.count()}")

# ══════════════════════════════════════════════════════════════
# PASO D — Agregación por category_name + country
# ══════════════════════════════════════════════════════════════
print("\n▶ Agregando por category_name + country...")

df_gold = df_clean.groupBy("category_name", "country").agg(
    F.count("keyword").alias("product_count"),
    F.avg("trends_mean").alias("avg_trend_score"),
    F.avg("trends_slope").alias("avg_trend_slope"),
    F.max("trends_mean").alias("max_trend_score"),
    F.avg("ali_avg_sale_price").alias("avg_price"),
    F.avg("ali_avg_evaluate_rate").alias("avg_rating"),
    F.sum("yt_total_views").alias("total_yt_views"),
    F.sum("yt_total_likes").alias("total_yt_likes"),
    F.avg("yt_videos_count").alias("avg_videos"),
).orderBy(F.desc("avg_trend_score"))

gold_count = df_gold.count()
print(f"  Grupos (filas gold): {gold_count}")
df_gold.show(20, truncate=False)

# ══════════════════════════════════════════════════════════════
# PASO E — Convertir a Pandas y subir Parquet a S3
# ══════════════════════════════════════════════════════════════
print("\n▶ Convirtiendo a Pandas y serializando Parquet...")
gold_pandas = df_gold.toPandas()
spark.stop()

buf = io.BytesIO()
gold_pandas.to_parquet(buf, index=False, engine="pyarrow", compression="snappy")
buf.seek(0)

parquet_key = f"{GOLD_PREFIX}/part-00000.snappy.parquet"
print(f"▶ Subiendo a s3://{GOLD_BUCKET}/{parquet_key} ...")
s3.put_object(Bucket=GOLD_BUCKET, Key=parquet_key, Body=buf.getvalue())

# Verificar
resp = s3.head_object(Bucket=GOLD_BUCKET, Key=parquet_key)
size_kb = resp["ContentLength"] / 1024
print(f"  ✓ Subido correctamente — {size_kb:.1f} KB")

# Listar gold bucket
print("\n▶ Contenido de s3://gold-data/:")
for obj in s3.list_objects_v2(Bucket=GOLD_BUCKET).get("Contents", []):
    print(f"  {obj['Key']}  ({obj['Size']} bytes)")

print("\n" + "=" * 60)
print("[Job 2] COMPLETADO")
print(f"  Parquet disponible en:")
print(f"  s3://{GOLD_BUCKET}/{parquet_key}")
print(f"  Filas gold: {gold_count}")
print("=" * 60)
