import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from datetime import datetime, timedelta
import seaborn as sns
import matplotlib.pyplot as plt

st.set_page_config(page_title="🧪 Test - Comparaciones de Lotes", layout="wide")
st.title("🧪 Comparación Avanzada de Lotes de Fermentación")
st.markdown("Tabla de estadísticas + Índice de Calidad + Gráficos comparativos")

# --- GENERAR DATOS SIMULADOS (3 LOTES) ---
@st.cache_data
def generar_lotes_simulados():
    """Genera 3 lotes con características diferentes"""
    horas = np.linspace(0, 72, 500)
    
    # LOTE 1: Fermentación óptima
    temp1 = 25 + 15 * (1 - np.exp(-horas/20)) + 0.3 * np.sin(horas/5) + np.random.normal(0, 0.15, len(horas))
    pres1 = 1 + 0.8 * (1 - np.exp(-horas/15)) + 0.15 * np.sin(horas/6) + np.random.normal(0, 0.03, len(horas))
    
    # LOTE 2: Fermentación con variabilidad media
    temp2 = 25 + 14 * (1 - np.exp(-horas/22)) + 0.8 * np.sin(horas/4) + np.random.normal(0, 0.3, len(horas))
    pres2 = 1 + 0.75 * (1 - np.exp(-horas/18)) + 0.3 * np.sin(horas/5) + np.random.normal(0, 0.08, len(horas))
    
    # LOTE 3: Fermentación con problemas (inestable)
    temp3 = 25 + 13 * (1 - np.exp(-horas/25)) + 1.2 * np.sin(horas/3) + np.random.normal(0, 0.5, len(horas))
    pres3 = 1 + 0.7 * (1 - np.exp(-horas/20)) + 0.5 * np.sin(horas/4) + np.random.normal(0, 0.15, len(horas))
    
    inicio = datetime.now() - timedelta(hours=72)
    tiempos = [inicio + timedelta(hours=float(h)) for h in horas]
    
    lotes = {
        'Lote A (Óptimo)': {
            'temp': pd.DataFrame({'Tiempo': tiempos, 'Valor': temp1}).sort_values('Tiempo').reset_index(drop=True),
            'pres': pd.DataFrame({'Tiempo': tiempos, 'Valor': pres1}).sort_values('Tiempo').reset_index(drop=True),
        },
        'Lote B (Normal)': {
            'temp': pd.DataFrame({'Tiempo': tiempos, 'Valor': temp2}).sort_values('Tiempo').reset_index(drop=True),
            'pres': pd.DataFrame({'Tiempo': tiempos, 'Valor': pres2}).sort_values('Tiempo').reset_index(drop=True),
        },
        'Lote C (Inestable)': {
            'temp': pd.DataFrame({'Tiempo': tiempos, 'Valor': temp3}).sort_values('Tiempo').reset_index(drop=True),
            'pres': pd.DataFrame({'Tiempo': tiempos, 'Valor': pres3}).sort_values('Tiempo').reset_index(drop=True),
        }
    }
    return lotes

lotes = generar_lotes_simulados()
lotes_seleccionados = list(lotes.keys())

# --- FUNCIÓN PARA CALCULAR ESTADÍSTICAS ---
def calcular_estadisticas(lotes_dict, nombres_lotes):
    """Calcula métricas para cada lote"""
    stats = []
    
    for nombre in nombres_lotes:
        df_temp = lotes_dict[nombre]['temp']
        df_pres = lotes_dict[nombre]['pres']
        
        # Calcular tasa de cambio (diferencia central)
        delta_tiempo = df_temp['Tiempo'].diff().dt.total_seconds() / 3600
        tasa_temp = (df_temp['Valor'].shift(-1) - df_temp['Valor'].shift(1)) / (2 * delta_tiempo)
        
        duracion_h = (df_temp['Tiempo'].max() - df_temp['Tiempo'].min()).total_seconds() / 3600
        
        stats.append({
            'Lote': nombre,
            'Temp Max (°C)': f"{df_temp['Valor'].max():.2f}",
            'Temp Min (°C)': f"{df_temp['Valor'].min():.2f}",
            'Temp Prom (°C)': f"{df_temp['Valor'].mean():.2f}",
            'Temp Desv (°C)': f"{df_temp['Valor'].std():.3f}",
            'Pres Max (bar)': f"{df_pres['Valor'].max():.2f}",
            'Pres Prom (bar)': f"{df_pres['Valor'].mean():.2f}",
            'Tasa Max (°C/h)': f"{tasa_temp[1:-1].max():.3f}",
            'Tasa Prom (°C/h)': f"{tasa_temp[1:-1].mean():.3f}",
            'Duración (h)': f"{duracion_h:.1f}",
        })
    
    return pd.DataFrame(stats)

