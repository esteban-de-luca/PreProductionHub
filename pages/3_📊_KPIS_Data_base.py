import streamlit as st

from ui_theme import apply_shared_sidebar

from src.kpis.kpi_sheets_analyzer import run_all_years_from_secrets, DEFAULT_MODEL_MAP


st.set_page_config(page_title="KPIS & Data base", layout="wide")

apply_shared_sidebar("pages/3_📊_KPIS_Data_base.py")
st.markdown("<style>h1 { font-size: 2.2rem !important; }</style>", unsafe_allow_html=True)

st.title("KPIS & Data base")

col_back, _ = st.columns([1, 5])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

st.caption("Acceso a KPIS de equipo, base de datos e información de ficheros de cortes realizados")

if "kpis" not in st.secrets:
    st.error("No encuentro [kpis] en Secrets. Añádelo en Streamlit Secrets y reinicia la app.")
    st.stop()

k = st.secrets["kpis"]

# Si ya tienes credenciales en otro bloque, cambia la clave aquí:
# Por ejemplo: st.secrets["gcp_service_account"] o st.secrets["google"]
# IMPORTANTE: esto debe ser el dict completo del Service Account.
if "gcp_service_account" in st.secrets:
    service_account_info = st.secrets["gcp_service_account"]
elif "google" in st.secrets:
    service_account_info = st.secrets["google"]
elif "gdrive" in st.secrets and "type" in st.secrets["gdrive"]:
    # Si metiste credenciales dentro de [gdrive] (no recomendado, pero soportado)
    service_account_info = st.secrets["gdrive"]
else:
    st.error(
        "No encuentro credenciales de Service Account en Secrets.\n\n"
        "Necesitas un bloque tipo [gcp_service_account] (recomendado) con el JSON de Google."
    )
    st.stop()

spreadsheet_id = k["ficheros_corte_sheet_id"]
gid_2024 = int(k["gid_2024"])
gid_2025 = int(k["gid_2025"])
gid_2026 = int(k["gid_2026"])
header_row = int(k.get("header_row", 4))
data_start_row = int(k.get("data_start_row", 5))


# ==========
# Sidebar: ajustes
# ==========
with st.sidebar:
    st.header("Ajustes KPIs")

    dash_means = st.selectbox("Cómo interpretar “-” en Modelo", ["DIY", "FS"], index=0)
    model_map = dict(DEFAULT_MODEL_MAP)
    model_map["-"] = dash_means

    st.caption("Claves: Complejo = Comentario (columna D) con contenido.")


# ==========
# Load (cache)
# ==========
@st.cache_data(ttl=60 * 30, show_spinner=True)
def load_results(_model_map_items: tuple) -> dict:
    mm = dict(_model_map_items)
    return run_all_years_from_secrets(
        service_account_info=service_account_info,
        spreadsheet_id=spreadsheet_id,
        gid_2024=gid_2024,
        gid_2025=gid_2025,
        gid_2026=gid_2026,
        header_row=header_row,
        data_start_row=data_start_row,
        model_map=mm,
    )

model_map_items = tuple(sorted(model_map.items()))
results = load_results(model_map_items)

year = st.segmented_control("Año", options=[2024, 2025, 2026], default=2026)
tables = results[year]

overview = tables["overview"]
if overview.empty:
    st.warning("No se encontraron datos para este año (o la hoja está vacía).")
    st.stop()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Ficheros", int(overview["files_count"].iloc[0]))
c2.metric("Proyectos únicos", int(overview["unique_projects"].iloc[0]))
c3.metric("Responsables", int(overview["unique_owners"].iloc[0]))
c4.metric("Tiempo total (min)", f'{overview["time_min_total"].iloc[0]:,.0f}'.replace(",", "."))
c5.metric("% Complejos", f'{overview["complex_rate"].iloc[0]*100:.1f}%')

st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Por Responsable", "Por Semana", "Por Proyecto", "Por Modelo", "Complejidad"]
)

with tab1:
    st.subheader("Estadísticas por Responsable (columna C)")
    st.dataframe(tables["by_owner"], use_container_width=True)

with tab2:
    st.subheader("Estadísticas por Semana (columna A)")
    st.dataframe(tables["by_week"], use_container_width=True)

with tab3:
    st.subheader("Estadísticas por Proyecto (columna B)")
    st.dataframe(tables["by_project"], use_container_width=True)

with tab4:
    st.subheader("Estadísticas por Modelo (columna I)")
    st.dataframe(tables["by_model"], use_container_width=True)

with tab5:
    st.subheader("Complejidad (comentario en columna D)")
    st.dataframe(tables["complexity_overview"], use_container_width=True)

st.caption("KPIs calculados automáticamente desde Google Sheets (headers fila 4, datos desde fila 5).")
