# Pipeline MVP — Fase 2: Prototipo Funcional Cloud-in-Local

Arquitectura completa de ingesta, procesamiento ML y servicio analítico sobre Kubernetes local (Minikube) simulando un entorno AWS.

---

## Arquitectura General

```
CSV (local)
    │
    ▼
[Paso 1] Job K8s ──────────► S3 raw-data (LocalStack)
                                    │
                                    ▼
                            [Paso 2] Job K8s (ML Pipeline)
                                    │
                                    ▼
                             S3 gold-data (Parquet)
                                    │
                                    ▼
                            [Paso 3] Job K8s (Loader)
                                    │
                                    ▼
                          MongoDB analytics_db
                          └─ gold_opportunity_ranking (326 docs)
                                    │
                                    ▼
                            [Paso 4] Job K8s (Data Mart)
                                    │
                                    ▼
                          MongoDB analytics_db
                          └─ gold_opportunity_ranking_by_category (27 docs)
                                    │
                                    ▼
                         [export_to_sheets.py] → category_ranking.csv
                                    │
                                    ▼
                           Google Sheets → Looker Studio
```

---

## Infraestructura Kubernetes

| Componente | Tipo | Imagen | Namespace |
|---|---|---|---|
| LocalStack | Deployment | `localstack/localstack:3.4` | default |
| MongoDB | StatefulSet | `mongo:7.0` | default |
| Job Paso 1 | Job | `amazon/aws-cli:2.22.35` | default |
| Job Paso 2 | Job | `ml-pipeline:latest` | default |
| Job Paso 3 | Job | `mongo-loader:latest` | default |
| Job Paso 4 | Job | `datamart:latest` | default |

---

## Paso 1 — Ingesta CSV → S3

**Archivo:** `k8s/step1/job-ingesta.yaml`

Sube el dataset crudo a LocalStack S3 simulando el bucket `raw-data` de AWS.

### Ejecutar

```bash
kubectl delete job job-ingesta-csv --ignore-not-found
kubectl apply -f k8s/step1/job-ingesta.yaml
kubectl wait --for=condition=complete job/job-ingesta-csv --timeout=60s
```

### Verificar

```bash
# Ver el archivo subido
kubectl exec deploy/localstack -- aws --endpoint-url=http://localhost:4566 \
  s3 ls s3://raw-data/

# Resultado esperado:
# dataset_validated.csv   (326 filas)
```

```bash
# Ver los buckets creados
kubectl exec deploy/localstack -- aws --endpoint-url=http://localhost:4566 \
  s3 ls

# Resultado esperado:
# raw-data
# gold-data
```

---

## Paso 2 — Pipeline ML → Parquet en S3

**Archivo:** `k8s/step2/job-spark-etl.yaml`  
**Script:** `k8s/step2/pipeline_s3.py`

Lee el CSV desde `s3://raw-data/`, ejecuta el pipeline ML completo y escribe el resultado en `s3://gold-data/` como Parquet comprimido (snappy).

### Pipeline ML ejecutado

| Etapa | Algoritmo | Output |
|---|---|---|
| Clasificación base | Logistic Regression | `target` (0/1) |
| Feature importance | Random Forest | `success_proba` |
| Score de oportunidad | XGBoost | `xgb_prob_high`, `tier` (HIGH/MEDIUM/LOW) |
| Segmentación | K-Means (4 clusters) | `cluster` (Viral/Premium, Barato masivo, Estable, Muerto) |
| Forecast de tendencia | Prophet | `forecast_mean` |
| Score final | POS (composite) | `POS` (0–5) |

### Ejecutar

```bash
eval $(minikube docker-env)
cd k8s/step2 && docker build -t ml-pipeline:latest . && cd ../..

kubectl delete job job-ml-pipeline --ignore-not-found
kubectl apply -f k8s/step2/job-spark-etl.yaml
kubectl wait --for=condition=complete job/job-ml-pipeline --timeout=180s
kubectl logs job/job-ml-pipeline
```

### Verificar

