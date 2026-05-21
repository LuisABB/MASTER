# -*- coding: utf-8 -*-
"""
pipeline_s3.py
──────────────
Versión cloud del pipeline V2_FINAL para ejecutar dentro de Kubernetes.

Cambios respecto al pipeline.py original:
  - Entrada : lee dataset_validated.csv desde s3://raw-data/ (LocalStack)
  - Salida  : guarda dashboard_final como Parquet en s3://gold-data/

Toda la lógica ML (LR → RF → XGBoost → K-Means → Prophet → POS) es idéntica.
"""

import io
import os
import warnings
import boto3
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, MinMaxScaler, LabelEncoder
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.cluster import KMeans

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG S3 (LocalStack)
# ─────────────────────────────────────────────────────────────────────────────
S3_ENDPOINT  = os.getenv("S3_ENDPOINT",  "http://localstack:4566")
S3_KEY       = os.getenv("AWS_ACCESS_KEY_ID",     "test")
S3_SECRET    = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
RAW_BUCKET   = "raw-data"
GOLD_BUCKET  = "gold-data"
RAW_KEY      = "dataset_validated.csv"
GOLD_KEY     = "dashboard_final/dashboard_final.snappy.parquet"

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_KEY,
    aws_secret_access_key=S3_SECRET,
    region_name="us-east-1",
)

# ═════════════════════════════════════════════════════════════════════════════
# PASO 1 — ETL & Feature Engineering
# ═════════════════════════════════════════════════════════════════════════════
print("=" * 65)
print("PASO 1 — ETL & Feature Engineering")
print("=" * 65)

# ── Leer CSV desde S3 ────────────────────────────────────────────────────────
print(f"  Leyendo s3://{RAW_BUCKET}/{RAW_KEY} ...")
obj = s3.get_object(Bucket=RAW_BUCKET, Key=RAW_KEY)
df = pd.read_csv(io.BytesIO(obj["Body"].read()))

df["generated_at"]     = pd.to_datetime(df["generated_at"],     errors="coerce")
df["trends_first_date"] = pd.to_datetime(df["trends_first_date"], errors="coerce")
df["trends_last_date"]  = pd.to_datetime(df["trends_last_date"],  errors="coerce")

# ── Forzar tipos numéricos ────────────────────────────────────────────────────
numeric_cols = [
    "ali_avg_sale_price", "ali_avg_evaluate_rate",
    "trends_count", "trends_mean", "trends_max", "trends_min", "trends_std",
    "trends_first_value", "trends_last_value", "trends_slope",
    "yt_total_views", "yt_total_likes", "yt_total_comments", "yt_videos_count",
]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# ── Features derivadas ────────────────────────────────────────────────────────
likes    = df["yt_total_likes"].fillna(0)
comments = df["yt_total_comments"].fillna(0)
views    = df["yt_total_views"].fillna(0)
videos   = df["yt_videos_count"].fillna(0)

df["yt_engagement"]   = (likes + comments) / views.replace(0, np.nan)
df["yt_engagement"]   = df["yt_engagement"].fillna(0)

df["trends_rel_change"] = np.where(
    df["trends_first_value"] == 0, 0.0,
    (df["trends_last_value"] - df["trends_first_value"]) / df["trends_first_value"],
)

cat_avg = df.groupby("category_name")["ali_avg_sale_price"].transform("mean")
df["ali_price_norm_by_cat"] = (df["ali_avg_sale_price"] / cat_avg.replace(0, np.nan)).fillna(1.0)

df["stability_score"]   = df["trends_mean"] / (df["trends_std"].fillna(0) + 1)
df["trend_quality"]     = df["trends_slope"].fillna(0) * df["stability_score"].fillna(0)
df["consistency_score"] = np.exp(-df["trends_std"].fillna(0).clip(upper=20))
df["trend_growth"]      = df["trends_last_value"].fillna(0) - df["trends_first_value"].fillna(0)
df["momentum_strength"] = df["trends_slope"].fillna(0) * df["trends_count"].fillna(0)
df["volatility"]        = df["trends_std"].fillna(0) / (df["trends_mean"].fillna(0) + 1)

df["social_velocity"] = (likes + comments) / (videos + 1)
df["views_per_video"] = views / (videos + 1)
df["comment_rate"]    = comments / (views + 1)

print(f"  Cargadas {len(df)} filas · {len(df.columns)} columnas tras feature engineering")
print(f"  Categorías: {df['category_name'].nunique()}  |  Países: {df['country'].nunique()}")

