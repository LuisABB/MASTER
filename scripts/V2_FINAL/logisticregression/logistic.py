# -*- coding: utf-8 -*-
"""
Programa: Logistic Regression - Predicción de éxito de productos
Autor: [Tu nombre]
Fecha: [Fecha]
"""

# 1. Librerías
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold, GridSearchCV, cross_validate
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    average_precision_score,
)

# 2. Cargar datos
file_path = 'dataset_validated.csv'
df = pd.read_csv(file_path)

# 3. Crear target binario de éxito
# Opciones de creación de target:
# - 'threshold': usar un umbral fijo en `trends_slope`
# - 'percentile': marcar como éxito el top X% por `trends_slope`
# - 'composite': combinar señales (trends + youtube + ali) en un score
target_method = 'percentile'  # 'threshold' | 'percentile' | 'composite'
percentile = 75  # top 25% serán considerados éxito

if target_method == 'threshold':
    threshold_slope = 0.5
    df['success'] = (df['trends_slope'] > threshold_slope).astype(int)
elif target_method == 'percentile':
    cutoff = np.percentile(df['trends_slope'].dropna(), percentile)
    df['success'] = (df['trends_slope'] >= cutoff).astype(int)
else:
    # composite score: combine normalized trends_slope, yt engagement and ali price
    # Normalizar por z-score
    trend_z = (df['trends_slope'] - df['trends_slope'].mean()) / df['trends_slope'].std(ddof=0)
    yt_engagement = df['yt_total_likes'] / df['yt_total_views'].replace(0, np.nan)
    yt_z = (yt_engagement - yt_engagement.mean()) / yt_engagement.std(ddof=0)
    ali_price_z = (df['ali_avg_sale_price'] - df['ali_avg_sale_price'].mean()) / df['ali_avg_sale_price'].std(ddof=0)
    # Composite: favor trends and engagement (weights pueden ajustarse)
    composite = 0.5 * trend_z.fillna(0) + 0.4 * yt_z.fillna(0) - 0.1 * ali_price_z.fillna(0)
    cutoff = np.percentile(composite.dropna(), percentile)
    df['success'] = (composite >= cutoff).astype(int)

# 4. Feature engineering y selección
# Derivadas sugeridas: engagement, cambio relativo, precio normalizado por categoría
df['yt_engagement'] = df['yt_total_likes'] / df['yt_total_views'].replace(0, np.nan)
df['trends_rel_change'] = np.where(
    df['trends_first_value'] == 0,
    0,
    (df['trends_last_value'] - df['trends_first_value']) / df['trends_first_value']
)
# Precio normalizado por categoría
df['ali_price_by_cat_mean'] = df.groupby('category_name')['ali_avg_sale_price'].transform('mean')
df['ali_price_norm_by_cat'] = df['ali_avg_sale_price'] / df['ali_price_by_cat_mean'].replace(0, np.nan)

numeric_features = [
    'ali_avg_sale_price', 'ali_avg_evaluate_rate',
    'trends_count', 'trends_mean', 'trends_max', 'trends_min', 'trends_std',
    'trends_first_value', 'trends_last_value', 'trends_slope', 'trends_rel_change',
    'yt_total_views', 'yt_total_likes', 'yt_total_comments', 'yt_videos_count', 'yt_engagement',
    'ali_price_norm_by_cat'
]

# One-hot encode `category_name` (drop first to avoid multicollinearity)
cat_dummies = pd.get_dummies(df['category_name'].fillna('NA'), prefix='cat', drop_first=True)

X = pd.concat([df[numeric_features], cat_dummies], axis=1)
y = df['success']

# 5. Manejar valores faltantes
# 5. Manejar valores faltantes
imputer = SimpleImputer(strategy='mean')
X_imputed = imputer.fit_transform(X)

# 6. Dividir en train/test
# 6. Dividir en train/test
X_train, X_test, y_train, y_test = train_test_split(
    X_imputed, y, test_size=0.2, random_state=42, stratify=y
)

# 7. Escalar features
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# 8. Entrenar Logistic Regression
# 8. Entrenar Logistic Regression con búsqueda de hiperparámetros
base = LogisticRegression(solver='liblinear', max_iter=1000, random_state=42)
param_grid = {
    'C': [0.01, 0.1, 1, 10],
    'penalty': ['l1', 'l2']
}
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
grid = GridSearchCV(base, param_grid, scoring='roc_auc', cv=cv, n_jobs=-1)
grid.fit(X_train_scaled, y_train)
best = grid.best_estimator_

# 9. Predicciones y probabilidades con el mejor modelo
y_pred = best.predict(X_test_scaled)
y_proba = best.predict_proba(X_test_scaled)[:, 1]

# 10. Evaluación del modelo
print("=== Mejor estimador ===")
print(grid.best_params_)

print("\n=== Matriz de Confusión ===")
print(confusion_matrix(y_test, y_pred))
print("\n=== Reporte de Clasificación ===")
print(classification_report(y_test, y_pred, digits=4))

roc_auc = roc_auc_score(y_test, y_proba)
ap = average_precision_score(y_test, y_proba)
print(f"ROC AUC: {roc_auc:.4f}")
print(f"Average Precision (PR AUC): {ap:.4f}")

# 11. Coeficientes para interpretar variables
# Coeficientes: necesitamos los nombres de las features después del preprocesamiento
feature_names = list(X.columns)
coef_df = pd.DataFrame({
    'feature': feature_names,
    'coefficient': best.coef_[0]
}).reindex(columns=['feature', 'coefficient'])
coef_df = coef_df.assign(abs_coef=coef_df['coefficient'].abs()).sort_values(by='abs_coef', ascending=False).drop(columns='abs_coef')
print("\n=== Coeficientes del modelo (ordenados por magnitud) ===")
print(coef_df)

# 12. Probabilidades de éxito para todos los productos
# 12. Probabilidades de éxito para todos los productos (modelo entrenado)
df['success_proba'] = best.predict_proba(scaler.transform(X_imputed))[:, 1]

# 13. Exportar resultados
df[['keyword', 'category_name', 'success', 'success_proba']].to_csv(
    'productos_con_probabilidades.csv', index=False
)
coef_df.to_csv('coeficientes_modelo.csv', index=False)

print("\nArchivos exportados: 'productos_con_probabilidades.csv' y 'coeficientes_modelo.csv'")