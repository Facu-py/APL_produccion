# Copilot instructions for APL_produccion

This file contains concise, actionable guidance for AI coding agents working on this repository.

## Big picture
- Single-file Streamlit app: `app_fermentacion.py` is the main app and contains the full UI, data loading, processing, and plotting logic.
- Data sources: a Google Sheets spreadsheet (metadata) and Excel files stored in a Google Drive folder (time series). Constants `FOLDER_ID` and `SPREADSHEET_ID` are defined at top of `app_fermentacion.py`.

## Key files
- `app_fermentacion.py`: single entrypoint for the web app — inspect for all business logic (UI, Google API, parsing, plotting).
- `requirements.txt`: lists runtime dependencies to install.
- `README.md`: minimal project description.

## How to run locally (developer workflow)
- Install deps: `pip install -r requirements.txt`.
- Run the app: `streamlit run app_fermentacion.py`.
- Authentication: the app expects a Google service account JSON object available as `st.secrets["gdrive"]`. Provide this via Streamlit secrets (`.streamlit/secrets.toml`) or the Streamlit cloud secrets UI.

Example minimal `secrets.toml`:
```
[gdrive]
# paste the JSON object here as a single TOML value or set STREAMLIT_SECRETS in deployment
```

## Data and parsing conventions (important for modifications)
- Sheet range read: `sheets_service.spreadsheets().values().get(range="DDP!A1:AA10000")` — code expects header row with columns including `Nº LOTE`, `INICIO`, `FIN`, `Producto`, `ESTADO`, `Mes`.
- Drive file parsing: downloaded Excel should include a time column (either `TimeString` or the first column) and columns `VarName` / `VarValue`.
- Temperature rows are selected via `df['VarName'].str.contains('T1.Output_registro')`; pressure via `P1.Output_registro`.
- Time parsing uses format `%d/%m/%Y %H:%M:%S` (errors coerced to NaT) and sorting by `Tiempo`.

## Matching logic and file naming patterns
- `buscar_archivo_lote(lote)` normalizes names by removing `-` and spaces and uppercasing. It attempts:
  - exact prefix match with `_R{reactor}` (reactor derived from lote split)
  - prefix with `_R`
  - fallback: filename contains cleaned lote
- When changing matching logic, update unit tests or run manual checks against `archivos_drive` listing.

## Caching and performance
- Streamlit caching decorators used: `@st.cache_data(ttl=600)` and `@st.cache_data(ttl=3600)` — adjust TTLs in-place if you need fresher or longer-lived caches.

## Testing and debugging tips
- To reproduce Drive access locally, use a service account JSON in `st.secrets` and ensure the service account has read access to the Drive folder and spreadsheet.
- Add `st.write()` or `st.json()` temporarily to inspect `archivos_drive`, `df_planilla`, and parsed DataFrames when debugging.
- For parsing issues, verify column names with a quick read of the downloaded Excel (open in Excel or read with `pd.read_excel` in a REPL).

## Project-specific conventions
- Single-file app: prefer making small, local helper functions inside `app_fermentacion.py` rather than introducing new modules, unless the change grows beyond a few hundred lines.
- Keep the hard-coded `FOLDER_ID` / `SPREADSHEET_ID` explicit when testing; for production, consider moving to secrets or config.

## When making changes
- Preserve the existing Google API setup pattern (service_account from `st.secrets["gdrive"]` and `build(...)`) unless switching to OAuth flow intentionally.
- If you add dependencies, update `requirements.txt`.
- Keep UI labels and DataFrame column names consistent with the spreadsheet; changing headers requires updating the sheet-reading code and any UI filters that rely on them.

## Where to look for examples in this repo
- `app_fermentacion.py`: matching logic (`buscar_archivo_lote`), file download/parse (`procesar_archivo`), and plotting (`fig_temp`, `fig_pres`).

If anything here is unclear or you want a different level of detail (e.g., suggested tests or refactor plan), tell me which section to expand. 
