Arquitectura recomendada y script de ejemplo

Este repositorio contiene un script `xgboost.py` que implementa:

- Cálculo de `trend_score` compuesto a partir de features de trends, YouTube y AliExpress.
- Clasificación multicategoría (HIGH/MEDIUM/LOW) con `XGBClassifier`.
- Entrenamiento de `XGBRanker` para ranking por categorías.
- Regresión con `XGBRegressor` para predecir `trend_score` (Commercial Predictive Score).
- Cálculo de `category_score` agregado por categoría.

Archivos principales:

- `xgboost.py`: script principal. Lee `dataset_validated.csv`, calcula `trend_score` y entrena modelos.
- `requirements.txt`: dependencias.

Ejemplo de uso (PowerShell):

```powershell
python xgboost.py --input dataset_validated.csv --do-classifier --do-regressor --do-ranker --do-category-score
```

Salida generada:

- `dataset_with_trend_score.csv`
- `category_scores.csv`
- Modelos en `models/` si XGBoost está instalado.

Siguientes pasos recomendados:

1. Revisar y ajustar pesos en `compute_trend_score` según negocio.
2. Añadir validación cruzada y búsqueda de hiperparámetros (GridSearchCV / Optuna).
3. Preparar pipelines de features (imputación, transformaciones categóricas).
4. Implementar evaluation A/B o backtesting para forecasting.
