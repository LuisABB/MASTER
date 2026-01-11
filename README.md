# Trends API - MVP 1.1 (Google Trends Real API + 5 Años)

API multi-fuente para análisis de tendencias. **MVP 1.1 implementa Google Trends REAL con soporte para hasta 5 años de datos históricos**, sistema anti-bloqueos, scoring automático, cache agresivo (24h) y fallback a datos stale.

## 🚀 Características

- ✅ **Google Trends Real API**: Datos reales usando `google-trends-api` (no mock)
- ✅ **Hasta 5 Años de Histórico**: Consulta hasta 1825 días para análisis predictivo
- ✅ **Sistema Anti-Bloqueos**: Lock de concurrencia, delays largos, exponential backoff
- ✅ **Fallback Inteligente**: Cache stale (48h) como backup si Google falla
- ✅ **Scoring Automático**: Algoritmo de 3 señales (growth, slope, peak)
- ✅ **Cache Versionado**: Redis con keys v4 (previene conflictos en actualizaciones)
- ✅ **Persistencia**: PostgreSQL con historial completo
- ✅ **Rate Limiting**: Protección contra abuso + delays anti-bot
- ✅ **Observabilidad**: Logging estructurado con Pino + detección de bloqueos
- ✅ **Validación robusta**: Zod schemas con límites de 5 años
- ✅ **Países soportados**: México (MX), Costa Rica (CR), España (ES)

## ⚠️ Importante: Google Trends Limitaciones

**Google Trends puede bloquear requests si:**
- Muchos requests en poco tiempo
- Detecta patrones de bot
- Consultas muy largas (>5 años no soportado)

**Solución implementada (MVP):**
1. ✅ Cache 24 horas (reduce requests en 90%)
2. ✅ Solo 1 request simultáneo (lock con cola)
3. ✅ Delays 4-5 segundos entre requests
4. ✅ Fallback a cache stale si falla (disponibilidad >98%)
5. ✅ Límite máximo: 1825 días (5 años)

**Ver guía de análisis:** `ANALYSIS_GUIDE.md`

## 📋 Requisitos

- Node.js >= 18.0.0
- PostgreSQL >= 14
- Redis >= 6.0 (REQUERIDO para cache y fallback stale)
- npm o pnpm

## 🛠️ Setup Rápido

### 1. Clonar e instalar dependencias

```bash
npm install
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

**Variables clave para MVP anti-bloqueos:**
```bash
CACHE_TTL_SECONDS=86400              # 24 horas
CACHE_STALE_TTL_SECONDS=172800       # 48 horas para fallback
GOOGLE_TRENDS_REQUEST_DELAY_MS=4000  # 4s entre requests
GOOGLE_TRENDS_RETRY_DELAY_MS=5000    # 5s base para backoff
GOOGLE_TRENDS_CONCURRENCY=1          # Solo 1 request simultáneo
```

### 3. Asegurarse de que PostgreSQL y Redis estén corriendo

```bash
# Verificar PostgreSQL
sudo systemctl status postgresql

# Verificar Redis (CRÍTICO para fallback stale)
sudo systemctl status redis-server

# Si no están corriendo, iniciarlos
sudo systemctl start postgresql
sudo systemctl start redis-server
```

### 4. Crear base de datos y usuario

```bash
# Crear usuario y base de datos en PostgreSQL
sudo -u postgres psql -c "CREATE USER trends_user WITH PASSWORD 'trends_password';"
sudo -u postgres psql -c "CREATE DATABASE trends_db OWNER trends_user;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE trends_db TO trends_user;"
sudo -u postgres psql -c "ALTER USER trends_user CREATEDB;"
sudo -u postgres psql -d trends_db -c "GRANT ALL ON SCHEMA public TO trends_user;"
```

### 5. Ejecutar migraciones de base de datos

```bash
npm run db:generate
npm run db:migrate
```

### 6. Iniciar el servidor

```bash
npm run dev
```

La API estará disponible en `http://localhost:3000`

