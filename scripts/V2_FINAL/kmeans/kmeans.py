import pandas as pd
import numpy as np
import os
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.decomposition import PCA

# ===============================
# 1. Cargar dataset
# ===============================
local_path = 'dataset_validated.csv'
alt_path = '/mnt/data/dataset_validated.csv'
if os.path.exists(local_path):
    df = pd.read_csv(local_path)
elif os.path.exists(alt_path):
    df = pd.read_csv(alt_path)
else:
    raise FileNotFoundError(
        f"Dataset not found. Checked: {local_path!r} and {alt_path!r}"
    )

# Verificar columnas disponibles
print(df.columns)

# ===============================
# 2. Selección de variables para clustering
# ===============================
features = ['views', 'slope', 'rating', 'price', 'engagement']

# Map requested feature names to available dataset columns (with simple heuristics)
cols = list(df.columns)
def find_column(candidates):
    for c in candidates:
        if c in cols:
            return c
    # try substring match
    for c in candidates:
        for col in cols:
            if c.lower() in col.lower():
                return col
    return None

selected = {}
selected['views'] = find_column(['views', 'yt_total_views', 'total_views'])
selected['slope'] = find_column(['slope', 'trends_slope', 'trends_last_value'])
selected['rating'] = find_column(['rating', 'ali_avg_evaluate_rate'])
selected['price'] = find_column(['price', 'ali_avg_sale_price'])
# engagement: try to compute from youtube stats if available
if find_column(['engagement']):
    selected['engagement'] = find_column(['engagement'])
elif all(find_column(k) for k in ['yt_total_likes', 'yt_total_comments', 'yt_total_views']):
    # compute engagement = (likes + comments) / views
    likes_col = find_column(['yt_total_likes'])
    comments_col = find_column(['yt_total_comments'])
    views_col = find_column(['yt_total_views'])
    df['engagement'] = (df[likes_col].fillna(0) + df[comments_col].fillna(0)) / df[views_col].replace(0, np.nan)
    df['engagement'] = df['engagement'].fillna(0)
    selected['engagement'] = 'engagement'
else:
    # fallback: try any column with 'engag' in name
    selected['engagement'] = find_column(['engag', 'interaction'])

missing = [k for k,v in selected.items() if v is None]
if missing:
    raise KeyError(
        f"Missing required features in dataset: {missing}. Available columns: {cols}"
    )

X = df[[selected[f] for f in features]].copy()
X.columns = features

# ===============================
# 3. Imputación y normalización de datos
# ===============================
imputer = SimpleImputer(strategy='median')
X_imputed = pd.DataFrame(imputer.fit_transform(X), columns=X.columns, index=X.index)

# ===============================
# 4b. Tratar outliers / transformaciones (log para variables sesgadas)
# ===============================
# Apply log1p to skewed numeric features to reduce skew and the influence of outliers
for col in ['views', 'price']:
    if col in X_imputed.columns:
        # ensure numeric
        X_imputed[col] = pd.to_numeric(X_imputed[col], errors='coerce').fillna(0)
        X_imputed[col] = np.log1p(X_imputed[col])

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_imputed)

# ===============================
# 4. Encontrar número óptimo de clusters
# ===============================

range_n_clusters = range(2, 10)
silhouette_scores = []

for n_clusters in range_n_clusters:
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(X_scaled)
    score = silhouette_score(X_scaled, cluster_labels)
    silhouette_scores.append(score)

# Graficar Silhouette Score
plt.figure(figsize=(8,5))
plt.plot(range_n_clusters, silhouette_scores, marker='o')
plt.xlabel('Número de Clusters')
plt.ylabel('Silhouette Score')
plt.title('Selección de número óptimo de clusters')
plt.show()

# ===============================
# 5. Aplicar K-Means
# ===============================
# We computed silhouette scores above; for segmentation into 4 types choose n_clusters=4
n_clusters = 4
print(f"Usando número fijo de clusters: {n_clusters}")

kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=50)
df['cluster'] = kmeans.fit_predict(X_scaled)

# Build a features-only DataFrame (imputed & standardized column names) for analysis
df_features = X_imputed.copy()
df_features.columns = features
df_features['cluster'] = df['cluster'].values

# ===============================
# 6. Analizar clusters
# ===============================
cluster_summary = df_features.groupby('cluster')[features].mean()
cluster_summary['count'] = df_features['cluster'].value_counts().sort_index()
print(cluster_summary)

# ===============================
# 7. Visualización profesional
# ===============================
sns.pairplot(df_features, vars=features, hue='cluster', palette='tab10', diag_kind='kde')
plt.suptitle('Segmentación K-Means de Productos', y=1.02)
plt.show()

# ===============================
# PCA 2D para visualizar clusters
# ===============================
pca = PCA(n_components=2)
X_pca = pca.fit_transform(X_scaled)
plt.figure(figsize=(8,6))
sns.scatterplot(x=X_pca[:,0], y=X_pca[:,1], hue=df_features['cluster'], palette='tab10', legend='full')
plt.title('Clusters K-Means (PCA 2D)')
plt.xlabel('PC1')
plt.ylabel('PC2')
plt.show()

# ===============================
# 8. Guardar resultados
# ===============================
df.to_csv('dataset_clustered.csv', index=False)
print('Archivo guardado: dataset_clustered.csv')

# ===============================
# 9. Asignar nombres a clusters, proporciones y exportar para reportes
# ===============================
cluster_names = {0: 'viral/premium', 1: 'barato masivo', 2: 'muerto', 3: 'estable'}
df['cluster_name'] = df['cluster'].map(cluster_names)

print('\nPorcentaje por tipo de cluster:')
print(df['cluster_name'].value_counts(normalize=True) * 100)

# Export con nombres
df.to_csv('dataset_clustered_named.csv', index=False)
print('Archivo guardado: dataset_clustered_named.csv')

# Boxplots por cluster (price y rating) — usan las columnas originales cuando existen
price_col = selected.get('price')
rating_col = selected.get('rating')
if price_col in df.columns:
    plt.figure(figsize=(8,6))
    sns.boxplot(x='cluster_name', y=price_col, data=df)
    plt.title('Distribución de Price por Cluster')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('boxplot_price_by_cluster.png')
    plt.close()
    print('Boxplot guardado: boxplot_price_by_cluster.png')
else:
    print('No se encontró columna de price original para boxplot.')

if rating_col in df.columns:
    plt.figure(figsize=(8,6))
    sns.boxplot(x='cluster_name', y=rating_col, data=df)
    plt.title('Distribución de Rating por Cluster')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('boxplot_rating_by_cluster.png')
    plt.close()
    print('Boxplot guardado: boxplot_rating_by_cluster.png')
else:
    print('No se encontró columna de rating original para boxplot.')

# Optional: 3D interactive plot with Plotly (saved as HTML) if installed and columns available
try:
    import plotly.express as px
    plot_price_col = price_col if price_col in df.columns else None
    plot_eng_col = selected.get('engagement') if selected.get('engagement') in df.columns else None
    plot_views_col = selected.get('views') if selected.get('views') in df.columns else None
    if plot_price_col and plot_eng_col and plot_views_col:
        fig = px.scatter_3d(df, x=plot_views_col, y=plot_price_col, z=plot_eng_col, color='cluster_name', title='3D: views-price-engagement')
        fig.write_html('clusters_3d.html')
        print('3D plot guardado: clusters_3d.html')
    else:
        print('Omitiendo Plotly 3D: faltan columnas requeridas para la gráfica 3D.')
except Exception:
    print('Plotly no está instalado o falló; para 3D instálalo con: pip install plotly')
