# app_fermentacion.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Comparador de Lotes - Fermentación", layout="wide")
st.title("🚀 Comparador de Curvas de Fermentación")
st.markdown("Subí los archivos de los lotes (.csv o .xlsx). La app mostrará una tabla con datos de producción de la planilla DDP y luego podrás comparar las curvas de temperatura y presión.")

# === CARGA DE PLANILLA DDP (Google Sheets) ===
@st.cache_resource
def cargar_ddp():
    # ID de tu planilla (extraído del link)
    SPREADSHEET_ID = '1ReAXz4FompTtBcNPVulztA5fwmj169LkCYrh4vQoE6g'
    HOJA = 'DDP'
    
    # Autenticación con cuenta de servicio (para Streamlit Cloud)
    # Debes subir un JSON de cuenta de servicio a Secrets en Streamlit Cloud (ver abajo)
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).worksheet(HOJA)
        data = sheet.get_all_values()
        df_ddp = pd.DataFrame(data[1:], columns=data[0])
        st.success("✅ Planilla DDP cargada correctamente")
        return df_ddp
    except Exception as e:
        st.error(f"Error cargando DDP: {e}. Verificá las credenciales.")
        return pd.DataFrame()

df_ddp = cargar_ddp()

# Sidebar
with st.sidebar:
    st.header("Subir lotes")
    uploaded_files = st.file_uploader(
        "Seleccioná uno o más archivos de lotes",
        type=['csv', 'xlsx'],
        accept_multiple_files=True
    )
    
    st.header("Opciones gráficas")
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
        tiempo_col = 'TimeString' if 'TimeString' in df.columns else df.columns[0]
        df['Tiempo'] = pd.to_datetime(df[tiempo_col], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        df = df.dropna(subset=['Tiempo']).sort_values('Tiempo')
        
        df_temp = df[df['VarName'].str.contains('T1.Output_registro', na=False)].copy()
        df_pres = df[df['VarName'].str.contains('P1.Output_registro', na=False)].copy()
        
        df_temp['Valor'] = pd.to_numeric(df_temp['VarValue'], errors='coerce')
        df_pres['Valor'] = pd.to_numeric(df_pres['VarValue'], errors='coerce')
        df_temp = df_temp.dropna(subset=['Valor'])
        df_pres = df_pres.dropna(subset=['Valor'])
        
        # Nombre limpio del lote (para buscar en DDP)
        nombre_limpio = file.name
        nombre_limpio = re.sub(r'\.(csv|xlsx)$', '', nombre_limpio, flags=re.I)
        nombre_limpio = re.sub(r'_R\d+$', '', nombre_limpio)
        nombre_limpio = nombre_limpio.replace("Copia de ", "").strip()
        
        return nombre_limpio, df_temp, df_pres, file.name
    
    except Exception as e:
        st.error(f"Error procesando {file.name}: {e}")
        return None, None, None, file.name

lotes = {}
for file in uploaded_files:
    nombre_limpio, df_temp, df_pres, archivo_original = procesar_archivo(file)
    if nombre_limpio:
        lotes[nombre_limpio] = {
            'temp': df_temp,
            'pres': df_pres,
            'archivo': archivo_original
        }

if not lotes:
    st.error("No se pudieron procesar los archivos.")
    st.stop()

# === TABLA CON DATOS DE DDP ===
st.subheader("📋 Información de los lotes subidos (de planilla DDP)")

tabla_data = []
for nombre_limpio in lotes.keys():
    fila_ddp = df_ddp[df_ddp['Nº LOTE'].astype(str).str.strip() == nombre_limpio]
    if not fila_ddp.empty:
        row = fila_ddp.iloc[0]
        tabla_data.append({
            "Lote": nombre_limpio,
            "Estado": row['ESTADO'],
            "Fecha": row['Fecha'],
            "Producto": row['Producto'],
            "Inicio": row['INICIO'],
            "Fin": row['FIN'],
            "Producidos [L]": row['Producidos [L]'],
            "Liberados [L]": row['Liberados [L]'],
            "Recuento UFC/ml": row['Recuento [UFC/ml]'],
            "Contaminado UFC/ml": row['Contaminado [UFC/ml]'],
            "Desvío": row['DESVÍO']
        })
    else:
        tabla_data.append({
            "Lote": nombre_limpio,
            "Estado": "No encontrado en DDP",
            "Fecha": "",
            "Producto": "",
            "Inicio": "",
            "Fin": "",
            "Producidos [L]": "",
            "Liberados [L]": "",
            "Recuento UFC/ml": "",
            "Contaminado UFC/ml": "",
            "Desvío": ""
        })

df_tabla = pd.DataFrame(tabla_data)
st.dataframe(df_tabla.style.apply(lambda row: ['background: lightgreen' if row.Estado == 'LIBERADO' 
                                              else 'background: lightcoral' if 'FNC' in row.Estado or 'PNC' in row.Estado 
                                              else '' for _ in row], axis=1), use_container_width=True)

# Selector de lotes para graficar
st.subheader("Seleccioná los lotes a comparar gráficamente")
seleccionados = []
cols = st.columns(3)
for i, nombre in enumerate(lotes.keys()):
    with cols[i % 3]:
        if st.checkbox(nombre, key=nombre):
            seleccionados.append(nombre)

if not seleccionados:
    st.info("👈 Marcá al menos un lote para ver los gráficos.")
    st.stop()

# Gráficos
fig_temp = go.Figure()
fig_pres = go.Figure() if mostrar_presion else None
colores = px.colors.qualitative.Plotly

for idx, nombre in enumerate(seleccionados):
    data = lotes[nombre]
    color = colores[idx % len(colores)]
    df_temp = data['temp']
    df_pres = data['pres']
    
    if tiempo_relativo and len(df_temp) > 0:
        inicio = df_temp['Tiempo'].min()
        x_temp = (df_temp['Tiempo'] - inicio).dt.total_seconds() / 3600
        x_pres = (df_pres['Tiempo'] - inicio).dt.total_seconds() / 3600 if len(df_pres) > 0 else []
        xlabel = "Horas desde inicio del lote"
    else:
        x_temp = df_temp['Tiempo']
        x_pres = df_pres['Tiempo']
        xlabel = "Fecha y Hora"
    
    fig_temp.add_trace(go.Scatter(x=x_temp, y=df_temp['Valor'], mode='lines', name=f"{nombre} - Temp", line=dict(color=color, width=3)))
    if mostrar_presion and len(df_pres) > 0:
        fig_pres.add_trace(go.Scatter(x=x_pres, y=df_pres['Valor'], mode='lines', name=f"{nombre} - Pres", line=dict(color=color, width=3)))

fig_temp.update_layout(title="Comparación de Temperatura", xaxis_title=xlabel, yaxis_title="Temperatura (°C)", hovermode="x unified", height=600)
if fig_pres:
    fig_pres.update_layout(title="Comparación de Presión", xaxis_title=xlabel, yaxis_title="Presión (bar)", hovermode="x unified", height=600)

st.plotly_chart(fig_temp, use_container_width=True)
if mostrar_presion and fig_pres:
    st.plotly_chart(fig_pres, use_container_width=True)

st.success(f"¡Listo! {len(seleccionados)} lote(s) comparados.")
