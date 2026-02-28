# 📦 Modelo de Datos - MongoDB

Este proyecto utiliza varias colecciones en MongoDB para almacenar los resultados de las consultas de tendencias, YouTube y AliExpress, así como los datos fusionados. A continuación se explica cada colección y sus campos principales.

---

## 1. `fusion_requests`
Almacena la petición principal de fusión y el resultado combinado.

- **request_id**: ID único de la petición.
- **generated_at**: Fecha y hora de generación.
- **keyword**: Palabra clave consultada.
- **country**: País de la consulta.
- **region**: Región utilizada (igual a country).
- **language**: Idioma de la consulta.
- **aliexpress_query**: Parámetros usados para AliExpress.
- **fusion**: Métricas combinadas (score, recomendación, pesos).
- **sources_used**: Fuentes utilizadas (Google Trends, YouTube, AliExpress).

---

## 2. `aliexpress_competitors`
Almacena los productos competidores obtenidos de AliExpress.

- **request_id**: ID de la petición de fusión.
- **generated_at**: Fecha de generación.
- **product_id**: ID del producto.
- **title**: Título del producto.
- **pricing**: Precios y descuentos.
- **metrics**: Métricas de ventas y evaluación.
- **category**: Información de categoría.
- **shop**: Información de la tienda.
- **url**: URL del producto.

---

## 3. `aliexpress_request_meta`
Meta-información sobre la consulta a AliExpress.

- **request_id**: ID de la petición.
- **competitors_count**: Número de competidores encontrados.

---

## 4. `trends_series`
Serie temporal de valores de tendencia.

- **request_id**: ID de la petición.
- **date**: Fecha del punto de la serie.
- **value**: Valor de tendencia.

---

## 5. `trends_summary`
Resumen de la consulta a Google Trends.

- **request_id**: ID de la petición.
- **series_count**: Número de puntos en la serie.
- **trend_score**: Score agregado de tendencias.
- **signals**: Señales calculadas (crecimiento, picos, etc.).
- **sources_used**: Fuentes utilizadas.
- **by_country**: Detalle por país.

---

## 6. `youtube_videos`
Videos analizados de YouTube.

- **request_id**: ID de la petición.
- **video_id**: ID del video.
- **title**: Título del video.
- **channel_title**: Canal del video.
- **published_at**: Fecha de publicación.
- **views**: Número de vistas.
- **likes**: Número de likes.
- **comments**: Número de comentarios.
- **engagement_rate**: Tasa de engagement.
- **freshness**: Métrica de frescura.
- **video_intent**: Score de intención.
- **query_used**: Query utilizada.
- **url**: URL del video.

---

## 7. `youtube_summary`
Resumen de la consulta a YouTube.

- **request_id**: ID de la petición.
- **query_used**: Query utilizada.
- **videos_analyzed**: Número de videos analizados.
- **total_views**: Vistas totales.
- **intent_score**: Score agregado de intención.

---

## 🔗 Relación entre colecciones

Todas las colecciones están relacionadas por el campo **request_id**, que permite rastrear todos los datos generados a partir de una misma consulta de fusión.

---

## 📝 Notas

- Los tipos de datos (string, int, double, date, etc.) están definidos para facilitar análisis y visualización.
- El modelo está optimizado para consultas analíticas y trazabilidad de cada request.
- La inserción en MongoDB se realiza automáticamente desde el endpoint de fusión.

