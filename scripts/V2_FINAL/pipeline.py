# -*- coding: utf-8 -*-
"""
pipeline.py
───────────
Pipeline completo: ETL → Logistic Regression → Random Forest → XGBoost
                  → K-Means → Prophet → Product Opportunity Score (POS)
                  → dashboard_final.csv

Entrada : dataset_validated.csv  (cualquiera de las carpetas del proyecto)
Salida  : dashboard_final.csv    (misma carpeta que este script)
"""

import os
import warnings
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, MinMaxScaler, LabelEncoder
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, BaggingClassifier
from sklearn.utils import resample
from sklearn.cluster import KMeans

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Usar el mismo CSV que está en logisticregression/ (todos son idénticos)
DATA_PATH = os.path.join(BASE_DIR, "logisticregression", "dataset_validated.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "dashboard_final.csv")

# ═════════════════════════════════════════════════════════════════════════════
# PASO 1 — ETL & Feature Engineering
# ═════════════════════════════════════════════════════════════════════════════
print("=" * 65)
print("PASO 1 — ETL & Feature Engineering")
print("=" * 65)

df = pd.read_csv(DATA_PATH)
df["generated_at"] = pd.to_datetime(df["generated_at"], errors="coerce")
df["trends_first_date"] = pd.to_datetime(df["trends_first_date"], errors="coerce")
df["trends_last_date"] = pd.to_datetime(df["trends_last_date"], errors="coerce")

# ── Forzar tipos numéricos en columnas clave ──────────────────────────────────
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
# YouTube engagement = (likes + comments) / views
likes    = df["yt_total_likes"].fillna(0)
comments = df["yt_total_comments"].fillna(0)
views    = df["yt_total_views"].fillna(0)
videos   = df["yt_videos_count"].fillna(0)

df["yt_engagement"]   = (likes + comments) / views.replace(0, np.nan)
df["yt_engagement"]   = df["yt_engagement"].fillna(0)

# Google Trends: cambio relativo first→last
df["trends_rel_change"] = np.where(
    df["trends_first_value"] == 0,
    0.0,
    (df["trends_last_value"] - df["trends_first_value"]) / df["trends_first_value"],
)

# AliExpress: precio normalizado por categoría
cat_avg = df.groupby("category_name")["ali_avg_sale_price"].transform("mean")
df["ali_price_norm_by_cat"] = (df["ali_avg_sale_price"] / cat_avg.replace(0, np.nan)).fillna(1.0)

# Métricas de tendencia
df["stability_score"]   = df["trends_mean"] / (df["trends_std"].fillna(0) + 1)
df["trend_quality"]     = df["trends_slope"].fillna(0) * df["stability_score"].fillna(0)
df["consistency_score"] = np.exp(-df["trends_std"].fillna(0).clip(upper=20))
df["trend_growth"]      = df["trends_last_value"].fillna(0) - df["trends_first_value"].fillna(0)
df["momentum_strength"] = df["trends_slope"].fillna(0) * df["trends_count"].fillna(0)
df["volatility"]        = df["trends_std"].fillna(0) / (df["trends_mean"].fillna(0) + 1)

# Métricas de YouTube adicionales
df["social_velocity"] = (likes + comments) / (videos + 1)
df["views_per_video"] = views / (videos + 1)
df["comment_rate"]    = comments / (views + 1)

print(f"  Cargadas {len(df)} filas · {len(df.columns)} columnas tras feature engineering")
print(f"  Categorías: {df['category_name'].nunique()}  |  Países: {df['country'].nunique()}")

# ═════════════════════════════════════════════════════════════════════════════
# PASO 2 — Logistic Regression → success_proba
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("PASO 2 — Logistic Regression  (baseline + probabilidad de éxito)")
print("=" * 65)

# Target: top 25% de trends_slope = éxito
cutoff_lr = np.percentile(df["trends_slope"].dropna(), 75)
df["success"] = (df["trends_slope"] >= cutoff_lr).astype(int)
print(f"  Umbral trends_slope para éxito: {cutoff_lr:.4f}")
print(f"  Clase 1 (éxito): {df['success'].sum()}  |  Clase 0: {(df['success']==0).sum()}")

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
X_lr_sc = scaler_lr.fit_transform(X_lr_imp)

X_tr, X_te, y_tr, y_te = train_test_split(
    X_lr_sc, y_lr, test_size=0.2, random_state=42, stratify=y_lr
)
lr_model = LogisticRegression(
    C=1.0, penalty="l2", solver="liblinear", max_iter=1000, random_state=42
)
lr_model.fit(X_tr, y_tr)
print(f"  Accuracy en test: {lr_model.score(X_te, y_te):.4f}")

# Probabilidades para todos los productos
df["success_proba"] = lr_model.predict_proba(X_lr_sc)[:, 1]
print(f"  success_proba → [{df['success_proba'].min():.3f}, {df['success_proba'].max():.3f}]")

# ═════════════════════════════════════════════════════════════════════════════
# PASO 3 — Random Forest → rf_prob
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("PASO 3 — Random Forest  (forecasting temporal / future_growth)")
print("=" * 65)

# Target: top 25% de crecimiento futuro (last - first)
df["future_growth"] = df["trends_last_value"].fillna(0) - df["trends_first_value"].fillna(0)
thr_rf = df["future_growth"].quantile(0.75)
df["success_rf"] = (df["future_growth"] >= thr_rf).astype(int)
print(f"  Umbral future_growth: {thr_rf:.4f}")

rf_features = [
    "trends_mean", "trends_std", "trends_slope",
    "yt_total_views", "yt_total_likes", "yt_total_comments", "yt_videos_count",
    "ali_avg_sale_price", "ali_avg_evaluate_rate",
    "yt_engagement", "views_per_video", "comment_rate",
]
rf_avail = [f for f in rf_features if f in df.columns]

# Ordenar temporalmente para TimeSeriesSplit
df_sorted = df.sort_values("generated_at").reset_index(drop=True)
X_rf_s = df_sorted[rf_avail].fillna(0)
y_rf_s = df_sorted["success_rf"]

# ── TimeSeriesSplit con Bootstrap ──────────────────────────────────────────
tscv = TimeSeriesSplit(n_splits=3)
last_rf_model = None
bootstrap_scores_rf = []

for fold, (tr_idx, te_idx) in enumerate(tscv.split(X_rf_s)):
    X_tr_fold = X_rf_s.iloc[tr_idx]
    y_tr_fold = y_rf_s.iloc[tr_idx]
    X_te_fold = X_rf_s.iloc[te_idx]
    y_te_fold = y_rf_s.iloc[te_idx]
    
    # Modelo base con bootstrap=True (ya es default en RandomForestClassifier)
    rf_model = RandomForestClassifier(
        n_estimators=200, max_depth=10, class_weight="balanced", 
        bootstrap=True, random_state=42
    )
    rf_model.fit(X_tr_fold, y_tr_fold)
    last_rf_model = rf_model
    
    fold_auc = "N/A"
    try:
        from sklearn.metrics import roc_auc_score
        proba_te = rf_model.predict_proba(X_te_fold)[:, 1]
        fold_auc_val = roc_auc_score(y_te_fold, proba_te)
        fold_auc = f"{fold_auc_val:.4f}"
        bootstrap_scores_rf.append(fold_auc_val)
    except Exception:
        pass
    print(f"  Fold {fold+1} ROC-AUC (CV): {fold_auc}")
    
    # ── Evaluación Bootstrap ────────────────────────────────────────────────
    n_bootstrap = 30
    bootstrap_auc_scores = []
    for b in range(n_bootstrap):
        X_boot, y_boot = resample(X_tr_fold, y_tr_fold, random_state=42+b)
        rf_boot = RandomForestClassifier(
            n_estimators=100, max_depth=10, class_weight="balanced",
            bootstrap=True, random_state=42+b
        )
        rf_boot.fit(X_boot, y_boot)
        proba_boot = rf_boot.predict_proba(X_te_fold)[:, 1]
        try:
            auc_boot = roc_auc_score(y_te_fold, proba_boot)
            bootstrap_auc_scores.append(auc_boot)
        except Exception:
            pass
    
    if bootstrap_auc_scores:
        mean_boot = np.mean(bootstrap_auc_scores)
        std_boot = np.std(bootstrap_auc_scores)
        print(f"           Bootstrap ({n_bootstrap}): {mean_boot:.4f} ± {std_boot:.4f}")

if bootstrap_scores_rf:
    print(f"  CV Mean ROC-AUC: {np.mean(bootstrap_scores_rf):.4f} ± {np.std(bootstrap_scores_rf):.4f}")

# Predecir en todo el dataset (mismo orden que df_sorted)
rf_probs_sorted = last_rf_model.predict_proba(X_rf_s)[:, 1]
# Re-asignar al df original según el índice guardado en df_sorted
df_sorted["rf_prob"] = rf_probs_sorted
df["rf_prob"] = df_sorted.set_index(df_sorted.index)["rf_prob"].values
print(f"  rf_prob → [{df['rf_prob'].min():.3f}, {df['rf_prob'].max():.3f}]")

# ═════════════════════════════════════════════════════════════════════════════
# PASO 4 — XGBoost → xgb_prob_high  +  SHAP
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("PASO 4 — XGBoost  (Trend Score + clasificación HIGH/MEDIUM/LOW)")
print("=" * 65)

try:
    from xgboost import XGBClassifier

    # Target multiclase basado en percentiles de trend_quality
    tq = df["trend_quality"].fillna(0)
    high_thr_xgb = np.percentile(tq, 90)
    med_thr_xgb  = np.percentile(tq, 70)
    df["xgb_target"] = np.where(
        tq > high_thr_xgb, "HIGH",
        np.where(tq > med_thr_xgb, "MEDIUM", "LOW")
    )
    print(f"  Distribución target XGBoost:\n{df['xgb_target'].value_counts().to_string()}")

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
    y_xgb = le_xgb.fit_transform(df["xgb_target"].astype(str))
    n_classes_xgb = len(le_xgb.classes_)

    xgb_params = dict(
        objective="multi:softprob",
        num_class=n_classes_xgb,
        max_depth=3,
        learning_rate=0.05,
        n_estimators=200,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=1,
        reg_lambda=2,
        min_child_weight=3,
        random_state=42,
        eval_metric="mlogloss",
    )
    
    X_tr_x, X_te_x, y_tr_x, y_te_x = train_test_split(
        X_xgb.values, y_xgb, test_size=0.2, random_state=42, stratify=y_xgb
    )
    
    # ── XGBoost Base Model ──────────────────────────────────────────────────
    # use_label_encoder eliminado en XGBoost >= 1.6
    try:
        xgb_base = XGBClassifier(**xgb_params, use_label_encoder=False)
    except TypeError:
        # XGBoost >= 1.6 no acepta use_label_encoder
        xgb_base = XGBClassifier(**xgb_params)
    
    # ── BaggingClassifier con Bootstrap para XGBoost ──────────────────────
    xgb_clf = BaggingClassifier(
        estimator=xgb_base,
        n_estimators=10,
        bootstrap=True,
        random_state=42,
        n_jobs=-1,
        verbose=0
    )
    xgb_clf.fit(X_tr_x, y_tr_x)
    
    # ── Evaluación Bootstrap de XGBoost ────────────────────────────────────
    from sklearn.metrics import accuracy_score, log_loss
    try:
        y_pred_xgb = xgb_clf.predict(X_te_x)
        acc_xgb = accuracy_score(y_te_x, y_pred_xgb)
        print(f"  XGBoost (Bagging) Test Accuracy: {acc_xgb:.4f}")
    except Exception as e:
        print(f"  XGBoost accuracy: {e}")
    
    # Bootstrap evaluation: entrenar múltiples versiones con muestras bootstrap
    n_bootstrap_xgb = 15
    bootstrap_acc_scores = []
    print(f"  XGBoost Bootstrap Evaluation ({n_bootstrap_xgb} iteraciones):")
    
    for b in range(n_bootstrap_xgb):
        X_boot_x, y_boot_x = resample(X_tr_x, y_tr_x, random_state=42+b)
        
        try:
            xgb_boot = XGBClassifier(**xgb_params, use_label_encoder=False)
        except TypeError:
            xgb_boot = XGBClassifier(**xgb_params)
        
        xgb_boot.fit(X_boot_x, y_boot_x, verbose=False)
        y_pred_boot = xgb_boot.predict(X_te_x)
        
        try:
            acc_boot = accuracy_score(y_te_x, y_pred_boot)
            bootstrap_acc_scores.append(acc_boot)
        except Exception:
            pass
    
    if bootstrap_acc_scores:
        mean_acc_boot = np.mean(bootstrap_acc_scores)
        std_acc_boot = np.std(bootstrap_acc_scores)
        ci_lower = np.percentile(bootstrap_acc_scores, 2.5)
        ci_upper = np.percentile(bootstrap_acc_scores, 97.5)
        print(f"    Mean Accuracy: {mean_acc_boot:.4f} ± {std_acc_boot:.4f}")
        print(f"    95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]")

    probs_xgb = xgb_clf.predict_proba(X_xgb.values)
    classes_xgb = list(le_xgb.classes_)  # e.g. ['HIGH', 'LOW', 'MEDIUM'] alphabetical

    if "HIGH" in classes_xgb:
        high_idx_xgb = classes_xgb.index("HIGH")
        df["xgb_prob_high"] = probs_xgb[:, high_idx_xgb]
    else:
        df["xgb_prob_high"] = probs_xgb.max(axis=1)

    print(f"  xgb_prob_high → [{df['xgb_prob_high'].min():.3f}, {df['xgb_prob_high'].max():.3f}]")

    # ── SHAP (opcional) ──────────────────────────────────────────────────────
    try:
        import shap
        # Usar muestra pequeña para evitar lentitud
        X_shap = X_xgb.values[:min(200, len(X_xgb))]
        explainer = shap.TreeExplainer(xgb_clf)
        # shap_values para multiclass devuelve array 3D (samples, features, classes)
        raw_shap = explainer.shap_values(X_shap)
        if isinstance(raw_shap, np.ndarray) and raw_shap.ndim == 3:
            # forma (samples, features, classes) → tomar clase HIGH
            sv = np.abs(raw_shap[:, :, high_idx_xgb]).mean(axis=0)
        elif isinstance(raw_shap, list):
            # lista de matrices 2D por clase
            sv = np.abs(raw_shap[high_idx_xgb]).mean(axis=0)
        else:
            sv = np.abs(raw_shap).mean(axis=0)
        shap_df = pd.DataFrame({"feature": xgb_avail, "shap_importance": sv})
        shap_df.sort_values("shap_importance", ascending=False).to_csv(
            os.path.join(BASE_DIR, "shap_importance.csv"), index=False
        )
        print("  SHAP guardado en shap_importance.csv")
    except Exception as e_shap:
        print(f"  SHAP omitido: {e_shap}")

except ImportError:
    print("  xgboost no instalado — usando trend_quality normalizada como fallback")
    mms_fb = MinMaxScaler()
    df["xgb_prob_high"] = mms_fb.fit_transform(
        df[["trend_quality"]].fillna(0)
    ).ravel()

# ═════════════════════════════════════════════════════════════════════════════
# PASO 5 — K-Means Clustering (k=4)
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("PASO 5 — K-Means Clustering  (Viral / Barato masivo / Estable / Muerto)")
print("=" * 65)

km_features = [
    "yt_total_views", "trends_slope", "ali_avg_evaluate_rate",
    "ali_avg_sale_price", "yt_engagement",
]
km_avail = [f for f in km_features if f in df.columns]
X_km = df[km_avail].copy()

imputer_km = SimpleImputer(strategy="median")
X_km_imp = imputer_km.fit_transform(X_km)

# log1p para reducir sesgo en vistas y precio
for col_name, arr_idx in [(c, km_avail.index(c)) for c in ["yt_total_views", "ali_avg_sale_price"] if c in km_avail]:
    X_km_imp[:, arr_idx] = np.log1p(X_km_imp[:, arr_idx])

scaler_km = StandardScaler()
X_km_sc = scaler_km.fit_transform(X_km_imp)

kmeans_model = KMeans(n_clusters=4, random_state=42, n_init=50)
df["cluster_id"] = kmeans_model.fit_predict(X_km_sc)

# Nombrar clusters según sus características medias
km_df = pd.DataFrame(X_km_imp, columns=km_avail)
km_df["cluster_id"] = df["cluster_id"].values
cluster_means = km_df.groupby("cluster_id")[km_avail].mean()

# Scoring heurístico: vistas altas + slope positivo + engagement alto = Viral
# Precio bajo + vistas medias = Barato masivo
# Estabilidad (slope ~0, rating alto) = Estable
# Todo bajo = Muerto
cluster_score = {}
for cid in range(4):
    r = cluster_means.loc[cid]
    views_sc = r.get("yt_total_views", 0)
    slope_sc = r.get("trends_slope", 0)
    eng_sc   = r.get("yt_engagement", 0)
    price_sc = r.get("ali_avg_sale_price", 0)
    cluster_score[cid] = views_sc * 1.0 + slope_sc * 5.0 + eng_sc * 3.0 - price_sc * 0.3

sorted_cids = sorted(cluster_score, key=cluster_score.get, reverse=True)
label_map = {
    sorted_cids[0]: "Viral/Premium",
    sorted_cids[1]: "Barato masivo",
    sorted_cids[2]: "Estable",
    sorted_cids[3]: "Muerto",
}
df["cluster"] = df["cluster_id"].map(label_map)
print(f"  Distribución de clusters:\n{df['cluster'].value_counts().to_string()}")
print(f"  Mapa cluster_id → etiqueta: {label_map}")

# ═════════════════════════════════════════════════════════════════════════════
# PASO 6 — Prophet Forecast → forecast_mean
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("PASO 6 — Prophet Forecast  (predicción temporal de trends_mean)")
print("=" * 65)

# forecast_mean por producto: proyección lineal a 90 días usando trends_slope
# Este es el método primario (siempre disponible y por producto)
df["forecast_mean"] = (
    df["trends_mean"].fillna(0) + df["trends_slope"].fillna(0) * 90
).clip(0, 100)
print(
    f"  Proyección por producto (trends_mean + slope×90d): "
    f"[{df['forecast_mean'].min():.2f}, {df['forecast_mean'].max():.2f}]"
)

# Prophet: forecast del mercado global (tendencia agregada) — informativo
prophet_ok = False
try:
    from prophet import Prophet

    df_ts = (
        df.dropna(subset=["generated_at"])
        .assign(ds=lambda x: x["generated_at"].dt.normalize())
        .groupby("ds")["trends_mean"]
        .mean()
        .reset_index()
        .rename(columns={"trends_mean": "y"})
        .sort_values("ds")
    )

    if len(df_ts) >= 5:
        df_ts["cap"]   = 100.0
        df_ts["floor"] = 0.0
        m_prophet = Prophet(
            growth="logistic",
            yearly_seasonality=False,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=0.05,
        )
        m_prophet.fit(df_ts)
        future_df = m_prophet.make_future_dataframe(periods=90)
        future_df["cap"]   = 100.0
        future_df["floor"] = 0.0
        forecast_df = m_prophet.predict(future_df)
        forecast_mean_global = float(forecast_df["yhat"].iloc[-1])
        forecast_mean_global = max(0.0, min(100.0, forecast_mean_global))
        df["forecast_mean_prophet"] = forecast_mean_global  # columna extra informativa
        prophet_ok = True
        print(f"  Prophet (mercado global a 90d): {forecast_mean_global:.2f}  →  columna 'forecast_mean_prophet'")
    else:
        print(f"  Prophet omitido: solo {len(df_ts)} días únicos")

except ImportError:
    print("  prophet no instalado — usando solo proyección por producto.")
except Exception as e_prophet:
    print(f"  Prophet omitido: {e_prophet}")

# ═════════════════════════════════════════════════════════════════════════════
# PASO 7 — Product Opportunity Score (POS)
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("PASO 7 — Product Opportunity Score (POS)")
print("=" * 65)
print(
    "  Fórmula: POS = 0.40·success_proba + 0.30·trend_quality\n"
    "                + 0.15·consistency_score + 0.15·social_velocity"
)

# Normalizar cada componente a [0, 1] antes de ponderar
def norm01(series: pd.Series) -> np.ndarray:
    vals = series.fillna(0).values.reshape(-1, 1)
    scaler = MinMaxScaler()
    return scaler.fit_transform(vals).ravel()

n_success   = norm01(df["success_proba"])
n_tquality  = norm01(df["trend_quality"])
n_consist   = norm01(df["consistency_score"])
n_social    = norm01(df["social_velocity"])

df["POS"] = (
    0.40 * n_success
    + 0.30 * n_tquality
    + 0.15 * n_consist
    + 0.15 * n_social
)

# Tiers basados en percentiles: HIGH top 10%, MEDIUM siguiente 20%, LOW resto
df["tier"] = pd.qcut(
    df["POS"],
    q=[0.0, 0.70, 0.90, 1.0],
    labels=["LOW", "MEDIUM", "HIGH"],
)

print(f"  POS → [{df['POS'].min():.4f}, {df['POS'].max():.4f}]")
print(f"  Distribución de tiers:\n{df['tier'].value_counts().sort_index().to_string()}")

# ═════════════════════════════════════════════════════════════════════════════
# PASO 8 — Exportar dashboard_final.csv
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("PASO 8 — Exportar dashboard_final.csv")
print("=" * 65)

FINAL_COLS = [
    "keyword",
    "category_name",
    "country",
    "trends_mean",
    "trends_slope",
    "yt_total_views",
    "yt_engagement",
    "ali_avg_sale_price",
    "cluster",
    "success_proba",
    "rf_prob",
    "xgb_prob_high",
    "forecast_mean",
    "trend_quality",
    "consistency_score",
    "social_velocity",
    "POS",
    "tier",
]

available_final = [c for c in FINAL_COLS if c in df.columns]
df_out = df[available_final].copy()

# Redondear columnas numéricas para legibilidad
round_cols = [
    "trends_mean", "trends_slope", "yt_total_views", "yt_engagement",
    "ali_avg_sale_price", "success_proba", "rf_prob", "xgb_prob_high",
    "forecast_mean", "trend_quality", "consistency_score", "social_velocity", "POS",
]
for rc in round_cols:
    if rc in df_out.columns:
        df_out[rc] = df_out[rc].round(6)

df_out.to_csv(OUTPUT_PATH, index=False)

print(f"\n  ✅  {len(df_out)} filas × {len(available_final)} columnas guardadas en:")
print(f"      {OUTPUT_PATH}")
print("\n" + "=" * 65)
print("  PIPELINE COMPLETO")
print("=" * 65)
print("\n  Columnas del dashboard:")
for col in available_final:
    print(f"    · {col}")
print(
    "\n  Siguiente paso: importar dashboard_final.csv en Google Data Studio\n"
    "  o Looker Studio como fuente de datos para visualizaciones interactivas.\n"
)