# ═════════════════════════════════════════════════════════════════════════════
# PASO 2 — Logistic Regression → success_proba
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("PASO 2 — Logistic Regression  (probabilidad de éxito)")
print("=" * 65)

cutoff_lr = np.percentile(df["trends_slope"].dropna(), 75)
df["success"] = (df["trends_slope"] >= cutoff_lr).astype(int)
print(f"  Umbral trends_slope: {cutoff_lr:.4f}  |  éxitos: {df['success'].sum()}")

lr_num_features = [
    "ali_avg_sale_price", "ali_avg_evaluate_rate",
    "trends_count", "trends_mean", "trends_max", "trends_min", "trends_std",
    "trends_first_value", "trends_last_value", "trends_slope", "trends_rel_change",
    "yt_total_views", "yt_total_likes", "yt_total_comments", "yt_videos_count",
    "yt_engagement", "ali_price_norm_by_cat",
]
cat_dummies = pd.get_dummies(df["category_name"].fillna("NA"), prefix="cat", drop_first=True)
X_lr = pd.concat([df[lr_num_features], cat_dummies], axis=1).astype(float)
y_lr = df["success"]

imputer_lr = SimpleImputer(strategy="mean")
X_lr_imp = imputer_lr.fit_transform(X_lr)
scaler_lr = StandardScaler()
X_lr_sc  = scaler_lr.fit_transform(X_lr_imp)

X_tr, X_te, y_tr, y_te = train_test_split(X_lr_sc, y_lr, test_size=0.2, random_state=42, stratify=y_lr)
lr_model = LogisticRegression(C=1.0, penalty="l2", solver="liblinear", max_iter=1000, random_state=42)
lr_model.fit(X_tr, y_tr)
print(f"  Accuracy en test: {lr_model.score(X_te, y_te):.4f}")

df["success_proba"] = lr_model.predict_proba(X_lr_sc)[:, 1]

# ═════════════════════════════════════════════════════════════════════════════
# PASO 3 — Random Forest → rf_prob
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("PASO 3 — Random Forest  (future_growth)")
print("=" * 65)

df["future_growth"] = df["trends_last_value"].fillna(0) - df["trends_first_value"].fillna(0)
thr_rf = df["future_growth"].quantile(0.75)
df["success_rf"] = (df["future_growth"] >= thr_rf).astype(int)

rf_features = [
    "trends_mean", "trends_std", "trends_slope",
    "yt_total_views", "yt_total_likes", "yt_total_comments", "yt_videos_count",
    "ali_avg_sale_price", "ali_avg_evaluate_rate",
    "yt_engagement", "views_per_video", "comment_rate",
]
rf_avail = [f for f in rf_features if f in df.columns]

df_sorted = df.sort_values("generated_at").reset_index(drop=True)
X_rf_s = df_sorted[rf_avail].fillna(0)
y_rf_s = df_sorted["success_rf"]

tscv = TimeSeriesSplit(n_splits=3)
last_rf_model = None
for fold, (tr_idx, te_idx) in enumerate(tscv.split(X_rf_s)):
    rf_model = RandomForestClassifier(n_estimators=200, max_depth=10, class_weight="balanced", random_state=42)
    rf_model.fit(X_rf_s.iloc[tr_idx], y_rf_s.iloc[tr_idx])
    last_rf_model = rf_model
    try:
        from sklearn.metrics import roc_auc_score
        auc = roc_auc_score(y_rf_s.iloc[te_idx], rf_model.predict_proba(X_rf_s.iloc[te_idx])[:, 1])
        print(f"  Fold {fold+1} ROC-AUC: {auc:.4f}")
    except Exception:
        print(f"  Fold {fold+1} ROC-AUC: N/A")

rf_probs = last_rf_model.predict_proba(X_rf_s)[:, 1]
df_sorted["rf_prob"] = rf_probs
df["rf_prob"] = df_sorted["rf_prob"].values

# ═════════════════════════════════════════════════════════════════════════════
# PASO 4 — XGBoost → xgb_prob_high
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("PASO 4 — XGBoost  (HIGH/MEDIUM/LOW)")
print("=" * 65)