# --- FUNCIÓN PARA CALCULAR ÍNDICE DE CALIDAD ---
def calcular_indice_calidad(lotes_dict, nombres_lotes):
    """
    Calcula un índice de calidad 0-100 basado en:
    - Estabilidad (desv std baja = mejor)
    - Velocidad controlada (tasa de cambio estable)
    - Duración adecuada
    """
    scores = []
    
    for nombre in nombres_lotes:
        df_temp = lotes_dict[nombre]['temp']
        
        # Estabilidad: temperatura con baja desviación = mejor
        desv = df_temp['Valor'].std()
        estabilidad = max(0, 100 - (desv * 50))  # Normalizar
        
        # Velocidad controlada: tasa de cambio baja y estable
        delta_tiempo = df_temp['Tiempo'].diff().dt.total_seconds() / 3600
        tasa_temp = (df_temp['Valor'].shift(-1) - df_temp['Valor'].shift(1)) / (2 * delta_tiempo)
        desv_tasa = tasa_temp[1:-1].std()
        velocidad = max(0, 100 - (desv_tasa * 100))
        
        # Promedio ponderado
        calidad = (estabilidad * 0.6 + velocidad * 0.4)
        
        scores.append({
            'Lote': nombre,
            'Estabilidad': f"{estabilidad:.1f}",
            'Velocidad Controlada': f"{velocidad:.1f}",
            'Índice de Calidad': f"{calidad:.1f}/100",
            '🎯 Rating': '⭐⭐⭐' if calidad >= 75 else ('⭐⭐' if calidad >= 50 else '⭐')
        })
    
    return pd.DataFrame(scores)

# --- LAYOUT PRINCIPAL ---
st.subheader("📊 Comparativa de Lotes")

# TAB 1: Estadísticas
tab1, tab2, tab3, tab4 = st.tabs(["📋 Estadísticas", "🎯 Calidad", "📈 Desviaciones", "🔗 Correlación"])

with tab1:
    st.markdown("#### Tabla Comparativa de Métricas")
    df_stats = calcular_estadisticas(lotes, lotes_seleccionados)
    st.dataframe(df_stats, use_container_width=True, hide_index=True)

with tab2:
    st.markdown("#### Índice de Calidad de Fermentación")
    df_calidad = calcular_indice_calidad(lotes, lotes_seleccionados)
    st.dataframe(df_calidad, use_container_width=True, hide_index=True)
    
    # Gráfico de índice
    col1, col2 = st.columns([2, 1])
    with col1:
        fig_calidad = go.Figure()
        calidades = [float(x.split('/')[0]) for x in df_calidad['Índice de Calidad']]
        fig_calidad.add_trace(go.Bar(
            x=df_calidad['Lote'],
            y=calidades,
            marker=dict(color=['#1f77b4' if x >= 75 else '#ff7f0e' if x >= 50 else '#d62728' for x in calidades]),
            text=[f"{x:.1f}" for x in calidades],
            textposition='outside'
        ))
        fig_calidad.update_layout(
            title="Índice de Calidad por Lote",
            yaxis_title="Puntuación (0-100)",
            height=400,
            showlegend=False
        )
        st.plotly_chart(fig_calidad, use_container_width=True)
    
    with col2:
        st.markdown("**Escala:**")
        st.markdown("🟢 **75-100**: Óptimo")
        st.markdown("🟡 **50-75**: Normal")
        st.markdown("🔴 **<50**: Problemático")

