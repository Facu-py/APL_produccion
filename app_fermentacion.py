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

# Sheets y Drive con service account
sheets_service = build('sheets', 'v4', credentials=credentials)
drive_service = build('drive', 'v3', credentials=credentials)

# ID de carpeta y planilla
FOLDER_ID = "1_2tfy8XDi4cDSokfi4Mbr-UAM9dTThhE"
SPREADSHEET_ID = "1ReAXz4FompTtBcNPVulztA5fwmj169LkCYrh4vQoE6g"
SCADA_FOLDER_ID = "1SS_UCOKlEgCs-tPl_tL0avx0CTQN3XpA"  # Carpeta con archivos SCADA 2026

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

# --- Listar archivos de carpeta Drive ---
def listar_archivos_drive(folder_id):
    try:
        # Intenta listar TODOS los archivos primero (sin filtro MIME)
        query = f"'{folder_id}' in parents and trashed = false"
        results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name, mimeType)', pageSize=100).execute()
        all_files = results.get('files', [])
        
        st.write(f"🔍 DEBUG - Total archivos en carpeta: {len(all_files)}")
        
        if all_files:
            st.write(f"📊 Todos los archivos encontrados:")
            for f in all_files:
                st.write(f"  - {f['name']} ({f.get('mimeType', 'unknown')})")
        
        # Filtra solo archivos Excel
        excel_files = [f for f in all_files if f['name'].lower().endswith(('.xlsx', '.xls'))]
        st.write(f"✅ Archivos Excel encontrados: {len(excel_files)}")
        
        return sorted(excel_files, key=lambda x: x['name'])
    except Exception as e:
        st.error(f"❌ Error listando archivos de Drive: {e}")
        import traceback
        st.error(f"Detalles: {traceback.format_exc()}")
        return []

# --- Descargar archivo de Drive ---
@st.cache_data(ttl=3600)
def descargar_archivo_drive(file_id):
    try:
        request = drive_service.files().get_media(fileId=file_id)
        file = io.BytesIO()
        downloader = MediaIoBaseDownload(file, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        file.seek(0)
        return file
    except Exception as e:
        st.error(f"Error descargando archivo: {e}")
        return None

df_planilla = cargar_planilla()
if df_planilla.empty:
    st.error("No se pudo cargar la planilla. Verifica credenciales y permisos.")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("Opciones")
    tiempo_relativo = st.checkbox("Tiempo relativo (horas desde inicio)", value=True)
    usar_inicio_oficial = st.checkbox("Usar INICIO oficial de planilla", value=False)
    mostrar_presion = st.checkbox("Mostrar presión", value=True)

# --- SELECCIONAR ARCHIVOS (Local o Drive) ---
st.subheader("Selecciona los archivos a comparar")
tab_local, tab_drive = st.tabs(["Cargar locales", "Seleccionar de Drive"])

uploaded_files = []

with tab_local:
    uploaded_files = st.file_uploader("Arrastra y suelta archivos Excel (.xlsx, .xls)", accept_multiple_files=True, type=['xlsx', 'xls'])

with tab_drive:
    st.write(f"🔍 Buscando archivos en carpeta SCADA 2026...")
    archivos_drive = listar_archivos_drive(SCADA_FOLDER_ID)
    
    if archivos_drive:
        st.write(f"📁 Se encontraron {len(archivos_drive)} archivos en Drive (SCADA 2026)")
        selected_files = st.multiselect(
            "Selecciona los archivos a descargar:",
            options=archivos_drive,
            format_func=lambda x: x['name']
        )
        
        if selected_files:
            st.info(f"Descargando {len(selected_files)} archivo(s)...")
            # Descargar archivos seleccionados
            drive_files_data = []
            for file_info in selected_files:
                file_data = descargar_archivo_drive(file_info['id'])
                if file_data:
                    drive_files_data.append((file_info['name'], file_data))
            
            # Simular file_uploader creando objetos tipo BytesIO con atributo 'name'
            class UploadedFile:
                def __init__(self, name, data):
                    self.name = name
                    self.data = data
                def read(self):
                    return self.data.read()
            
            uploaded_files = [UploadedFile(name, data) for name, data in drive_files_data]
    else:
        st.warning(f"⚠️ No se encontraron archivos Excel en la carpeta (ID: {SCADA_FOLDER_ID})")
        st.info("Verifica que:")
        st.markdown("""
        - La carpeta tenga archivos .xlsx o .xls
        - El email **fermentacion-drive-reader@fermentacion-app-integracion.iam.gserviceaccount.com** tenga acceso de lectura
        - Los permisos se hayan propagado correctamente
        """)

if not uploaded_files:
    st.info("⬆️ Carga al menos un archivo Excel para graficar.")
    st.stop()

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

# --- SELECCIONAR LOTES A GRAFICAR ---
st.subheader("📊 Selecciona los lotes a graficar")
lotes_disponibles = list(lotes.keys())
lotes_seleccionados = st.multiselect(
    "Elige los lotes que deseas comparar:",
    options=lotes_disponibles,
    default=lotes_disponibles  # Por defecto, todos seleccionados
)

if not lotes_seleccionados:
    st.warning("⚠️ Debes seleccionar al menos un lote para graficar.")
    st.stop()

# --- MOSTRAR INFORMACIÓN DE LOTES (Tabla DDP) ---
st.subheader("📋 Información de los lotes")

# Preparar datos de lotes para mostrar
info_lotes = []
for nombre_lote in lotes_seleccionados:
    # Buscar en la planilla
    lote_info = df_planilla[df_planilla["Nº LOTE"] == lotes[nombre_lote]['lote']]
    
    if not lote_info.empty:
        row = lote_info.iloc[0]
        info = {
            "Lote": nombre_lote,
            "Estado": row.get("ESTADO", "N/A"),
            "Recuento": row.get("RECUENTO", "N/A"),
        }
        
        # Si es PNC, mostrar recuento de contaminado
        if str(row.get("ESTADO", "")).upper() == "PNC":
            info["Recuento Contaminado"] = row.get("RECUENTO_CONTAMINADO", "N/A")
        
        info_lotes.append(info)
    else:
        # Si no está en la planilla, mostrar con info vacía
        info_lotes.append({
            "Lote": nombre_lote,
            "Estado": "No encontrado",
            "Recuento": "N/A",
        })

# Mostrar tabla
if info_lotes:
    df_info = pd.DataFrame(info_lotes)
    st.dataframe(df_info, use_container_width=True, hide_index=True)
else:
    st.info("No hay información disponible para los lotes seleccionados.")

# --- GRÁFICOS ---
st.subheader("📈 Gráficos de Fermentación")
fig_temp = go.Figure()
fig_pres = go.Figure() if mostrar_presion else None
colores = px.colors.qualitative.Plotly

for idx, nombre in enumerate(lotes_seleccionados):
    color = colores[idx % len(colores)]
    data = lotes[nombre]
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