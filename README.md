# Trends API - Python/Flask

Migración completa del proyecto de Node.js/Express a Python/Flask.

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

Copiar `.env.example` a `.env` y ajustar valores (DATABASE_URL, REDIS_URL, etc.)

### 4. Iniciar servicios necesarios

```bash
# PostgreSQL y Redis deben estar corriendo
docker-compose up -d  # Si usas Docker
# o iniciarlos manualmente
```

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

- `GET /health` - Health check
- `POST /v1/trends/query` - Query Google Trends
- `GET /v1/regions` - List supported regions
- `POST /dev/mock-trends` - Mock data (dev only)

## 🔧 Estructura del Proyecto

```
master/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── config.py            # Configuration
│   ├── connectors/          # Google Trends connector
│   ├── models/              # SQLAlchemy models
│   ├── routes/              # Flask blueprints
│   ├── services/            # Business logic
│   ├── utils/               # Utilities (logger, dates, redis)
│   └── middleware/          # Middleware
├── tests/                   # Pytest tests
├── server.py                # Entry point
├── requirements.txt         # Python dependencies
└── .env                     # Environment variables
```

## 🆚 Diferencias con Node.js

| Node.js | Python |
|---------|--------|
| Express | Flask |
| Prisma | SQLAlchemy |
| Jest | pytest |
| google-trends-api | pytrends |
| pino | loguru |
| npm | pip |

## ✅ Ventajas de Python/Flask

- **pytrends** es más estable que google-trends-api
- Mejor para data science/ML
- Código más limpio y conciso
- Mejor integración con pandas/numpy

## 📝 Notas

- El sistema de mocks se mantiene igual (NODE_ENV=test)
- La configuración anti-bloqueo de Google Trends está implementada
- La base de datos PostgreSQL usa el mismo schema
- Redis se usa para caché igual que antes

## 🔗 Recursos

- [Flask Documentation](https://flask.palletsprojects.com/)
- [pytrends Documentation](https://pypi.org/project/pytrends/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [pytest Documentation](https://docs.pytest.org/)
