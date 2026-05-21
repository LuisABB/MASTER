#!/usr/bin/env bash
# =============================================================
# run-step1.sh — Ejecuta completo el Paso 1: Ingesta CSV → S3
#
# Uso: ./k8s/step1/run-step1.sh
# =============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CSV_SRC="$REPO_ROOT/scripts/V2_FINAL/logisticregression/dataset_validated.csv"
NAMESPACE="default"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  PASO 1 — Capa Raw: Ingesta CSV → LocalStack S3      ║"
echo "╚══════════════════════════════════════════════════════╝"

# ── 1. Verificar que Minikube está corriendo ──────────────────
echo ""
echo "▶ Verificando Minikube..."
if ! minikube status | grep -q "host: Running"; then
  echo "  Minikube no está corriendo. Iniciando..."
  minikube start --memory=5120 --cpus=4 --driver=docker
fi
echo "  ✓ Minikube activo"

# ── 2. Copiar CSV al nodo Minikube ────────────────────────────
echo ""
echo "▶ Copiando CSV al nodo Minikube (/mnt/data/)..."
if [ ! -f "$CSV_SRC" ]; then
  echo "  ERROR: No se encontró el CSV en:"
  echo "  $CSV_SRC"
  exit 1
fi
minikube ssh "sudo mkdir -p /mnt/data" 2>/dev/null || true
minikube cp "$CSV_SRC" "minikube:/mnt/data/dataset_validated.csv"
echo "  ✓ CSV copiado → minikube:/mnt/data/dataset_validated.csv"

# ── 3. Desplegar LocalStack ───────────────────────────────────
echo ""
echo "▶ Desplegando LocalStack..."
kubectl apply -f "$SCRIPT_DIR/localstack-deployment.yaml" -n $NAMESPACE

echo "  Esperando a que LocalStack esté Ready..."
kubectl rollout status deployment/localstack -n $NAMESPACE --timeout=120s
echo "  ✓ LocalStack desplegado"

# ── 4. Ejecutar Job de ingesta ────────────────────────────────
echo ""
echo "▶ Lanzando Job de ingesta..."
# Eliminar job anterior si existe
kubectl delete job job-ingesta-csv -n $NAMESPACE 2>/dev/null || true
sleep 2
kubectl apply -f "$SCRIPT_DIR/job-ingesta.yaml" -n $NAMESPACE

echo "  Esperando a que el Job complete..."
kubectl wait --for=condition=complete job/job-ingesta-csv -n $NAMESPACE --timeout=180s

# ── 5. Mostrar logs del Job ───────────────────────────────────
echo ""
echo "▶ Logs del Job de ingesta:"
echo "─────────────────────────────────────────────────────────"
kubectl logs job/job-ingesta-csv -n $NAMESPACE
echo "─────────────────────────────────────────────────────────"

# ── 6. Verificación externa (port-forward + awscli) ───────────
echo ""
echo "▶ Verificación final desde tu máquina (port-forward)..."
kubectl port-forward svc/localstack 4566:4566 -n $NAMESPACE &
PF_PID=$!
sleep 3

echo "  Listando s3://raw-data/:"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 --region=us-east-1 \
      s3 ls s3://raw-data/ --human-readable

echo "  Listando todos los buckets:"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 --region=us-east-1 \
      s3 ls

kill $PF_PID 2>/dev/null || true

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅ PASO 1 COMPLETADO                                ║"
echo "║  CSV disponible en: s3://raw-data/dataset_validated.csv ║"
echo "║  Buckets creados: s3://raw-data  s3://gold-data      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Siguiente: cd k8s/step2 && ./run-step2.sh"