try:
    from xgboost import XGBClassifier

    tq = df["trend_quality"].fillna(0)
    df["xgb_target"] = np.where(tq > np.percentile(tq, 90), "HIGH",
                        np.where(tq > np.percentile(tq, 70), "MEDIUM", "LOW"))
    print(f"  Distribución:\n{df['xgb_target'].value_counts().to_string()}")

    xgb_features = [
        "trends_slope", "trends_mean", "trends_std", "trends_count",
        "stability_score", "trend_quality", "consistency_score", "social_velocity",
        "momentum_strength", "trend_growth", "volatility",
        "yt_total_views", "yt_total_likes", "yt_total_comments", "yt_videos_count",
        "yt_engagement", "ali_avg_sale_price", "ali_avg_evaluate_rate",
    ]
    xgb_avail = [f for f in xgb_features if f in df.columns]
    X_xgb = df[xgb_avail].fillna(0)

    le_xgb = LabelEncoder()
    y_xgb  = le_xgb.fit_transform(df["xgb_target"].astype(str))

    xgb_params = dict(objective="multi:softprob", num_class=len(le_xgb.classes_),
                      max_depth=3, learning_rate=0.05, n_estimators=200,
                      subsample=0.8, colsample_bytree=0.8,
                      reg_alpha=1, reg_lambda=2, min_child_weight=3,
                      random_state=42, eval_metric="mlogloss")
    try:
        xgb_clf = XGBClassifier(**xgb_params, use_label_encoder=False)
    except TypeError:
        xgb_clf = XGBClassifier(**xgb_params)

    X_tr_x, X_te_x, y_tr_x, y_te_x = train_test_split(X_xgb.values, y_xgb, test_size=0.2, random_state=42, stratify=y_xgb)
    xgb_clf.fit(X_tr_x, y_tr_x, eval_set=[(X_te_x, y_te_x)], verbose=False)

    probs_xgb   = xgb_clf.predict_proba(X_xgb.values)
    classes_xgb = list(le_xgb.classes_)
    high_idx    = classes_xgb.index("HIGH") if "HIGH" in classes_xgb else 0
    df["xgb_prob_high"] = probs_xgb[:, high_idx]
    print(f"  xgb_prob_high → [{df['xgb_prob_high'].min():.3f}, {df['xgb_prob_high'].max():.3f}]")

except ImportError:
    print("  xgboost no disponible — usando fallback MinMaxScaler")
    df["xgb_prob_high"] = MinMaxScaler().fit_transform(df[["trend_quality"]].fillna(0)).ravel()

# ═════════════════════════════════════════════════════════════════════════════
# PASO 5 — K-Means Clustering (k=4)
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("PASO 5 — K-Means Clustering  (Viral / Barato masivo / Estable / Muerto)")
print("=" * 65)

km_features = ["yt_total_views", "trends_slope", "ali_avg_evaluate_rate", "ali_avg_sale_price", "yt_engagement"]
km_avail    = [f for f in km_features if f in df.columns]
X_km_imp    = SimpleImputer(strategy="median").fit_transform(df[km_avail].copy())

for c in ["yt_total_views", "ali_avg_sale_price"]:
    if c in km_avail:
        X_km_imp[:, km_avail.index(c)] = np.log1p(X_km_imp[:, km_avail.index(c)])

X_km_sc = StandardScaler().fit_transform(X_km_imp)
df["cluster_id"] = KMeans(n_clusters=4, random_state=42, n_init=50).fit_predict(X_km_sc)

km_df  = pd.DataFrame(X_km_imp, columns=km_avail)
km_df["cluster_id"] = df["cluster_id"].values
means  = km_df.groupby("cluster_id")[km_avail].mean()
scores = {
    cid: means.loc[cid].get("yt_total_views", 0) * 1.0
       + means.loc[cid].get("trends_slope", 0) * 5.0
       + means.loc[cid].get("yt_engagement", 0) * 3.0
       - means.loc[cid].get("ali_avg_sale_price", 0) * 0.3
    for cid in range(4)
}
sorted_cids = sorted(scores, key=scores.get, reverse=True)
label_map   = {sorted_cids[0]: "Viral/Premium", sorted_cids[1]: "Barato masivo",
               sorted_cids[2]: "Estable",        sorted_cids[3]: "Muerto"}
df["cluster"] = df["cluster_id"].map(label_map)
print(f"  Distribución clusters:\n{df['cluster'].value_counts().to_string()}")

# ═════════════════════════════════════════════════════════════════════════════
# PASO 6 — Prophet Forecast → forecast_mean
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("PASO 6 — Prophet Forecast  (proyección 90 días)")
print("=" * 65)

