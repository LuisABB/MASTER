# Trends API - MVP 1 (Google Trends)

API multi-fuente para análisis de tendencias. MVP 1 implementa Google Trends con scoring automático, cache inteligente y persistencia.

## 🚀 Características

- ✅ **Google Trends Integration**: Datos temporales y regionales
- ✅ **Scoring Automático**: Algoritmo de 3 señales (growth, slope, peak)
- ✅ **Cache Inteligente**: Redis con TTL configurable (6-24h)
- ✅ **Persistencia**: PostgreSQL con historial completo
- ✅ **Rate Limiting**: Protección contra abuso
- ✅ **Observabilidad**: Logging estructurado con Pino
- ✅ **Validación robusta**: Zod schemas
- ✅ **Arquitectura escalable**: Listo para TikTok/IG/YouTube

## 📋 Requisitos

- Node.js >= 18.0.0
- PostgreSQL >= 14
- Redis >= 6.0
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

Ajusta las variables en `.env` si es necesario.

### 3. Asegurarse de que PostgreSQL y Redis estén corriendo

```bash
# Verificar PostgreSQL
sudo systemctl status postgresql

# Verificar Redis
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
  "keyword": "scooter",
  "region": "MX-CMX",
  "window_days": 90,
  "baseline_days": 365
}
```

**Response:**
```json
{
  "keyword": "scooter",
  "region": "MX-CMX",
  "window_days": 90,
  "baseline_days": 365,
  "generated_at": "2026-01-10T12:00:00Z",
  "sources_used": ["google_trends"],
  "trend_score": 72.6,
  "signals": {
    "growth_7_vs_30": 1.34,
    "slope_14d": 0.18,
    "recent_peak_30d": 0.92
  },
  "series": [
    { "date": "2025-10-15", "value": 21 },
    { "date": "2025-10-16", "value": 19 }
  ],
  "by_region": [
    { "region": "MX-CMX", "value": 100 },
    { "region": "MX-JAL", "value": 78 }
  ],
  "explain": [
    "El interés en los últimos 7 días creció 34% vs los últimos 30 días.",
    "La tendencia de los últimos 14 días es positiva (creciente).",
    "El interés reciente alcanzó 92% del máximo posible.",
    "Los datos corresponden a la región MX-CMX."
  ],
  "cache": {
    "hit": false,
    "ttl_seconds": 21600
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Listar Regiones Soportadas

```bash
GET /v1/regions
```

**Response:**
```json
{
  "count": 15,
  "regions": [
    { "code": "MX-CMX", "name": "Ciudad de México" },
    { "code": "MX-JAL", "name": "Jalisco" },
    { "code": "MX-NLE", "name": "Nuevo León" }
  ]
}
```

## 🧪 Ejemplos de Uso

### Con curl

```bash
# Consultar tendencia de "scooter" en CDMX
curl -X POST http://localhost:3000/v1/trends/query \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "scooter",
    "region": "MX-CMX",
    "window_days": 90,
    "baseline_days": 365
  }'

# Ver regiones soportadas
curl http://localhost:3000/v1/regions

# Health check
curl http://localhost:3000/health
```

### Con JavaScript/Fetch

```javascript
const response = await fetch('http://localhost:3000/v1/trends/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    keyword: 'scooter',
    region: 'MX-CMX',
    window_days: 90,
    baseline_days: 365
  })
});

const data = await response.json();
console.log(`Trend Score: ${data.trend_score}`);
console.log(`Explanations:`, data.explain);
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
│   │   └── regions.routes.js       # Regiones soportadas
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
│       └── regionMap.js            # Mapeo de regiones
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
```

## 🔒 Validación y Rate Limiting

### Validaciones

- **keyword**: 2-60 caracteres
- **region**: Debe estar en lista de regiones soportadas
- **window_days**: Solo valores permitidos: 7, 30, 90, 365
- **baseline_days**: Máximo 730 días (2 años), debe ser ≥ window_days

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
docker exec -it trends-redis redis-cli
> KEYS trend:*
> GET "trend:scooter:MX-CMX:90:365"
```

## ⚠️ Manejo de Errores

La API devuelve errores consistentes:

```json
{
  "error": "Validation failed",
  "details": [
    {
      "field": "region",
      "message": "Region \"MX-XXX\" is not supported"
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

- **Key format**: `trend:{keyword}:{region}:{window}:{baseline}`
- **TTL**: 6-24 horas (configurable)
- **Cache miss**: Fetch from Google Trends → Score → Persist → Cache → Return

### Database

- **Postgres 16**: Relacional robusto
- **Prisma ORM**: Type-safe queries
- **Índices optimizados**: Para lookups de cache y queries por región/keyword

### Google Trends Connector

- **Max retries**: 3 (configurable)
- **Retry delay**: 2 segundos con backoff
- **Retryable errors**: ECONNRESET, ETIMEDOUT, 429, 503, 504
- **Parallel fetches**: Time series + Regional data simultáneo

## 📄 Licencia

MIT

---

**Desarrollado para análisis de tendencias multi-fuente** 🚀
