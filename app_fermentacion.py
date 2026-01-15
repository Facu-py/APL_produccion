import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
from datetime import datetime
import io

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

st.set_page_config(page_title="Comparador de Lotes - Fermentación", layout="wide")
st.title("🚀 Comparador de Curvas de Fermentación")
st.markdown("Selecciona lotes desde la planilla de producción y compara temperatura y presión automáticamente desde Drive.")

# --- Configuración Google API ---
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gdrive"], scopes=[
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/spreadsheets.readonly'
    ])

# Sheets siempre con service account (para planilla privada)
sheets_service = build('sheets', 'v4', credentials=credentials)

# Drive: API key si disponible (para carpeta pública), sino service account
if 'api_key' in st.secrets.get('gdrive', {}):
    api_key = st.secrets['gdrive']['api_key']
    drive_service = build('drive', 'v3', developerKey=api_key)
    st.write("Usando API key para Drive (carpeta pública)")
else:
    drive_service = build('drive', 'v3', credentials=credentials)
    st.write("Service account email:", st.secrets["gdrive"].get("client_email", "No encontrado"))

# ID de carpeta y planilla
FOLDER_ID = "1_2tfy8XDi4cDSokfi4Mbr-UAM9dTThhE"
SPREADSHEET_ID = "1ReAXz4FompTtBcNPVulztA5fwmj169LkCYrh4vQoE6g"

# --- Cargar planilla ---
@st.cache_data(ttl=600)
def cargar_planilla():
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range="DDP!A1:AA10000"
        ).execute()

        values = result.get('values', [])
        if not values:
            return pd.DataFrame()

        df = pd.DataFrame(values[1:], columns=values[0])
        df['INICIO'] = pd.to_datetime(df['INICIO'], dayfirst=True, errors='coerce')
        df['FIN'] = pd.to_datetime(df['FIN'], dayfirst=True, errors='coerce')
        return df

    except Exception as e:
        st.error(f"Error cargando planilla: {e}")
        return pd.DataFrame()

df_planilla = cargar_planilla()
if df_planilla.empty:
    st.error("No se pudo cargar la planilla. Verifica credenciales y permisos.")
    st.stop()

# --- SUBIR ARCHIVOS ---
st.subheader("Sube los archivos Excel de los lotes a comparar")
uploaded_files = st.file_uploader("Arrastra y suelta archivos Excel (.xlsx, .xls)", accept_multiple_files=True, type=['xlsx', 'xls'])

if not uploaded_files:
    st.info("Sube al menos un archivo Excel para graficar.")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("Opciones")
    tiempo_relativo = st.checkbox("Tiempo relativo (horas desde inicio)", value=True)
    usar_inicio_oficial = st.checkbox("Usar INICIO oficial de planilla", value=False)  # Deshabilitado
    mostrar_presion = st.checkbox("Mostrar presión", value=True)

# --- PROCESAR ARCHIVOS SUBIDOS ---
lotes = {}
for uploaded_file in uploaded_files:
    try:
        df = pd.read_excel(uploaded_file)
        df = df.dropna(how='all')
        tiempo_col = 'TimeString' if 'TimeString' in df.columns else df.columns[0]
        df['Tiempo'] = pd.to_datetime(df[tiempo_col], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        df = df.dropna(subset=['Tiempo']).sort_values('Tiempo')

        df_temp = df[df['VarName'].str.contains('T1.Output_registro', na=False)]
        df_pres = df[df['VarName'].str.contains('P1.Output_registro', na=False)]

        df_temp['Valor'] = pd.to_numeric(df_temp['VarValue'], errors='coerce')
        df_pres['Valor'] = pd.to_numeric(df_pres['VarValue'], errors='coerce')

        nombre_limpio = re.sub(r'\.(xlsx|xlsm)$', '', uploaded_file.name, flags=re.I)
        nombre_limpio = re.sub(r'_R\d+$', '', nombre_limpio)

        # Usar el nombre del archivo como lote
        lote_asociado = nombre_limpio

        lotes[nombre_limpio] = {'temp': df_temp, 'pres': df_pres, 'lote': lote_asociado}

    except Exception as e:
        st.error(f"Error procesando {uploaded_file.name}: {e}")

if not lotes:
    st.error("No se pudieron procesar los archivos subidos.")
    st.stop()

# --- GRAFICOS ---
fig_temp = go.Figure()
fig_pres = go.Figure() if mostrar_presion else None
colores = px.colors.qualitative.Plotly

for idx, (nombre, data) in enumerate(lotes.items()):
    color = colores[idx % len(colores)]
    df_temp = data['temp']
    df_pres = data['pres']

    if tiempo_relativo:
        inicio = None
        if usar_inicio_oficial:
            row = df_planilla[df_planilla["Nº LOTE"] == data['lote']]["INICIO"]
            if not row.empty:
                inicio = row.iloc[0]

        if inicio is None:
            inicio = df_temp['Tiempo'].min()

        x_temp = (df_temp['Tiempo'] - inicio).dt.total_seconds() / 3600
        x_pres = (df_pres['Tiempo'] - inicio).dt.total_seconds() / 3600 if len(df_pres) else []
        xlabel = "Horas"
    else:
        x_temp = df_temp['Tiempo']
        x_pres = df_pres['Tiempo']
        xlabel = "Fecha/Hora"

    fig_temp.add_trace(go.Scatter(
        x=x_temp, y=df_temp['Valor'],
        mode='lines', name=f"{nombre} - Temp",
        line=dict(color=color, width=3),
    ))

    if mostrar_presion and len(df_pres):
        fig_pres.add_trace(go.Scatter(
            x=x_pres, y=df_pres['Valor'],
            mode='lines', name=f"{nombre} - Pres",
            line=dict(color=color, width=3),
        ))

fig_temp.update_layout(
    title="Temperatura",
    xaxis_title=xlabel,
    yaxis_title="°C",
    hovermode="x unified",
    height=600
)

st.plotly_chart(fig_temp, use_container_width=True)

if mostrar_presion:
    fig_pres.update_layout(
        title="Presión",
        xaxis_title=xlabel,
        yaxis_title="bar",
        hovermode="x unified",
        height=600
    )
    st.plotly_chart(fig_pres, use_container_width=True)

st.success("¡Comparación lista!")
