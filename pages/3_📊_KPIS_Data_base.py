import altair as alt
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

model_map = dict(DEFAULT_MODEL_MAP)
model_map["-"] = "DIY"
debug_mode = False


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

with st.sidebar:
    if st.button("🔄 Actualizar datos", use_container_width=True):
        load_results.clear()
        st.toast("Datos actualizados desde Google Sheets.", icon="✅")
        st.rerun()

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

files_count = int(overview["files_count"].iloc[0])
boards_total = int(overview["boards_total"].iloc[0])
time_min_total = float(overview["time_min_total"].iloc[0])
time_min_avg = (time_min_total / files_count) if files_count else 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Ficheros", files_count)
c2.metric("Tableros", boards_total)
c3.metric("Responsables", int(overview["unique_owners"].iloc[0]))
c4.metric("Tiempo medio (min)", f"{time_min_avg:.1f}")
c5.metric("% Complejos", f'{overview["complex_rate"].iloc[0]*100:.1f}%')

st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Por Responsable", "Por Semana", "Por Proyecto", "Por Modelo", "Complejidad"]
)

with tab1:
    st.subheader("Estadísticas por Responsable")
    by_owner_view = tables["by_owner"].copy()
    by_owner_view["time_min_avg"] = by_owner_view["time_min_avg"].round(1)
    by_owner_view["boards_avg"] = by_owner_view["boards_avg"].map(lambda value: f"{value:.1f}")
    by_owner_view["complex_rate"] = by_owner_view["complex_rate"].map(lambda value: f"{value * 100:.1f}%")
    by_owner_view = by_owner_view.rename(
        columns={
            "owner": "Responsable",
            "files": "Ficheros",
            "time_min_avg": "Tiempo promedio",
            "boards_total": "Tableros totales",
            "boards_avg": "Tableros promedio",
            "complex_files": "Ficheros complejos",
            "complex_rate": "Complejidad media",
        }
    )
    st.dataframe(
        by_owner_view[
            [
                "Responsable",
                "Ficheros",
                "Tiempo promedio",
                "Tableros totales",
                "Tableros promedio",
                "Ficheros complejos",
                "Complejidad media",
            ]
        ],
        use_container_width=True,
    )

    chart_data = tables["by_owner"].copy()
    chart_data = chart_data.rename(
        columns={
            "owner": "Responsable",
            "files": "Ficheros",
            "time_min_avg": "Tiempo promedio",
            "boards_total": "Tableros totales",
            "boards_avg": "Tableros promedio",
            "complex_files": "Ficheros complejos",
            "complex_rate": "Complejidad media",
        }
    )
    chart_data["Complejidad media"] = chart_data["Complejidad media"] * 100

    chart_options = [
        ("Ficheros", ".0f"),
        ("Tiempo promedio", ".1f"),
        ("Tableros totales", ".0f"),
        ("Tableros promedio", ".1f"),
        ("Ficheros complejos", ".0f"),
        ("Complejidad media", ".1f"),
    ]

    if "owner_chart_index" not in st.session_state:
        st.session_state.owner_chart_index = 0

    col_prev, col_name, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.button("⬅️ Anterior", use_container_width=True):
            st.session_state.owner_chart_index = (st.session_state.owner_chart_index - 1) % len(chart_options)
    with col_next:
        if st.button("Siguiente ➡️", use_container_width=True):
            st.session_state.owner_chart_index = (st.session_state.owner_chart_index + 1) % len(chart_options)

    option_labels = [name for name, _ in chart_options]
    selected_label = col_name.selectbox(
        "Gráfico",
        options=option_labels,
        index=st.session_state.owner_chart_index,
        key="owner_chart_selector",
    )
    st.session_state.owner_chart_index = option_labels.index(selected_label)

    selected_metric, selected_format = chart_options[st.session_state.owner_chart_index]
    chart_title = f"{selected_metric} por Responsable"

    chart_sorted = chart_data[["Responsable", selected_metric]].sort_values(selected_metric, ascending=False)

    metric_tooltip = ["Responsable", alt.Tooltip(f"{selected_metric}:Q", format=selected_format)]
    if selected_metric == "Complejidad media":
        metric_tooltip = [
            "Responsable",
            alt.Tooltip(f"{selected_metric}:Q", format=selected_format, title="Complejidad media (%)"),
        ]

    metric_chart = alt.Chart(chart_sorted).mark_bar().encode(
        x=alt.X("Responsable:N", sort="-y", title="Responsable"),
        y=alt.Y(f"{selected_metric}:Q", title=selected_metric),
        tooltip=metric_tooltip,
    )

    if selected_metric == "Complejidad media":
        labels = metric_chart.mark_text(
            align="center",
            baseline="bottom",
            dy=-4,
        ).transform_calculate(label=f"format(datum['{selected_metric}'], '.1f') + '%'").encode(
            text="label:N"
        )
    else:
        labels = metric_chart.mark_text(
            align="center",
            baseline="bottom",
            dy=-4,
        ).encode(text=alt.Text(f"{selected_metric}:Q", format=selected_format))

    st.subheader(chart_title)
    st.altair_chart(metric_chart + labels, use_container_width=True)

with tab2:
    st.subheader("Estadísticas por Semana")
    by_week_view = tables["by_week"].copy()
    by_week_view = by_week_view.rename(
        columns={
            "week": "Semana",
            "files": "Ficheros",
            "time_min_avg": "Tiempo promedio",
            "boards_total": "Tableros totales",
            "boards_avg": "Tableros promedio",
            "complex_files": "Proyectos complejos",
            "complex_rate": "Complejidad media",
        }
    )
    st.dataframe(
        by_week_view[
            [
                "Semana",
                "Ficheros",
                "Tiempo promedio",
                "Tableros totales",
                "Tableros promedio",
                "Proyectos complejos",
                "Complejidad media",
            ]
        ],
        use_container_width=True,
    )

with tab3:
    st.subheader("Estadísticas por Proyecto")
    st.dataframe(tables["by_project"], use_container_width=True)

with tab4:
    st.subheader("Estadísticas por Modelo")
    st.dataframe(tables["by_model"], use_container_width=True)

with tab5:
    st.subheader("Complejidad")
    st.dataframe(tables["complexity_overview"], use_container_width=True)
