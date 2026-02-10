import streamlit as st

from src.kpis.kpi_sheets_analyzer import run_all_years_from_secrets, DEFAULT_MODEL_MAP
from ui_theme import apply_shared_sidebar

st.set_page_config(page_title="KPIs & Data base", layout="wide")
apply_shared_sidebar("pages/3_📊_KPIS_Data_base.py")
st.title("📊 KPIs — Ficheros de corte")

# ==========
# Secrets
# ==========
if "kpis" not in st.secrets:
    st.error("No encuentro [kpis] en Secrets.")
    st.stop()

k = st.secrets["kpis"]

# Credenciales (ajusta si tu bloque se llama distinto)
if "gcp_service_account" in st.secrets:
    service_account_info = st.secrets["gcp_service_account"]
else:
    st.error("No encuentro [gcp_service_account] en Secrets (Service Account).")
    st.stop()

spreadsheet_id = k["ficheros_corte_sheet_id"]
gid_2024 = int(k["gid_2024"])
gid_2025 = int(k["gid_2025"])
gid_2026 = int(k["gid_2026"])
header_row = int(k.get("header_row", 4))
data_start_row = int(k.get("data_start_row", 5))

with st.sidebar:
    st.header("Ajustes KPIs")

    dash_means = st.selectbox("Cómo interpretar “-” en Modelo", ["DIY", "FS"], index=0)
    model_map = dict(DEFAULT_MODEL_MAP)
    model_map["-"] = dash_means

    debug_mode = st.toggle("Modo diagnóstico (si hay errores de columnas)", value=False)

    st.caption("Complejo = Comentario (columna D) con contenido.")


@st.cache_data(ttl=60 * 30, show_spinner=True)
def load_results(_model_map_items: tuple, _debug: bool) -> dict:
    mm = dict(_model_map_items)

    # Si quieres fijar columnas manualmente, aquí puedes poner overrides (opcional)
    # Ejemplo:
    # overrides = {"project_id": "ID Proyecto (B)"}
    overrides = None

    return run_all_years_from_secrets(
        service_account_info=service_account_info,
        spreadsheet_id=spreadsheet_id,
        gid_2024=gid_2024,
        gid_2025=gid_2025,
        gid_2026=gid_2026,
        header_row=header_row,
        data_start_row=data_start_row,
        model_map=mm,
        column_overrides=overrides,
    )

model_map_items = tuple(sorted(model_map.items()))

try:
    results = load_results(model_map_items, debug_mode)
except Exception as e:
    st.error("Error cargando KPIs.")
    st.exception(e)
    st.stop()

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
    st.subheader("Estadísticas por Responsable")
    st.dataframe(tables["by_owner"], use_container_width=True)

with tab2:
    st.subheader("Estadísticas por Semana")
    st.dataframe(tables["by_week"], use_container_width=True)

with tab3:
    st.subheader("Estadísticas por Proyecto")
    st.dataframe(tables["by_project"], use_container_width=True)

with tab4:
    st.subheader("Estadísticas por Modelo")
    st.dataframe(tables["by_model"], use_container_width=True)

with tab5:
    st.subheader("Complejidad")
    st.dataframe(tables["complexity_overview"], use_container_width=True)

st.caption("KPIs desde Google Sheets (headers fila 4, datos fila 5+).")

