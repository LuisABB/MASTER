# Trends API - Python/Flask

Migración completa del proyecto de Node.js/Express a Python/Flask.

## 📦 Versiones

- **Python**: 3.10+
- **Flask**: 3.0.0
- **Redis**: 5.0.1
- **pytrends**: 4.9.2
- **requests**: 2.31.0
- **loguru**: 0.7.2
- **pytest**: 7.4.3

## 🚀 Instalación

### 1. Crear entorno virtual

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# o en Windows: venv\Scripts\activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Copiar `.env.example` a `.env` y ajustar valores:
- `YOUTUBE_API_KEY` - API Key de YouTube Data API v3 (opcional, para funcionalidad YouTube)
- `ALIEXPRESS_APP_KEY` - AppKey de AliExpress Affiliate API
- `ALIEXPRESS_APP_SECRET` - App Secret de AliExpress Affiliate API
- `ALIEXPRESS_TRACKING_ID` - Tracking ID (opcional)
- `CATEGORY_RESOLUTION_MODE` - `none|api|hybrid` (default: `none`). `api` usa `affiliate.category.get` para `category_name/path`.

### 4. Iniciar Redis

```bash
# Linux/Mac
sudo apt install redis-server  # Ubuntu/Debian
brew install redis              # Mac
sudo systemctl start redis      # Linux
brew services start redis       # Mac

# Verificar que funciona
redis-cli ping  # Debe responder: PONG
```

#### Activar Redis en Linux (Ubuntu/Pop!_OS/Debian)

```bash
# Instalar
sudo apt update
sudo apt install redis-server

# Activar al inicio del sistema
sudo systemctl enable redis-server

# Iniciar el servicio
sudo systemctl start redis-server

# Ver estado
systemctl status redis-server

# Probar conexión
redis-cli ping  # Debe responder: PONG
```

#### Activar Redis en Windows
- Instalar desde: https://github.com/tporadowski/redis/releases
- Ejecutar `redis-server.exe` y luego `redis-cli.exe ping`.

#### Notas útiles

- El servicio escucha por defecto en `127.0.0.1:6379`.
- Configuración: `/etc/redis/redis.conf`.
- Si el puerto cambia, actualiza `REDIS_URL` en `.env`.

## 🏃 Ejecutar

### Modo desarrollo

```bash
source venv/bin/activate
python server.py
```

### Modo producción (con Gunicorn)

```bash
source venv/bin/activate
gunicorn -w 4 -b 0.0.0.0:3000 "app:create_app()"
```

## 🧪 Tests

```bash
source venv/bin/activate
NODE_ENV=test pytest
```

### Con coverage

```bash
NODE_ENV=test pytest --cov=app --cov-report=html
```

## 📚 Endpoints

### Google Trends
- `POST /v1/trends/query` - Query Google Trends data
  ```json
  {
    "keyword": "maletas",
    "country": "MX",
    "window_days": 30
  }
  ```

### YouTube
- `POST /v1/sources/youtube/query` - Query YouTube videos and calculate intent scores
  ```json
  {
    "keyword": "maletas",
    "country": "MX",
    "lang": "es",
    "window_days": 30,
    "maxResults": 25
  }
  ```

### Insights Fusion
- `POST /v1/insights/fusion/query` - Combined insights from Google Trends + YouTube + AliExpress
  ```json
  {
    "keyword": "zapatillas",
    "country": "CR",
    "window_days": 30,
    "lang": "es",
    "maxResults": 25,
    "target_currency": "MXN",
    "page": 1,
    "page_size": 10
  }
  ```

### AliExpress Affiliate (Portals)
- `POST /aliexpress/search` - Query AliExpress Affiliate products
  ```json
  {
    "keywords": "phone",
    "ship_to_country": "MX",
    "target_currency": "MXN",
    "target_language": "ES",
    "page": 1,
    "page_size": 10
  }
  ```

### Utilities
- `GET /health` - Health check
- `GET /v1/regions` - List supported regions

### Development Only
- `POST /dev/mock-trends` - Mock trends data
- `POST /dev/clear-cache` - Clear Redis cache  
- `GET /dev/cache-info` - View cache info

## 🔧 Estructura del Proyecto

```
master/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── connectors/
│   │   ├── google_trends_connector.py
│   │   ├── youtube_connector.py
│   │   └── aliexpress_connector.py
│   ├── routes/
│   │   ├── trends_routes.py
│   │   ├── youtube_routes.py
│   │   ├── fusion_routes.py
│   │   ├── aliexpress_routes.py
│   │   └── dev_routes.py
│   ├── services/
│   │   ├── trend_engine_service.py
│   │   ├── youtube_intent_service.py
│   │   └── scoring_service.py
│   ├── utils/
│   │   ├── logger.py
│   │   ├── dates.py
│   │   ├── redis_client.py
│   │   └── mongodb_fusion_insert.py
│   └── middleware/
├── results/
│   ├── trends_data.csv
│   ├── youtube_data.csv
│   ├── fusion_data.csv
│   └── aliexpress_data.csv
├── tests/
├── server.py
├── requirements.txt
└── .env
```

## 📝 Notas