## 📡 Endpoints

### Health Check

```bash
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-01-10T12:00:00Z",
  "uptime": 123.45,
  "services": {
    "database": "ok",
    "cache": "ok"
  }
}
```

### Consultar Tendencia

```bash
POST /v1/trends/query
Content-Type: application/json

{
  "keyword": "bitcoin",
  "country": "MX",
  "window_days": 30,
  "baseline_days": 1795
}
```

**Parámetros:**
- `keyword` (string, 2-60 chars): Palabra clave a analizar
- `country` (string): `MX`, `CR`, o `ES`
- `window_days` (number): 7, 30, 90, o 365 días de ventana de análisis
- `baseline_days` (number): 30-1825 días de histórico (máximo 5 años)
  - ⚠️ **Límite total**: `window_days + baseline_days ≤ 1825` (5 años)

**Response:**
```json
{
  "keyword": "bitcoin",
  "country": "MX",
  "window_days": 30,
  "baseline_days": 1795,
  "generated_at": "2026-01-11T12:00:00Z",
  "sources_used": ["google_trends"],
  "trend_score": 72.6,
  "signals": {
    "growth_7_vs_30": 1.34,
    "slope_14d": 0.18,
    "recent_peak_30d": 0.92
  },
  "series": [
    { "date": "2021-02-07", "value": 21 },  // ← 5 años atrás
    { "date": "2021-02-14", "value": 19 },
    // ... ~260 semanas de datos ...
    { "date": "2026-01-04", "value": 45 },
    { "date": "2026-01-11", "value": 42 }
  ],
  "by_country": [
    { "country": "MX", "value": 100 },
    { "country": "CR", "value": 78 },
    { "country": "ES", "value": 65 }
  ],
  "explain": [
    "El interés en los últimos 7 días creció 34% vs los últimos 30 días.",
    "La tendencia de los últimos 14 días es positiva (creciente).",
    "El interés reciente alcanzó 92% del máximo posible.",
    "Los datos corresponden a México (MX)."
  ],
  "cache": {
    "hit": false,
    "ttl_seconds": 86400  // 24 horas
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Granularidad de datos (automática por Google Trends):**
- 1-90 días: Datos diarios
- 91-1825 días: Datos semanales (~260 puntos para 5 años)

### Listar Países Soportados

```bash
GET /v1/countries
```

**Response:**
```json
{
  "count": 3,
  "countries": [
    { "code": "MX", "name": "México" },
    { "code": "CR", "name": "Costa Rica" },
    { "code": "ES", "name": "España" }
  ]
}
```

## 🧪 Ejemplos de Uso

### Análisis de 1 Año (Default)

```bash
# Análisis estándar: últimos 30 días vs 1 año de histórico
curl -X POST http://localhost:3000/v1/trends/query \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "bitcoin",
    "country": "MX",
    "window_days": 30,
    "baseline_days": 365
  }'
```

### Análisis de 5 Años (Máximo - Para Predicción)

```bash
# Análisis profundo: últimos 30 días vs 5 años de histórico
# Ideal para detectar estacionalidad y predecir patrones
curl -X POST http://localhost:3000/v1/trends/query \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "viva mexico",
    "country": "MX",
    "window_days": 30,
    "baseline_days": 1795
  }' | jq '{
    keyword,
    trend_score,
    series_length: (.series | length),
    first_date: .series[0].date,
    last_date: .series[-1].date,
    by_country
  }'

# Response esperado:
# {
#   "keyword": "viva mexico",
#   "trend_score": 35.03,
#   "series_length": 261,      # ~5 años en semanas
#   "first_date": "2021-02-07", # Inicio: Feb 2021
#   "last_date": "2026-01-11",  # Fin: Hoy
#   "by_country": [
#     { "country": "MX", "value": 100 },
#     { "country": "CR", "value": 8 },
#     { "country": "ES", "value": 3 }
#   ]
# }
```

### Análisis Rápido (7 Días vs 30 Días)

```bash
# Análisis de corto plazo
curl -X POST http://localhost:3000/v1/trends/query \
  -H "Content-Type": application/json" \
  -d '{
    "keyword": "mundial futbol",
    "country": "CR",
    "window_days": 7,
    "baseline_days": 30
  }'
