import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
import time

# Cargar credenciales
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gdrive"], scopes=[
        'https://www.googleapis.com/auth/drive.readonly',
    ])

drive_service = build('drive', 'v3', credentials=credentials)

st.title("🔍 Test de Acceso a Google Drive")

service_account_email = st.secrets["gdrive"].get("client_email", "No encontrado")
st.write(f"**Email del Service Account:** `{service_account_email}`")

st.info("**Esperando a que se propaguen los permisos...**")
time.sleep(2)

# Test 1: Intentar acceder a la carpeta SCADA
st.subheader("Test 1: Acceso a carpeta SCADA 2026")
SCADA_FOLDER_ID = "1SS_UCOKlEgCs-tPl_tL0avx0CTQN3XpA"

try:
    folder_meta = drive_service.files().get(fileId=SCADA_FOLDER_ID, fields='name, mimeType, owners').execute()
    st.success(f"✅ Carpeta encontrada: **{folder_meta.get('name')}**")
    st.write(f"Propietario: {folder_meta.get('owners', [{}])[0].get('displayName', 'Desconocido')}")
except Exception as e:
    st.error(f"❌ No se puede acceder a la carpeta SCADA")
    st.error(f"Error: {e}")
    st.info("**Esto podría ser normal si los permisos aún no se han propagado.**")

# Test 2: Listar archivos en SCADA
st.subheader("Test 2: Listar archivos en SCADA")
try:
    query = f"'{SCADA_FOLDER_ID}' in parents and trashed = false"
    results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)', pageSize=50).execute()
    files = results.get('files', [])
    st.write(f"**Archivos encontrados: {len(files)}**")
    if files:
        for f in files:
            st.write(f"  ✅ {f['name']}")
    else:
        st.warning("⚠️ 0 archivos encontrados en la carpeta")
except Exception as e:
    st.error(f"Error: {e}")

# Test 3: Alternativa - Buscar por nombre
st.subheader("Test 3: Buscar archivos por nombre (alternativa)")
try:
    # Buscar archivos que contengan "GPF" (parece ser el patrón en Drive)
    query = "name contains 'GPF' and trashed = false"
    results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name, parents)', pageSize=50).execute()
    files = results.get('files', [])
    st.write(f"**Archivos encontrados con 'GPF': {len(files)}**")
    if files:
        st.write("Primeros 10:")
        for f in files[:10]:
            st.write(f"  ✅ {f['name']} (ID: `{f['id']}`)")
except Exception as e:
    st.error(f"Error: {e}")

# Test 4: Buscar archivos .xlsx directamente
st.subheader("Test 4: Buscar archivos .xlsx")
try:
    query = "name contains '.xlsx' and trashed = false"
    results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)', pageSize=20).execute()
    files = results.get('files', [])
    st.write(f"**Archivos .xlsx encontrados: {len(files)}**")
    if files:
        st.write("Primeros 10:")
        for f in files[:10]:
            st.write(f"  ✅ {f['name']}")
except Exception as e:
    st.error(f"Error: {e}")

# Test 5: Verificar permisos
st.subheader("Test 5: Verificar permisos y reintentar")
col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 Reintentar (esperar 5 seg)"):
        st.info("Esperando a que se propaguen los permisos...")
        time.sleep(5)
        st.rerun()

with col2:
    if st.button("🔄 Reintentar ahora"):
        st.rerun()

st.warning("""
**SI AÚN NO FUNCIONA:**

1. **Verifica que compartiste correctamente:**
   - Click en la carpeta de Drive
   - Click en "Compartir" (esquina superior derecha)
   - Busca el email `fermentacion-drive-reader@fermentacion-app-integracion.iam.gserviceaccount.com`
   - Confirma que dice "Lector"

2. **Si aparece un archivo con nombre "GPF"**, significa que SÍ tiene acceso (solo que a ese archivo específico)

3. **Alternativa temporal:** Usa la pestaña **"Cargar locales"** para subir archivos manualmente

4. **Si nada funciona**, posiblemente sea un problema de DNS o caché. Intenta:
   - Refrescar la página (F5)
   - Abrir en incógnito/privado
   - Esperar 10 minutos completos
""")

