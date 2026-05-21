# ============================================================
# Imagen ML Pipeline para el Job ETL (Paso 2)
# Ejecuta pipeline_s3.py: replica lógica de V2_FINAL/pipeline.py
# Lee desde s3://raw-data/ y escribe Parquet en s3://gold-data/
# ============================================================
FROM python:3.11-slim

# Instalar dependencias ML + S3
RUN pip install --no-cache-dir \
    boto3==1.34.69 \
    pyarrow==15.0.2 \
    pandas==2.2.1 \
    numpy==1.26.4 \
    scikit-learn==1.4.2 \
    xgboost==2.0.3

WORKDIR /app

# Copiar el pipeline dentro de la imagen
COPY pipeline_s3.py .

CMD ["python3", "/app/pipeline_s3.py"]
