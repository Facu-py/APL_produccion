# app_fermentacion.py
# Guardar este archivo y ejecutar con: streamlit run app_fermentacion.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import re
from datetime import datetime

st.set_page_config(page_title="Comparador de Lotes - Fermentación", layout="wide")
st.title("🚀 Comparador de Curvas de Fermentación")
st.markdown("Subí los archivos de los lotes (.csv o .xlsx) y compará temperatura y presión de forma interactiva.")

# Sidebar para subida de archivos
with st.sidebar:
    st.header("Subir lotes")
    uploaded_files = st.file_uploader(
        "Seleccioná uno o más archivos de lotes",
        type=['csv', 'xlsx'],
        accept_multiple_files=True
    )
    
    st.header("Opciones")
    tiempo_relativo = st.checkbox("Tiempo relativo (horas desde inicio del lote)", value=True)
    mostrar_presion = st.checkbox("Graficar presión", value=True)

if not uploaded_files:
    st.info("👆 Subí al menos un archivo para comenzar.")
    st.stop()

# Procesar archivos subidos
@st.cache_data(show_spinner=False)
def procesar_archivo(file):
    try:
        if file.name.lower().endswith('.csv'):
            df = pd.read_csv(file, sep=';', encoding='latin-1')
        else:
            df = pd.read_excel(file)
        
        df = df.dropna(how='all')
        
        # Columna de tiempo
        tiempo_col = 'TimeString' if 'TimeString' in df.columns else df.columns[0]
        df['Tiempo'] = pd.to_datetime(df[tiempo_col], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        df = df.dropna(subset=['Tiempo']).sort_values('Tiempo')
        
        # Extraer temperatura y presión
        df_temp = df[df['VarName'].str.contains('T1.Output_registro', na=False)].copy()
        df_pres = df[df['VarName'].str.contains('P1.Output_registro', na=False)].copy()
        
        df_temp['Valor'] = pd.to_numeric(df_temp['VarValue'], errors='coerce')
        df_pres['Valor'] = pd.to_numeric(df_pres['VarValue'], errors='coerce')
        
        df_temp = df_temp.dropna(subset=['Valor'])
        df_pres = df_pres.dropna(subset=['Valor'])
        
        # Nombre limpio del lote
        nombre = file.name
        nombre = re.sub(r'\.(csv|xlsx)$', '', nombre, flags=re.I)
        nombre = re.sub(r'_R\d+$', '', nombre)
        nombre = nombre.replace("Copia de ", "").strip()
        
        return nombre, df_temp, df_pres
    
    except Exception as e:
        st.error(f"Error procesando {file.name}: {e}")
        return None, None, None

# Procesar todos los archivos
lotes = {}
for file in uploaded_files:
    nombre, df_temp, df_pres = procesar_archivo(file)
    if nombre:
        lotes[nombre] = {'temp': df_temp, 'pres': df_pres, 'archivo': file.name}

if not lotes:
    st.error("No se pudieron procesar los archivos.")
    st.stop()

# Selector de lotes
st.subheader("Seleccioná los lotes a comparar")
cols = st.columns(3)
seleccionados = []
for i, (nombre, data) in enumerate(lotes.items()):
    with cols[i % 3]:
        if st.checkbox(nombre, key=nombre):
            seleccionados.append(nombre)

if not seleccionados:
    st.info("👈 Marcá al menos un lote para ver los gráficos.")
    st.stop()

# Aquí podrías cargar la planilla DDP para recorte oficial (opcional, te lo agrego después si querés)

# Preparar datos para gráficos
fig_temp = go.Figure()
fig_pres = go.Figure() if mostrar_presion else None

colores = px.colors.qualitative.Plotly

for idx, nombre in enumerate(seleccionados):
    data = lotes[nombre]
    color = colores[idx % len(colores)]
    
    df_temp = data['temp']
    df_pres = data['pres']
    
    # Tiempo relativo o absoluto
    if tiempo_relativo and len(df_temp) > 0:
        inicio = df_temp['Tiempo'].min()
        x_temp = (df_temp['Tiempo'] - inicio).dt.total_seconds() / 3600
        x_pres = (df_pres['Tiempo'] - inicio).dt.total_seconds() / 3600
        xlabel = "Horas desde inicio del lote"
    else:
        x_temp = df_temp['Tiempo']
        x_pres = df_pres['Tiempo']
        xlabel = "Fecha y Hora"
    
    # Temperatura
    fig_temp.add_trace(go.Scatter(
        x=x_temp, y=df_temp['Valor'],
        mode='lines',
        name=f"{nombre} - Temp",
        line=dict(color=color, width=3),
        hovertemplate=f"<b>{nombre}</b><br>Tiempo: %{{x}}<br>Temperatura: %{{y:.2f}} °C<extra></extra>"
    ))
    
    # Presión (si está activada)
    if mostrar_presion and len(df_pres) > 0:
        fig_pres.add_trace(go.Scatter(
            x=x_pres, y=df_pres['Valor'],
            mode='lines',
            name=f"{nombre} - Pres",
            line=dict(color=color, width=3),
            hovertemplate=f"<b>{nombre}</b><br>Tiempo: %{{x}}<br>Presión: %{{y:.2f}} bar<extra></extra>"
        ))

# Configuración común
fig_temp.update_layout(
    title="Comparación de Temperatura",
    xaxis_title=xlabel,
    yaxis_title="Temperatura (°C)",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=600
)

if fig_pres:
    fig_pres.update_layout(
        title="Comparación de Presión",
        xaxis_title=xlabel,
        yaxis_title="Presión (bar)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=600
    )

# Mostrar gráficos
st.plotly_chart(fig_temp, use_container_width=True)
if mostrar_presion and fig_pres:
    st.plotly_chart(fig_pres, use_container_width=True)

st.success(f"¡Listo! {len(seleccionados)} lote(s) comparados con gráficos interactivos (zoom, hover, etc.).")