```bash
# Ver el Parquet generado en S3
kubectl exec deploy/localstack -- aws --endpoint-url=http://localhost:4566 \
  s3 ls s3://gold-data/ --recursive

# Resultado esperado:
# dashboard_final/dashboard_final.snappy.parquet
```

---

## Paso 3 — Parquet → MongoDB

**Archivo:** `k8s/step3/job-loader.yaml`  
**Script:** `k8s/step3/loader_s3_to_mongo.py`

Lee el Parquet desde `s3://gold-data/` e inserta los 326 productos ML-enriquecidos en MongoDB `analytics_db.gold_opportunity_ranking`.

**Colección:** `gold_opportunity_ranking`  
**Campos ML clave:** `POS`, `tier`, `cluster`, `success_proba`, `xgb_prob_high`, `forecast_mean`, `category_name`  
**Índices:** `POS` (desc), `tier`, `cluster`, `category_name`, `country`

### Ejecutar

```bash
eval $(minikube docker-env)
cd k8s/step3 && docker build -t mongo-loader:latest . && cd ../..

kubectl delete job job-parquet-loader --ignore-not-found
kubectl apply -f k8s/step3/job-loader.yaml
kubectl wait --for=condition=complete job/job-parquet-loader --timeout=60s
kubectl logs job/job-parquet-loader
```

### Verificar

```bash
# Contar documentos insertados
kubectl exec -it mongodb-0 -- mongosh analytics_db --eval \
  "print(db.gold_opportunity_ranking.countDocuments())"

# Resultado esperado: 326
```

```bash
# Ver un documento de ejemplo
kubectl exec -it mongodb-0 -- mongosh analytics_db --eval \
  "printjson(db.gold_opportunity_ranking.findOne({},{keyword:1,category_name:1,POS:1,tier:1,cluster:1,_id:0}))"

# Resultado esperado:
# {
#   keyword: 'patin electrico',
#   category_name: 'Sports & Entertainment',
#   cluster: 'Muerto',
#   POS: 0.158282,
#   tier: 'LOW'
# }
```

```bash
# Ver índices creados
kubectl exec -it mongodb-0 -- mongosh analytics_db --eval \
  "printjson(db.gold_opportunity_ranking.getIndexes().map(i => i.name))"
```

---

## Paso 4 — Data Mart (Agregación por Categoría)

**Archivo:** `k8s/step4/job-datamart.yaml`  
**Script:** `k8s/step4/datamart_aggregation.py`

Ejecuta un pipeline de agregación MongoDB que materializa una vista pre-calculada por categoría en `gold_opportunity_ranking_by_category`.

**Colección destino:** `gold_opportunity_ranking_by_category`  
**Documentos:** 27 categorías  
**Campos:** `category_name`, `total_products`, `avg_POS`, `max_POS`, `avg_success_proba`, `avg_trend_quality`, `avg_social_velocity`, `avg_xgb_prob_high`, `tier_distribution`, `cluster_distribution`, `top_products` (top 3), `computed_at`

### Pipeline de Agregación

```
$match (filtrar nulls) → $group (por categoría) → $project (redondear)
→ $sort (avg_POS desc) → $addFields (computed_at) → $out (escribir colección)
```

### Ejecutar

```bash
eval $(minikube docker-env)
cd k8s/step4 && docker build -t datamart:latest . && cd ../..

kubectl delete job job-datamart --ignore-not-found
kubectl apply -f k8s/step4/job-datamart.yaml
kubectl wait --for=condition=complete job/job-datamart --timeout=60s
kubectl logs job/job-datamart
```

### Verificar

```bash
# Contar categorías en el Data Mart
kubectl exec -it mongodb-0 -- mongosh analytics_db --eval \
  "print(db.gold_opportunity_ranking_by_category.countDocuments())"

# Resultado esperado: 27
```

```bash
# Ver top 5 categorías por avg_POS
kubectl exec -it mongodb-0 -- mongosh analytics_db --eval \
  "db.gold_opportunity_ranking_by_category
    .find({},{category_name:1,total_products:1,avg_POS:1,tier_distribution:1,_id:0})
    .sort({avg_POS:-1}).limit(5).forEach(d => printjson(d))"
```

