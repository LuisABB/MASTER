Random Forest classifier pipeline

Descripción
- Este repo contiene un script `randomforestclassifier.py` que carga `dataset_validated.csv`, construye un `trend_score` compuesto, crea un target binario `success`, entrena un Random Forest y muestra métricas y la importancia de features.

Cómo usar (Windows PowerShell)

1) Crear un entorno virtual (opcional pero recomendado):

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
```

2) Instalar dependencias:

```powershell
pip install -r requirements.txt
```

3) Ejecutar el script:

```powershell
python randomforestclassifier.py
```

Parámetros editables
- `THRESHOLD` en la parte superior del script: valor numérico o `None` (usa la mediana)
- `TEST_SIZE`, `N_ESTIMATORS`, `MAX_DEPTH` también están definidos al inicio

Salida
- Métricas en consola (accuracy, confusion matrix, classification report)
- `rf_model.joblib` guardado en el mismo directorio