# Proyección lineal por producto (siempre disponible)
df["forecast_mean"] = (df["trends_mean"].fillna(0) + df["trends_slope"].fillna(0) * 90).clip(0, 100)
print(f"  Proyección lineal: [{df['forecast_mean'].min():.2f}, {df['forecast_mean'].max():.2f}]")

try:
    from prophet import Prophet
    df_ts = (df.dropna(subset=["generated_at"])
               .assign(ds=lambda x: x["generated_at"].dt.normalize())
               .groupby("ds")["trends_mean"].mean()
               .reset_index().rename(columns={"trends_mean": "y"})
               .sort_values("ds"))
    if len(df_ts) >= 5:
        df_ts["cap"] = 100.0; df_ts["floor"] = 0.0
        m = Prophet(growth="logistic", yearly_seasonality=False, weekly_seasonality=True,
                    daily_seasonality=False, changepoint_prior_scale=0.05)
        m.fit(df_ts)
        future = m.make_future_dataframe(periods=90)
        future["cap"] = 100.0; future["floor"] = 0.0
        fc = m.predict(future)
        df["forecast_mean_prophet"] = float(np.clip(fc["yhat"].iloc[-1], 0, 100))
        print(f"  Prophet global a 90d: {df['forecast_mean_prophet'].iloc[0]:.2f}")
except ImportError:
    print("  prophet no instalado — usando solo proyección lineal")
except Exception as e:
    print(f"  Prophet omitido: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# PASO 7 — Product Opportunity Score (POS)
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("PASO 7 — Product Opportunity Score (POS)")
print("=" * 65)
print("  Fórmula: POS = 0.40·success_proba + 0.30·trend_quality + 0.15·consistency_score + 0.15·social_velocity")

def norm01(s: pd.Series) -> np.ndarray:
    return MinMaxScaler().fit_transform(s.fillna(0).values.reshape(-1, 1)).ravel()

df["POS"] = (0.40 * norm01(df["success_proba"])
           + 0.30 * norm01(df["trend_quality"])
           + 0.15 * norm01(df["consistency_score"])
           + 0.15 * norm01(df["social_velocity"]))

df["tier"] = pd.qcut(df["POS"], q=[0.0, 0.70, 0.90, 1.0], labels=["LOW", "MEDIUM", "HIGH"])
print(f"  POS → [{df['POS'].min():.4f}, {df['POS'].max():.4f}]")
print(f"  Tiers:\n{df['tier'].value_counts().sort_index().to_string()}")

# ═════════════════════════════════════════════════════════════════════════════
# PASO 8 — Guardar dashboard_final como Parquet en s3://gold-data/
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("PASO 8 — Exportar dashboard_final → s3://gold-data/")
print("=" * 65)

FINAL_COLS = [
    "keyword", "category_name", "country",
    "trends_mean", "trends_slope",
    "yt_total_views", "yt_engagement",
    "ali_avg_sale_price",
    "cluster", "success_proba", "rf_prob", "xgb_prob_high",
    "forecast_mean", "trend_quality", "consistency_score", "social_velocity",
    "POS", "tier",
]
available_final = [c for c in FINAL_COLS if c in df.columns]
df_out = df[available_final].copy()

round_cols = ["trends_mean", "trends_slope", "yt_total_views", "yt_engagement",
              "ali_avg_sale_price", "success_proba", "rf_prob", "xgb_prob_high",
              "forecast_mean", "trend_quality", "consistency_score", "social_velocity", "POS"]
for rc in round_cols:
    if rc in df_out.columns:
        df_out[rc] = df_out[rc].round(6)

# Serializar como Parquet y subir a S3
buf = io.BytesIO()
df_out.to_parquet(buf, index=False, engine="pyarrow", compression="snappy")
buf.seek(0)

s3.put_object(Bucket=GOLD_BUCKET, Key=GOLD_KEY, Body=buf.getvalue())
resp = s3.head_object(Bucket=GOLD_BUCKET, Key=GOLD_KEY)

print(f"  ✅  {len(df_out)} filas × {len(available_final)} columnas")
print(f"  ✅  Subido: s3://{GOLD_BUCKET}/{GOLD_KEY}")
print(f"  ✅  Tamaño: {resp['ContentLength'] / 1024:.1f} KB")
print("\n" + "=" * 65)
print("  PIPELINE COMPLETO")
print("=" * 65)
for col in available_final:
    print(f"    · {col}")
