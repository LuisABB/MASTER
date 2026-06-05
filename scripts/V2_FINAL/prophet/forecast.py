import pandas as pd
from prophet import Prophet
import matplotlib.pyplot as plt

# 1️⃣ Cargar CSV (archivo local en el proyecto)
df = pd.read_csv('dataset_validated.csv')

# 2️⃣ Convertir fechas a datetime
# Puedes usar 'generated_at' como timestamp principal
df['generated_at'] = pd.to_datetime(df['generated_at'])
df['trends_first_date'] = pd.to_datetime(df['trends_first_date'])

# 3️⃣ Selección de variables para Prophet
# Prophet requiere 'ds' como fecha y 'y' como variable a predecir
df_prophet = df[['generated_at', 'trends_mean', 'trends_slope', 'country']].rename(
    columns={'generated_at':'ds', 'trends_mean':'y'}
)

# 4️⃣ Forecast por país
countries = df_prophet['country'].unique()
forecasts = {}

for country in countries:
    df_country = df_prophet[df_prophet['country'] == country].copy()
    
    # 5️⃣ Configuración del modelo
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False
    )
    
    # 6️⃣ Agregar trends_slope como regresor opcional si existe
    if df_country['trends_slope'].notna().sum() > 0:
        model.add_regressor('trends_slope')
    
    # 7️⃣ Ajustar modelo
    model.fit(df_country)
    
    # 8️⃣ Crear dataframe para predicción futura (90 días)
    future = model.make_future_dataframe(periods=90)
    
    # Incluir regresor trends_slope en futuro
    if 'trends_slope' in df_country.columns:
        # Usamos el último valor de trends_slope como aproximación
        future['trends_slope'] = df_country['trends_slope'].iloc[-1]
    
    # 9️⃣ Predicción
    forecast = model.predict(future)
    forecasts[country] = forecast
    
    # 10️⃣ Graficar predicción
    fig = model.plot(forecast)
    plt.title(f'Forecast trends_mean - {country}')
    plt.xlabel('Fecha')
    plt.ylabel('Trends Mean')
    plt.show()
    
    # 11️⃣ Componentes de la predicción (tendencia, estacionalidad)
    fig2 = model.plot_components(forecast)
    plt.show()

# 12️⃣ forecasts contiene los resultados de cada país
