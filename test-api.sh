#!/bin/bash

# Script de prueba de la API de Trends

echo "🧪 Probando Trends API"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Health Check
echo "1️⃣  Health Check"
echo -n "   GET /health ... "
HEALTH=$(curl -s http://localhost:3000/health)
STATUS=$(echo $HEALTH | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null)
if [ "$STATUS" = "ok" ]; then
    echo -e "${GREEN}✓ OK${NC}"
else
    echo -e "${RED}✗ FAIL${NC}"
    echo "$HEALTH"
fi
echo ""

# 2. Regiones
echo "2️⃣  Regiones Soportadas"
echo -n "   GET /v1/regions ... "
REGIONS=$(curl -s http://localhost:3000/v1/regions)
COUNT=$(echo $REGIONS | python3 -c "import sys, json; print(json.load(sys.stdin)['count'])" 2>/dev/null)
echo -e "${GREEN}✓ $COUNT regiones${NC}"
echo ""

# 3. Query de Tendencia (ejemplo simple)
echo "3️⃣  Query de Tendencia"
echo "   POST /v1/trends/query"
echo -e "   ${YELLOW}Keyword: bitcoin, Country: MX, Window: 30 días${NC}"
echo ""

curl -s -X POST http://localhost:3000/v1/trends/query \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "bitcoin",
    "country": "MX",
    "window_days": 30,
    "baseline_days": 365
  }' | python3 -m json.tool

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Pruebas completadas${NC}"