```bash
# Ver un documento completo
kubectl exec -it mongodb-0 -- mongosh analytics_db --eval \
  "printjson(db.gold_opportunity_ranking_by_category.findOne(
    {},
    {category_name:1,total_products:1,avg_POS:1,tier_distribution:1,top_products:1,_id:0}
  ))"

# Resultado esperado:
# {
#   total_products: 1,
#   category_name: 'Motorcycle Equipments & Parts',
#   avg_POS: 0.6643,
#   tier_distribution: { HIGH: 1, MEDIUM: 0, LOW: 0 },
#   top_products: [{
#     keyword: 'casco bicicleta',
#     POS: 0.664298,
#     tier: 'HIGH',
#     cluster: 'Viral/Premium',
#     success_proba: 0.999798,
#     xgb_prob_high: 0.9421929717063904
#   }]
# }
```

---

## Exportación a CSV → Looker Studio

**Script:** `scripts/export_to_sheets.py`

Exporta el Data Mart (Paso 4) a CSV plano para subir a Google Sheets y conectar con Looker Studio.

### Prerequisito

```bash
# El port-forward debe estar activo
kubectl port-forward svc/mongodb 27017:27017 &
```

### Ejecutar

```bash
cd scripts
python export_to_sheets.py

# Output: category_ranking.csv (27 filas, 22 columnas)
```

### Conectar a Looker Studio

1. Sube `scripts/category_ranking.csv` a [sheets.google.com](https://sheets.google.com) → **File → Import**
2. Ve a [lookerstudio.google.com](https://lookerstudio.google.com) → **Create → Report**
3. **Add data** → **Google Sheets** → selecciona la hoja importada
4. Columnas disponibles: `avg_POS`, `tier_HIGH`, `tier_MEDIUM`, `tier_LOW`, `cluster_viral`, `top_product_1`, etc.

---

## Re-ejecución Completa del Pipeline

> **Nota:** LocalStack no persiste datos al reiniciar Minikube. MongoDB sí persiste (PVC). Si reinicias Minikube, ejecuta Pasos 1 y 2 antes de continuar.

```bash
# Verificar estado del cluster
minikube status
kubectl get pods

# Paso 1 — Reingestar CSV
kubectl delete job job-ingesta-csv --ignore-not-found
kubectl apply -f k8s/step1/job-ingesta.yaml
kubectl wait --for=condition=complete job/job-ingesta-csv --timeout=60s

# Paso 2 — Re-correr ML Pipeline
kubectl delete job job-ml-pipeline --ignore-not-found
kubectl apply -f k8s/step2/job-spark-etl.yaml
kubectl wait --for=condition=complete job/job-ml-pipeline --timeout=180s

# Paso 3 — Recargar MongoDB
kubectl delete job job-parquet-loader --ignore-not-found
kubectl apply -f k8s/step3/job-loader.yaml
kubectl wait --for=condition=complete job/job-parquet-loader --timeout=60s

# Paso 4 — Recalcular Data Mart
kubectl delete job job-datamart --ignore-not-found
kubectl apply -f k8s/step4/job-datamart.yaml
kubectl wait --for=condition=complete job/job-datamart --timeout=60s

# Exportar CSV
cd scripts && python export_to_sheets.py
```

---

## Estado Final Verificado

| Componente | Estado | Evidencia |
|---|---|---|
| S3 raw-data | ✅ | `dataset_validated.csv` 326 filas |
| S3 gold-data | ✅ | `dashboard_final.snappy.parquet` 326 filas × 18 cols |
| MongoDB Paso 3 | ✅ | `gold_opportunity_ranking` — 326 documentos |
| MongoDB Paso 4 | ✅ | `gold_opportunity_ranking_by_category` — 27 categorías |
| CSV exportado | ✅ | `scripts/category_ranking.csv` — 27 filas × 22 columnas |
