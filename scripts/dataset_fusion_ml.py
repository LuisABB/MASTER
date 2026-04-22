from pymongo import MongoClient
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix, precision_score, recall_score, f1_score
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

# ======================================
# FUNCIONES 
# ======================================

def safe_dataframe(data):
    return pd.json_normalize(data) if data else pd.DataFrame()

def clean_column_names(df):
    df.columns = [col.replace(".", "_") for col in df.columns]
    return df

def remove_unhashable(df):
    cols_to_drop = [
        col for col in df.columns
        if df[col].apply(lambda x: isinstance(x, (list, dict))).any()
    ]
    if cols_to_drop:
        print("🧹 Eliminando columnas problemáticas:", cols_to_drop)
    return df.drop(columns=cols_to_drop)

def safe_groupby(df, group_col, agg_dict):
    if df.empty or group_col not in df.columns:
        return pd.DataFrame(columns=[group_col] + list(agg_dict.keys()))
    for col in agg_dict.keys():
        if col not in df.columns:
            df[col] = 0
    return df.groupby(group_col).agg(agg_dict).reset_index()

# ======================================
# CONEXIÓN
# ======================================

client = MongoClient("mongodb+srv://David:Mysehna123@cluster0.2lyc7x2.mongodb.net/?retryWrites=true&w=majority")
db = client["ecommerce_metrics"]

# ======================================
# CARGA LIMPIEZA DE DATASETS
# ======================================

df_fusion = clean_column_names(safe_dataframe(list(db.fusion_requests.find())))
df_youtube = clean_column_names(safe_dataframe(list(db.youtube_summary.find())))
df_trends = clean_column_names(safe_dataframe(list(db.trends_summary.find())))
df_ali = clean_column_names(safe_dataframe(list(db.aliexpress_competitors.find())))

# ======================================
# ALIEXPRESS
# ======================================

df_ali_grouped = safe_groupby(df_ali, "request_id", {
    "pricing_sale_price": "mean",
    "metrics_evaluate_rate": "mean"
}).rename(columns={
    "pricing_sale_price": "sale_price",
    "metrics_evaluate_rate": "evaluation_rate"
})

# ======================================
# JOIN
# ======================================

df = df_fusion.copy()

if not df_youtube.empty:
    df = df.merge(df_youtube, on="request_id", how="left")

if not df_trends.empty:
    df = df.merge(df_trends, on="request_id", how="left")

if not df_ali_grouped.empty:
    df = df.merge(df_ali_grouped, on="request_id", how="left")

# ======================================
# LIMPIEZA
# ======================================

df = remove_unhashable(df)
df = df.drop_duplicates()
df = df.fillna(0)

# ======================================
# FEATURE ENGINEERING
# ======================================

# Engagement
if "total_likes" in df.columns and "total_views" in df.columns:
    df["engagement"] = df["total_likes"] / (df["total_views"] + 1)
elif "total_views" in df.columns and "videos_analyzed" in df.columns:
    df["engagement"] = df["total_views"] / (df["videos_analyzed"] + 1)

# Growth
df["growth"] = df.get("signals_growth_7_vs_30", 0)

# ======================================

# TARGET (CORREGIDO - SIN LEAKAGE Y BALANCEADO)
# ======================================

if not df.empty:
    # Score combinado SIN leakage
    df["trend_score"] = (
        df["signals_recent_peak_30d"] * 0.6 +
        df["signals_growth_7_vs_30"] * 0.4
    )

    try:
        df["target"] = pd.qcut(
            df["trend_score"],
            q=2,
            labels=[0, 1],
            duplicates="drop"
        ).astype(int)
    except ValueError as e:
        print("Advertencia: No se pudo crear target balanceado por falta de variedad en los datos. Se asigna target=0 a todo el dataset.")
        df["target"] = 0

    # Debug obligatorio
    print("\nDISTRIBUCIÓN DEL TARGET:")
    print(df["target"].value_counts())
    print(df["target"].value_counts(normalize=True))

# ======================================
# DATASET EXPORT
# ======================================

print("\nDATASET FINAL (preview)")
print(df.head())

print("\nColumnas finales:")
print(df.columns.tolist())

