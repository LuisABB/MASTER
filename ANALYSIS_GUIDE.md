# 📊 Guía de Análisis de Tendencias

Esta guía te ayudará a interpretar los resultados de la API de Trends y tomar decisiones basadas en datos.

---

## 📑 Tabla de Contenidos

1. [Anatomía de una Respuesta](#anatomía-de-una-respuesta)
2. [Trend Score: La Métrica Clave](#trend-score-la-métrica-clave)
3. [Las 3 Señales de Tendencia](#las-3-señales-de-tendencia)
4. [Interpretando Series Temporales](#interpretando-series-temporales)
5. [Análisis por País](#análisis-por-país)
6. [Casos de Uso Reales](#casos-de-uso-reales)
7. [Mejores Prácticas](#mejores-prácticas)

---

## Anatomía de una Respuesta

Cuando consultas la API con:

```bash
POST /v1/trends/query
{
  "keyword": "bitcoin",
  "country": "MX",
  "window_days": 30
}
```

Obtienes una respuesta estructurada en **7 secciones clave**:

```json
{
  // 1. METADATA
  "keyword": "bitcoin",
  "country": "MX",
  "window_days": 30,
  "generated_at": "2026-01-11T05:05:00.161Z",
  "sources_used": ["mock_data"],
  
  // 2. SCORE PRINCIPAL
  "trend_score": 34.95,
  
  // 3. SEÑALES TÉCNICAS
  "signals": {
    "growth_7_vs_30": 0.91,
    "slope_14d": -0.0107,
    "recent_peak_30d": 0.48
  },
  
  // 4. SERIE TEMPORAL (366 días)
  "series": [...],
  
  // 5. COMPARACIÓN INTERNACIONAL
  "by_country": [...],
  
  // 6. EXPLICACIÓN EN LENGUAJE NATURAL
  "explain": [...],
  
  // 7. CACHE INFO
  "cache": {
    "hit": false,
    "ttl_seconds": 21600
  }
}
```

---

## Trend Score: La Métrica Clave

### ¿Qué es el Trend Score?

Un **índice de 0 a 100** que resume qué tan "caliente" está una tendencia en este momento.

### Escala de Interpretación

| Rango | Categoría | Significado | Acción Recomendada |
|-------|-----------|-------------|-------------------|
| **80-100** | 🔥 **Muy Fuerte** | Tendencia explosiva, crecimiento acelerado | ✅ Invertir recursos YA |
| **60-79** | 📈 **Positiva** | Crecimiento sostenido, momento favorable | ✅ Oportunidad clara |
| **40-59** | ⚖️ **Moderada** | Estabilidad, sin dirección clara | ⚠️ Monitorear de cerca |
| **20-39** | 📉 **Débil** | Decrecimiento o bajo interés | ❌ Evitar o replantear |
| **0-19** | ❄️ **Muy Baja** | Tendencia muerta o en caída libre | ❌ No invertir |

### Ejemplo Real

```json
{
  "keyword": "bitcoin",
  "trend_score": 34.95
}
```

**Interpretación:**
- ❌ **No es buen momento** para contenido de Bitcoin
- Está en la zona **débil/decreciente**
- Mejor esperar a que suba a 60+ o buscar otro tema

---

## Las 3 Señales de Tendencia

El `trend_score` se calcula con **3 señales técnicas**:

```
trend_score = (growth_7_vs_30 × 50%) + (slope_14d × 30%) + (recent_peak_30d × 20%)
```

### 1️⃣ Growth 7 vs 30 (Peso: 50%)

**¿Qué mide?** Momentum reciente = promedio últimos 7 días ÷ promedio últimos 30 días

```json
"growth_7_vs_30": 0.91
```

| Valor | Interpretación | Significado |
|-------|---------------|-------------|
| **> 1.5** | 🚀 Explosión viral | Interés se duplicó en última semana |
| **1.2 - 1.5** | 📈 Crecimiento fuerte | +20-50% de aumento |
| **1.0 - 1.2** | ↗️ Crecimiento suave | +0-20% de aumento |
| **0.8 - 1.0** | ⚖️ Estabilidad | ±20% de variación |
| **< 0.8** | 📉 Desaceleración | Cayendo >20% |

**Ejemplo:**
```json
"growth_7_vs_30": 0.91  // -9% última semana
```
→ El interés está **bajando ligeramente** en los últimos 7 días.

---

### 2️⃣ Slope 14d (Peso: 30%)

**¿Qué mide?** Dirección de la tendencia = pendiente de regresión lineal de últimos 14 días

```json
"slope_14d": -0.0107
```

| Valor | Interpretación | Significado |
|-------|---------------|-------------|
| **> 0.1** | ⬆️ Tendencia ascendente fuerte | Subiendo rápido |
| **0 - 0.1** | ↗️ Tendencia ascendente suave | Subiendo lentamente |
| **-0.1 - 0** | ↘️ Tendencia descendente suave | Bajando lentamente |
| **< -0.1** | ⬇️ Tendencia descendente fuerte | Cayendo rápido |

**Ejemplo:**
```json
"slope_14d": -0.0107  // Pendiente negativa pequeña
```
→ La tendencia está en **leve caída** las últimas 2 semanas.

---

### 3️⃣ Recent Peak 30d (Peso: 20%)

**¿Qué mide?** Intensidad máxima = valor máximo de últimos 30 días (normalizado 0-1)

```json
"recent_peak_30d": 0.48
```

| Valor | Interpretación | Significado |
|-------|---------------|-------------|
| **> 0.8** | 🔥 Pico muy alto | Cerca del máximo histórico |
| **0.5 - 0.8** | 📊 Pico moderado | Interés medio-alto |
| **< 0.5** | 📉 Pico bajo | Lejos de su potencial |

**Ejemplo:**
```json
"recent_peak_30d": 0.48  // 48/100
```
→ El interés está en **niveles bajos**, solo alcanzó 48% de su capacidad.

---

## Interpretando Series Temporales

### Estructura de los Datos

```json
"series": [
  { "date": "2025-01-11", "value": 39 },
  { "date": "2025-01-12", "value": 40 },
  ...
  { "date": "2026-01-11", "value": 38 }
]
```

- **Total:** `window_days + 1` puntos (baseline igual a window)
- **Valores:** 0-100 (interés relativo normalizado)
- **Orden:** Cronológico ascendente

### Patrones Comunes

#### 🔥 **Tendencia Explosiva** (Score: 80-100)
```
  100 ████████████
   80 ████████
   60 ████
   40 ██
   20 █
    0 ─────────────────────────────
      <─ baseline ─><─ window ─>
```
**Características:**
- Crecimiento acelerado en últimos días
- Pico reciente > 80
- Pendiente positiva pronunciada

---

#### 📈 **Tendencia Positiva** (Score: 60-79)
```
   80     ████████
   60   ██████
   40 ████
   20 ██
    0 ─────────────────────────────
      <─ baseline ─><─ window ─>
```
**Características:**
- Crecimiento sostenido
- Sin caídas bruscas
- Pendiente positiva estable

---

#### 📉 **Tendencia Decreciente** (Score: 20-39)
```
   80 ████
   60   ██
   40     ████
   20       ██████
    0 ─────────────────────────────
      <─ baseline ─><─ window ─>
```
**Características:**
- Pico en el pasado
- Caída sostenida
- Pendiente negativa

---

#### ⚖️ **Tendencia Estable** (Score: 40-59)
```
   60 ████████████████
   40 ████████████████
   20 ████████████████
    0 ─────────────────────────────
      <─ baseline ─><─ window ─>
```
**Características:**
- Sin variaciones significativas
- Plateau
- Pendiente cercana a 0

---

## Análisis por País

### Estructura de Datos

```json
"by_country": [
  { "country": "MX", "value": 100 },
  { "country": "CR", "value": 78 },
  { "country": "ES", "value": 65 }
]
```

- **3 países** ordenados por interés descendente
- **Valores 0-100** (relativo al país con más interés)
- **Códigos ISO 3166-1 alpha-2** para países

### Códigos de País

| Código | País |
|--------|------|
| MX | México |
| CR | Costa Rica |
| ES | España |

### Cómo Interpretar

#### Dominancia de un País
```json
"by_country": [
  { "country": "MX", "value": 100 },  // Dominante
  { "country": "CR", "value": 45 },   // Medio
  { "country": "ES", "value": 22 }    // Bajo
]
```
**Interpretación:**
- **Diferencia MX-ES: 78 puntos** → México domina el interés
- Focus en México para máximo ROI
- España muestra poco interés comparativamente

---

#### Distribución Balanceada
```json
"by_country": [
  { "country": "MX", "value": 100 },
  { "country": "ES", "value": 95 },
  { "country": "CR", "value": 88 }
]
```
**Interpretación:**
- **Diferencia mínima** → Interés internacional equilibrado
- Estrategia multi-país viable
- No necesitas geo-targeting agresivo

---

## Casos de Uso Reales

### 🎯 Caso 1: Creador de Contenido

**Objetivo:** Decidir sobre qué crear contenido esta semana

**Consulta:**
```bash
POST /v1/trends/query
{
  "keyword": "inteligencia artificial",
  "country": "MX",
  "window_days": 7
}
```

**Respuesta:**
```json
{
  "trend_score": 78.5,
  "signals": {
    "growth_7_vs_30": 1.35,
    "slope_14d": 0.12,
    "recent_peak_30d": 0.85
  }
}
```

**Decisión:**
- ✅ **Score 78.5** → Tendencia positiva
- ✅ **Growth 1.35** → +35% última semana (momentum fuerte)
- ✅ **Slope 0.12** → Tendencia ascendente
- ✅ **Peak 0.85** → Interés alto

**Acción:** ✅ **CREAR CONTENIDO YA** sobre IA. Alto potencial de engagement.

---

### 📱 Caso 2: Marketing de Producto

**Objetivo:** Elegir el mejor país para lanzar campaña

**Consultas:**
```bash
# Opción A: México
POST /v1/trends/query {"keyword": "tenis running", "country": "MX"}

# Opción B: Costa Rica
POST /v1/trends/query {"keyword": "tenis running", "country": "CR"}

# Opción C: España
POST /v1/trends/query {"keyword": "tenis running", "country": "ES"}
```

**Resultados:**
```json
// México
{ "trend_score": 45, "by_country": [{"country": "MX", "value": 88}] }

// Costa Rica
{ "trend_score": 52, "by_country": [{"country": "CR", "value": 71}] }

// España
{ "trend_score": 68, "by_country": [{"country": "ES", "value": 95}] }
```

**Decisión:**
- ❌ México: Score 45, interés alto pero **decreciendo**
- ⚠️ Costa Rica: Score 52, interés medio
- ✅ **España: Score 68, interés MUY alto y creciendo**

**Acción:** ✅ Lanzar campaña en **España primero**, luego expandir a México.

---

### 📊 Caso 3: Análisis Competitivo

**Objetivo:** Comparar tu marca vs competencia

**Consultas:**
```bash
POST /v1/trends/query {"keyword": "mi marca"}
POST /v1/trends/query {"keyword": "competidor A"}
POST /v1/trends/query {"keyword": "competidor B"}
```

**Resultados:**
```json
// Mi marca
{ "trend_score": 42, "signals": {"growth_7_vs_30": 0.88} }

// Competidor A
{ "trend_score": 71, "signals": {"growth_7_vs_30": 1.45} }

// Competidor B
{ "trend_score": 38, "signals": {"growth_7_vs_30": 0.75} }
```

**Interpretación:**
- 📈 Competidor A está **arrasando** (+45% última semana)
- ⚖️ Tu marca está **estable/leve caída** (-12%)
- 📉 Competidor B está **perdiendo** (-25%)

**Acción:**
- Investigar qué está haciendo Competidor A
- Aprovechar la caída de Competidor B
- Mejorar tu estrategia de visibilidad

---

### 🔍 Caso 4: Detección de Tendencias Emergentes

**Objetivo:** Encontrar el próximo tema viral

**Estrategia:** Buscar keywords con:
- `trend_score > 70` (fuerte)
- `growth_7_vs_30 > 1.3` (+30% reciente)
- `slope_14d > 0.08` (ascendente)

**Consulta múltiple:**
```bash
for keyword in "chatgpt" "stable diffusion" "midjourney"; do
  curl -X POST http://localhost:3000/v1/trends/query \
    -d "{\"keyword\": \"$keyword\"}"
done
```

**Resultados:**
```json
// ChatGPT
{ "trend_score": 65, "growth_7_vs_30": 1.15 }  // ⚠️ Pasando

// Stable Diffusion
{ "trend_score": 48, "growth_7_vs_30": 0.92 }  // ❌ Decayendo

// Midjourney
{ "trend_score": 82, "growth_7_vs_30": 1.55 }  // ✅ EXPLOSIÓN
```

**Decisión:** ✅ **"Midjourney"** es la tendencia emergente. Crear contenido YA.

---

## Mejores Prácticas

### 1. ⏰ Timing de Consultas

```bash
# ❌ MAL: Consultar cada minuto
while true; do
  curl POST /v1/trends/query -d '{"keyword": "bitcoin"}'
  sleep 60
done

# ✅ BIEN: Consultar cada 6 horas (respeta el cache)
curl POST /v1/trends/query -d '{"keyword": "bitcoin"}'
# Esperar 6 horas (TTL del cache)
```

**Por qué:**
- Cache TTL = 6 horas
- Google Trends se actualiza cada ~4 horas
- Consultas frecuentes no dan nuevos datos

---

### 2. 📅 Selección de Ventanas

```bash
# Para NOTICIAS/VIRAL
{
  "window_days": 7       # Última semana
}

# Para SEASONAL/TENDENCIAS LARGAS
{
  "window_days": 30      # Último mes
}

# Para ANÁLISIS HISTÓRICO
{
  "window_days": 90      # Últimos 3 meses
}
```

---

### 3. 🎯 Interpretación de Contexto

**No solo mires el score, analiza el contexto:**

```json
{
  "keyword": "navidad",
  "trend_score": 25,
  "signals": {"growth_7_vs_30": 0.65}
}
```

**Fecha de consulta:** 15 de enero

**Interpretación:**
- ❌ **NO significa** que "navidad" es mala keyword
- ✅ **SIGNIFICA** que es temporada baja (post-diciembre)
- 🔮 **PROYECCIÓN:** Volverá a 90+ en noviembre

**Acción correcta:**
- Programar contenido para octubre-noviembre
- No crear contenido ahora

---

### 4. 🔄 Monitoreo Continuo

```bash
# Crear dashboard de seguimiento
POST /v1/trends/query {"keyword": "mi_tema", ...}

# Guardar histórico cada 6 horas
{
  "2026-01-10 00:00": 45,
  "2026-01-10 06:00": 47,
  "2026-01-10 12:00": 52,
  "2026-01-10 18:00": 58
}

# Detectar momentum
if (score_18h - score_00h) > 10:
  alert("🚀 Tendencia acelerando!")
```

---

### 5. 📊 Comparación Relativa

**No analices keywords en aislamiento:**

```bash
# ❌ MAL
POST /v1/trends/query {"keyword": "producto A"}
# Score: 55 → ¿Es bueno o malo? 🤷

# ✅ BIEN
POST /v1/trends/query {"keyword": "producto A"}  # Score: 55
POST /v1/trends/query {"keyword": "producto B"}  # Score: 72
POST /v1/trends/query {"keyword": "producto C"}  # Score: 38

# Ahora sí puedo decidir: B > A > C
```

---

### 6. 🗺️ Geo-Targeting Inteligente

**Usa `by_country` para optimizar presupuesto:**

```json
"by_country": [
  { "country": "MX", "value": 100 },  // 50% del presupuesto
  { "country": "ES", "value": 75 },   // 35% del presupuesto
  { "country": "CR", "value": 45 }    // 15% del presupuesto
]
```

**ROI esperado:**
- México: Alto volumen + alto interés = **ROI máximo**
- Costa Rica: Interés moderado = **ROI medio**
- Ajustar distribución según objetivos de mercado

---

## 🎓 Resumen Ejecutivo

### Checklist de Decisión

Antes de tomar acción, verifica:

```
✅ trend_score > 60     → Tendencia favorable
✅ growth_7_vs_30 > 1.0 → Momentum positivo
✅ slope_14d > 0        → Dirección ascendente
✅ recent_peak_30d > 0.6 → Interés alto
✅ Cache hit = false    → Datos frescos
```

**Si cumples 4/5:** ✅ **ADELANTE**  
**Si cumples 2-3/5:** ⚠️ **Monitorear**  
**Si cumples 0-1/5:** ❌ **Evitar**

---

### Métricas Clave por Objetivo

| Objetivo | Métrica Principal | Umbral | Acción |
|----------|------------------|--------|--------|
| **Contenido viral** | `growth_7_vs_30` | > 1.3 | Crear YA |
| **SEO largo plazo** | `slope_14d` | > 0.05 | Invertir |
| **Campaña internacional** | `by_country[0].value` | > 80 | Geo-target top país |
| **Detección emergente** | `trend_score` + `growth` | > 70 + 1.4 | First mover |
| **Evitar fracaso** | `trend_score` | < 40 | No invertir |

---

### Preguntas Frecuentes

**Q: ¿Por qué mi keyword tiene score bajo pero alta búsqueda en Google Ads?**  
A: Trend Score mide **cambio/momentum**, no volumen absoluto. Un término puede tener millones de búsquedas pero ser "aburrido" (sin crecimiento).

**Q: ¿Cuánto tarda en actualizarse el cache?**  
A: 6 horas (21600 segundos). Puedes verificar en `cache.ttl_seconds`.

**Q: ¿Qué significa `sources_used: ["mock_data"]`?**  
A: Estás usando datos simulados para testing. En producción será `["google_trends"]` o `["serpapi"]`.

**Q: ¿Puedo comparar países con una sola consulta?**  
A: Sí, cada consulta incluye comparación automática entre México (MX), Costa Rica (CR) y España (ES) en el campo `by_country`.

**Q: ¿Los valores de `series` son búsquedas totales?**  
A: No, son **interés relativo normalizado 0-100**. 100 = momento de máximo interés en el período analizado.

---

## 🚀 Próximos Pasos

1. Lee el [README.md](README.md) para setup básico
2. Usa esta guía para interpretar resultados
3. Experimenta con diferentes `window_days` (baseline se iguala automáticamente)
4. Crea tu propio dashboard de monitoreo
5. Automatiza la detección de tendencias emergentes

---

**¿Preguntas?** Abre un issue en el repositorio o consulta la documentación técnica.

**Versión:** MVP 1.0  
**Última actualización:** Enero 2026