```

### Scripts de Utilidad

```bash
# Ver países soportados
curl http://localhost:3000/v1/countries

# Health check
curl http://localhost:3000/health

# Limpiar cache (útil después de actualizaciones)
npm run cache:clear

# Ver keys en cache
npm run cache:keys
```

### Con JavaScript/Fetch

```javascript
// Análisis de 5 años para machine learning
const response = await fetch('http://localhost:3000/v1/trends/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    keyword: 'bitcoin',
    country: 'MX',
    window_days: 30,
    baseline_days: 1795  // 5 años
  })
});

const data = await response.json();

console.log(`Trend Score: ${data.trend_score}`);
console.log(`Historical data points: ${data.series.length}`);
console.log(`Date range: ${data.series[0].date} to ${data.series[data.series.length-1].date}`);
console.log(`Explanations:`, data.explain);

// Usar series para análisis predictivo
const series = data.series.map(p => ({
  date: new Date(p.date),
  value: p.value
}));
```

## 📊 Modelo de Scoring

El `trend_score` (0-100) se calcula con 3 señales:

### 1. Growth (50% del score)
```
growth_7_vs_30 = avg(últimos 7 días) / avg(últimos 30 días)
```
- > 1.1: Crecimiento positivo
- 0.9-1.1: Estable
- < 0.9: Decrecimiento

### 2. Slope (30% del score)
```
slope_14d = pendiente de regresión lineal (últimos 14 días)
```
- > 0: Tendencia ascendente
- ≈ 0: Tendencia plana
- < 0: Tendencia descendente

### 3. Recent Peak (20% del score)
```
recent_peak_30d = max(últimos 30 días) / 100
```
- > 0.8: Interés alto
- 0.5-0.8: Interés moderado
- < 0.5: Interés bajo

**Fórmula final:**
```
score = 100 * clamp(0.5*norm(growth) + 0.3*norm(slope) + 0.2*peak, 0, 1)
```

## 🗂️ Estructura del Proyecto

```
.
├── src/
│   ├── app.js                      # Configuración Express
│   ├── server.js                   # Entry point
│   ├── routes/
│   │   ├── trends.routes.js        # Rutas de tendencias
│   │   ├── health.routes.js        # Health check
│   │   └── countries.routes.js     # Países soportados
│   ├── controllers/
│   │   └── trends.controller.js    # Controlador principal
│   ├── services/
│   │   ├── trendEngine.service.js  # Orquestador principal
│   │   └── scoring.service.js      # Cálculo de score
│   ├── connectors/
│   │   └── googleTrends.connector.js # Google Trends API
│   ├── middleware/
│   │   ├── validate.middleware.js  # Validación Zod
│   │   ├── error.middleware.js     # Error handling
│   │   └── requestId.middleware.js # Request tracking
│   ├── schemas/
│   │   └── trend.schema.js         # Schemas de validación
│   ├── db/
│   │   └── prismaClient.js         # Cliente Prisma
│   ├── cache/
│   │   └── redisClient.js          # Cliente Redis
│   └── utils/
│       ├── logger.js               # Logger Pino
│       ├── dates.js                # Helpers de fechas
│       ├── normalize.js            # Normalización de datos
│       └── regionMap.js            # Mapeo de países (legacy name)
├── prisma/
│   └── schema.prisma               # Esquema de base de datos
├── package.json
└── README.md
```

## 🔧 Scripts Disponibles

```bash
# Desarrollo (con hot reload)
npm run dev

# Producción
npm start

# Base de datos
npm run db:generate     # Generar cliente Prisma
npm run db:migrate      # Ejecutar migraciones
npm run db:studio       # Abrir Prisma Studio (GUI)
npm run db:reset        # Reset completo de DB