df.to_csv("dataset_final.csv", index=False)
print("\nDataset guardado como dataset_final.csv")

# ======================================
# FEATURES CORRECTAS (SIN TRAMPA)
# ======================================

cols = [
    "sale_price",
    "evaluation_rate",
    "engagement",
    "growth",
    "signals_slope_14d",
    "series_count"
]

X = df[cols]
y = df["target"]

# ======================================
# TRAIN / TEST (STRATIFIED)
# ======================================

X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# ======================================
# ESCALADO CORRECTO (FIN DE LIMPIEZA)
# ======================================

scaler = StandardScaler()

X_train = X_train.copy()
X_test = X_test.copy()

X_train[cols] = scaler.fit_transform(X_train[cols])
X_test[cols] = scaler.transform(X_test[cols])

# ======================================
# MODELOS PREDICTIVOS
# ======================================

# ======================================
# 1. LOGISTIC REGRESSION
#
#X_train → datos para enseñar al modelo  
#y_train → respuestas correctas (lo que debe aprender)
#
#X_test → datos nuevos (examen)  
#y_test → respuestas reales para comparar
#
#X = información  
#y = respuesta
# ======================================

log_model = LogisticRegression()

log_model.fit(X_train, y_train)


y_pred_log = log_model.predict(X_test)
print("\n📊 MÉTRICAS - LOGISTIC REGRESSION")
print("Accuracy:", accuracy_score(y_test, y_pred_log))
print("Precision:", precision_score(y_test, y_pred_log))
print("Recall:", recall_score(y_test, y_pred_log))
print("F1-score:", f1_score(y_test, y_pred_log))

print("\nMatriz de confusión:")
print(confusion_matrix(y_test, y_pred_log))

importance_log = pd.DataFrame({
    "feature": cols,
    "coef": log_model.coef_[0]
}).sort_values(by="coef", ascending=False)

print("\nIMPORTANCIA - LOGISTIC REGRESSION")
print(importance_log)

# ======================================
# 2. RANDOM FOREST
# ======================================


model = RandomForestClassifier(
    n_estimators=200,
    max_depth=None,
    min_samples_split=5,
    random_state=42
)

model.fit(X_train, y_train)


y_pred = model.predict(X_test)
print("\n📊 MÉTRICAS - RANDOM FOREST")
print("Accuracy:", accuracy_score(y_test, y_pred))
print("Precision:", precision_score(y_test, y_pred))
print("Recall:", recall_score(y_test, y_pred))
print("F1-score:", f1_score(y_test, y_pred))

print("\nClassification Report:")
print(classification_report(y_test, y_pred))

print("\nMatriz de confusión:")
print(confusion_matrix(y_test, y_pred))

# ======================================
# VALIDACIÓN CRUZADA
# ======================================

scores = cross_val_score(model, X, y, cv=5)

# ======================================
# FEATURE IMPORTANCE
# ======================================

importance = pd.DataFrame({
    "feature": cols,
    "importance": model.feature_importances_
}).sort_values(by="importance", ascending=False)

print("\nIMPORTANCIA - RANDOM FOREST")
print(importance)

# ======================================
# MODELO 3: XGBOOST
# ======================================

xgb_model = XGBClassifier(
    n_estimators=200,
    max_depth=4,
    learning_rate=0.1,
    random_state=42,
    eval_metric='logloss'
)

xgb_model.fit(X_train, y_train)


y_pred_xgb = xgb_model.predict(X_test)
print("\n📊 MÉTRICAS - XGBOOST")
print("Accuracy:", accuracy_score(y_test, y_pred_xgb))
print("Precision:", precision_score(y_test, y_pred_xgb))
print("Recall:", recall_score(y_test, y_pred_xgb))
print("F1-score:", f1_score(y_test, y_pred_xgb))

print("\nClassification Report:")
print(classification_report(y_test, y_pred_xgb))

print("\nMatriz de confusión:")
print(confusion_matrix(y_test, y_pred_xgb))

importance_xgb = pd.DataFrame({
    "feature": cols,
    "importance": xgb_model.feature_importances_
}).sort_values(by="importance", ascending=False)

print("\nIMPORTANCIA - XGBOOST")
print(importance_xgb)