FROM python:3.11-slim

RUN pip install --no-cache-dir pymongo==4.6.1

WORKDIR /app
COPY datamart_aggregation.py .

CMD ["python3", "/app/datamart_aggregation.py"]
