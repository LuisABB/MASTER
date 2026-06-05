FROM python:3.11-slim

RUN pip install --no-cache-dir \
    boto3==1.34.69 \
    pyarrow==15.0.2 \
    pandas==2.2.1 \
    numpy==1.26.4 \
    pymongo==4.6.1

WORKDIR /app
COPY loader_s3_to_mongo.py .

CMD ["python3", "/app/loader_s3_to_mongo.py"]