with tab3:
    st.markdown("#### Desviación de Cada Lote respecto al Promedio")
    
    # Calcular desviación
    fig_desv = go.Figure()
    
    # Calcular temperatura promedio de todos los lotes
    temp_promedio_general = np.mean([lotes[nombre]['temp']['Valor'].mean() for nombre in lotes_seleccionados])
    
    colores_desv = px.colors.qualitative.Plotly
    
    for idx, nombre in enumerate(lotes_seleccionados):
        df_temp = lotes[nombre]['temp']
        x_vals = (df_temp['Tiempo'] - df_temp['Tiempo'].min()).dt.total_seconds() / 3600
        desviacion = df_temp['Valor'] - temp_promedio_general
        
        fig_desv.add_trace(go.Scatter(
            x=x_vals, y=desviacion,
            mode='lines', name=nombre,
            line=dict(width=2.5),
            fill='tozeroy'
        ))
    
    fig_desv.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig_desv.update_layout(
        title="Desviación de Temperatura respecto al Promedio General",
        xaxis_title="Horas",
        yaxis_title="Desviación (°C)",
        hovermode="x unified",
        height=500
    )
    st.plotly_chart(fig_desv, use_container_width=True)

with tab4:
    st.markdown("#### Correlación entre Lotes")
    
    # Crear matriz de correlación de temperaturas
    temp_data = {}
    for nombre in lotes_seleccionados:
        temp_data[nombre] = lotes[nombre]['temp']['Valor'].values
    
    df_temp_matrix = pd.DataFrame(temp_data)
    corr_matrix = df_temp_matrix.corr()
    
    fig_corr = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=corr_matrix.columns,
        y=corr_matrix.columns,
        colorscale='RdBu',
        zmid=0,
        zmin=-1,
        zmax=1,
        text=np.round(corr_matrix.values, 2),
        texttemplate='%{text}',
        textfont={"size": 12},
    ))
    
    fig_corr.update_layout(
        title="Matriz de Correlación de Temperatura entre Lotes",
        height=400
    )
    st.plotly_chart(fig_corr, use_container_width=True)
    
    st.info("💡 **Correlación alta (>0.8)** = Lotes con patrones similares")

# --- GRÁFICOS PRINCIPALES ---
st.subheader("📈 Gráficos de Fermentación")

fig_temp_all = go.Figure()
fig_pres_all = go.Figure()
colores = px.colors.qualitative.Plotly

for idx, nombre in enumerate(lotes_seleccionados):
    color = colores[idx % len(colores)]
    df_temp = lotes[nombre]['temp']
    df_pres = lotes[nombre]['pres']
    
    x_vals = (df_temp['Tiempo'] - df_temp['Tiempo'].min()).dt.total_seconds() / 3600
    
    fig_temp_all.add_trace(go.Scatter(
        x=x_vals, y=df_temp['Valor'],
        mode='lines', name=nombre,
        line=dict(color=color, width=3)
    ))
    
    fig_pres_all.add_trace(go.Scatter(
        x=x_vals, y=df_pres['Valor'],
        mode='lines', name=nombre,
        line=dict(color=color, width=3)
    ))

fig_temp_all.update_layout(
    title="Temperatura - Comparativa de Todos los Lotes",
    xaxis_title="Horas",
    yaxis_title="°C",
    hovermode="x unified",
    height=500
)

fig_pres_all.update_layout(
    title="Presión - Comparativa de Todos los Lotes",
    xaxis_title="Horas",
    yaxis_title="bar",
    hovermode="x unified",
    height=500
)

col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(fig_temp_all, use_container_width=True)
with col2:
    st.plotly_chart(fig_pres_all, use_container_width=True)

# --- BOX PLOT COMPARATIVO ---
st.subheader("📊 Distribución de Temperaturas (Box Plot)")

fig_box = go.Figure()

for nombre in lotes_seleccionados:
    df_temp = lotes[nombre]['temp']
    fig_box.add_trace(go.Box(
        y=df_temp['Valor'],
        name=nombre,
        boxmean='sd'
    ))

fig_box.update_layout(
    title="Distribución de Temperatura por Lote (Mediana, Q1-Q3, Desv Std)",
    yaxis_title="Temperatura (°C)",
    height=500
)
st.plotly_chart(fig_box, use_container_width=True)

st.success("✅ ¡Comparativa completa lista!")