- El sistema de mocks se mantiene igual (NODE_ENV=test)
- La configuración anti-bloqueo de Google Trends está implementada
**Inserción automática en MongoDB** - Cada request a `/v1/insights/fusion/query` inserta el JSON completo en la base de datos MongoDB (`ecommerce_metrics`) usando la función avanzada. No es necesario cargar archivos manualmente, los datos se almacenan directamente desde el endpoint.
Redis se usa para caché con TTL de 24 horas
**Genera CSV automáticamente**:
  - `results/trends_data.csv` - Datos de Google Trends
  - `results/youtube_data.csv` - Datos de YouTube
  - `results/fusion_data.csv` - Datos combinados con score de fusión (incluye AliExpress)
  - `results/aliexpress_data.csv` - Datos de AliExpress Affiliate

## 🗄️ MongoDB: Inserción automática

Cada vez que se consulta `/v1/insights/fusion/query`, el JSON de respuesta se inserta automáticamente en la base de datos MongoDB (`ecommerce_metrics`).

Las colecciones avanzadas incluyen:
- `fusion_requests`
- `aliexpress_competitors`
- `aliexpress_request_meta`
- `trends_series`
- `trends_summary`
- `youtube_videos`
- `youtube_summary`

No es necesario cargar archivos .json manualmente, la inserción se realiza directamente desde el endpoint Flask usando la función `insertar_fusion_json_en_mongodb`.

Notas de AliExpress CSV:
- Incluye `category_name`, `category_path`, `macro_category`, `macro_path` y `category_resolution_confidence` cuando `CATEGORY_RESOLUTION_MODE=api`.

## 🧾 CSVs generados (Fusion)

Cada request a `/v1/insights/fusion/query` crea 3 CSV separados con timestamp. Columnas y significado:

## 📖 Consulta el modelo de datos

Para ver la explicación completa del modelo de datos en MongoDB, revisa el archivo [MODELO_MONGODB.md](MODELO_MONGODB.md).

## 🔗 Recursos

- [Flask Documentation](https://flask.palletsprojects.com/)
- [pytrends Documentation](https://pypi.org/project/pytrends/)
- [Redis Documentation](https://redis.io/docs/)
- [pytest Documentation](https://docs.pytest.org/)
- [YouTube Data API v3](https://developers.google.com/youtube/v3)

## 📋 Changelog

### v2.1.0 (2026-02-21)

**Breaking Changes:**
- ✅ `region` ya no se recibe en Fusion (YouTube usa `country`)
- ✅ `ship_to_country` ya no se recibe en Fusion (AliExpress usa `country`)
- ✅ `target_language` ya no se recibe en Fusion (usa `lang`)
- ✅ `baseline_days` ya no se recibe en Trends/Fusion (usa `window_days`)

**Mejoras:**
- ✨ CSVs de Fusion ahora son 3 archivos separados con timestamp

### v2.0.0 (2026-01-31)

**Breaking Changes:**
- ✅ Eliminada base de datos PostgreSQL/SQLAlchemy completamente
- ✅ Parámetro `region` renombrado a `country` en todos los endpoints
- ✅ Sistema basado 100% en Redis para caché

**Nuevas Funcionalidades:**
- ✨ YouTube Data API v3 integrado (`/v1/sources/youtube/query`)
- ✨ Endpoint de fusión Google Trends + YouTube (`/v1/insights/fusion/query`)
- ✨ Cálculo de intent scores para videos de YouTube:
  - `engagement_rate` = (likes + 2*comments) / views
  - `freshness` = exp(-days / half_life)
  - `video_intent` = log10(views+1) * engagement * freshness
- ✨ Generación automática de 3 archivos CSV:
  - `results/trends_data.csv` - Datos de Google Trends
  - `results/youtube_data.csv` - Datos de YouTube con métricas
  - `results/fusion_data.csv` - Fusión ponderada (70% Trends + 30% YouTube)
- ✨ CSV en modo append - acumulación de datos entre requests

**Mejoras:**
- 🔧 Anti-bloqueo Google Trends mejorado:
  - Rotación de 5 User Agents diferentes
  - Delays aleatorios (1-3s inicial, 8-12s entre requests)
  - Exponential backoff (5 reintentos, 10-15s delay)
- 🔧 Optimización de queries YouTube:
  - Cambio de queries con templates a keywords directos
  - Mejor aprovechamiento del algoritmo de relevancia de YouTube
- 🔧 Límites de tiempo configurables:
  - Google Trends: hasta 5 años (1825 días)
  - YouTube: máximo 365 días (limitación API)
- 🔧 Logging detallado con emojis para debugging

**Correcciones:**
- 🐛 Fixed: CSV no guardaba datos cuando YouTube retornaba 0 videos
- 🐛 Fixed: Queries muy específicas fallaban en YouTube
- 🐛 Fixed: HTTP 429 errors por exceso de requests a Google Trends
- 🐛 Fixed: Parámetro `country` vs `region` inconsistente

### v1.0.0 (2025-12-XX)
- 🎉 Migración inicial de Node.js/Express a Python/Flask
- ✅ Google Trends API con pytrends
- ✅ Redis para caché (24h TTL)
- ✅ Sistema de mocks para testing