# Cache Redis
npm run cache:clear     # Limpiar todo el cache
npm run cache:keys      # Ver primeras 20 keys en cache

# Tests
npm test                # Ejecutar todos los tests (138 tests)
npm run test:watch      # Tests en modo watch
npm run test:coverage   # Tests con coverage report
```

## 🔒 Validación y Rate Limiting

### Validaciones

- **keyword**: 2-60 caracteres
- **country**: Código ISO 3166-1 alpha-2 (MX, CR, ES)
- **window_days**: Solo valores permitidos: 7, 30, 90, 365
- **baseline_days**: 30-1825 días (hasta 5 años)
- **Límite total**: `window_days + baseline_days ≤ 1825` (5 años máximo)

### Rate Limiting

- **Default**: 60 requests por minuto por IP
- **Configurable** via `RATE_LIMIT_MAX_REQUESTS` en `.env`
- **Response 429** cuando se excede el límite

## 🐛 Debugging

### Ver logs estructurados

Los logs incluyen `requestId` para rastreo completo:

```json
{
  "level": "info",
  "time": "2026-01-10T12:00:00.000Z",
  "requestId": "550e8400-e29b-41d4-a716-446655440000",
  "msg": "Processing trend query request"
}
```

### Inspeccionar base de datos

```bash
npm run db:studio
```

Abre en `http://localhost:5555`

### Verificar cache Redis

```bash
# Ver keys en cache
npm run cache:keys

# O directamente con redis-cli
redis-cli
> KEYS trend:v4:*
> GET "trend:v4:bitcoin:MX:30:365"
> TTL "trend:v4:bitcoin:MX:30:365"

# Limpiar cache
npm run cache:clear
```

## ⚠️ Manejo de Errores

La API devuelve errores consistentes:

```json
{
  "error": "Validation failed",
  "details": [
    {
      "field": "country",
      "message": "Country \"XX\" is not supported. Supported: MX, CR, ES"
    }
  ],
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Códigos de estado:**
- `400`: Validación fallida
- `404`: Keyword sin datos disponibles
- `429`: Rate limit excedido
- `500`: Error interno del servidor
- `503`: Servicio degradado (DB o Redis caído)

## 🚦 Próximos Pasos (Post-MVP 1)

- [ ] TikTokPublicConnector
- [ ] YouTubeConnector
- [ ] InstagramLimitedConnector
- [ ] Job Queue (Celery/BullMQ)
- [ ] Autenticación OAuth
- [ ] Multi-keyword batch queries
- [ ] Webhooks para queries async

## 📝 Notas Técnicas

### Cache Strategy

- **Key format**: `trend:v4:{keyword}:{country}:{window}:{baseline}` (con versioning)
- **TTL**: 24 horas (86400s)
- **Stale TTL**: 48 horas (172800s) para fallback
- **Cache miss**: Fetch from Google Trends → Score → Persist → Cache → Return
- **Versioning**: v4 previene conflictos en actualizaciones

### Database

- **Postgres 16**: Relacional robusto
- **Prisma ORM**: Type-safe queries
- **Índices optimizados**: Para lookups de cache y queries por país/keyword

### Google Trends Connector

- **Max retries**: 3 intentos con exponential backoff (5s → 10s → 20s)
- **Request delay**: 4 segundos entre requests
- **Concurrency**: Solo 1 request simultáneo (lock con cola)
- **Retryable errors**: ECONNRESET, ETIMEDOUT, 429, 503, 504, HTML responses
- **Country comparison**: Single global query filtrado para MX, CR, ES (evita rate limiting)
- **Supported countries**: México (MX), Costa Rica (CR), España (ES)
- **Historical limit**: Hasta 1825 días (5 años) de datos históricos

## 📄 Licencia

MIT

---

**Desarrollado para análisis de tendencias multi-fuente** 🚀
