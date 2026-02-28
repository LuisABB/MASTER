#!/bin/bash
# Test script para verificar que la API Python funciona correctamente

BASE_URL="http://localhost:3000"

echo "🧪 Testing Trends API (Python/Flask)"
echo "===================================="
echo ""

# Test 1: Root endpoint
echo "1️⃣  Testing root endpoint..."
curl -s "$BASE_URL/" | jq '.name, .version' || echo "❌ Failed"
echo ""

# Test 2: Health check
echo "2️⃣  Testing health check..."
curl -s "$BASE_URL/health" | jq '.status' || echo "❌ Failed"
echo ""

# Test 3: Regions
echo "3️⃣  Testing regions endpoint..."
curl -s "$BASE_URL/v1/regions" | jq '.count' || echo "❌ Failed"
echo ""

# Test 4: Mock trends (development endpoint)
echo "4️⃣  Testing mock trends endpoint..."
curl -s -X POST "$BASE_URL/dev/mock-trends" \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "test",
    "country": "MX",
    "window_days": 7
  }' | jq -r '.source, "TimeSeries:", (.timeSeries | length)' || echo "❌ Failed"
echo ""

# Test 5: Real trends query (with mocks in test mode)
echo "5️⃣  Testing real trends query endpoint (may take 15-20s)..."
curl -s --max-time 60 -X POST "$BASE_URL/v1/trends/query" \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "python",
    "country": "MX",
    "window_days": 7
  }' | jq -r '.keyword, .trend_score, (.series | length), .sources_used[0]' || echo "❌ Failed"
echo ""

echo "===================================="
echo "✅ All tests completed!"
