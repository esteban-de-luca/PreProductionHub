import altair as alt
import pandas as pd
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

    chart_data = tables["by_owner"].copy().rename(
        columns={
            "owner": "Responsable",
            "files": "Ficheros",
            "time_min_avg": "Tiempo promedio",
            "complex_rate": "Complejidad media",
        }
    )
    chart_data["Complejidad media"] = chart_data["Complejidad media"] * 100

    def build_owner_chart(dataframe, metric, title, color, number_format):
        chart_source = dataframe[["Responsable", metric]].sort_values(metric, ascending=False)
        base_chart = alt.Chart(chart_source).mark_bar(color=color).encode(
            x=alt.X("Responsable:N", sort="-y", title="Responsable"),
            y=alt.Y(f"{metric}:Q", title=title),
            tooltip=["Responsable", alt.Tooltip(f"{metric}:Q", format=number_format)],
        )

        if metric == "Complejidad media":
            labels = base_chart.mark_text(align="center", baseline="bottom", dy=-4, color="white").transform_calculate(
                label="format(datum['Complejidad media'], '.1f') + '%'"
            ).encode(text="label:N")
        else:
            labels = base_chart.mark_text(align="center", baseline="bottom", dy=-4, color="white").encode(
                text=alt.Text(f"{metric}:Q", format=number_format)
            )

        return base_chart + labels

    st.subheader("Gráficos por Responsable")
    chart_col_1, chart_col_2, chart_col_3 = st.columns(3)

    with chart_col_1:
        st.markdown("**Ficheros**")
        st.altair_chart(
            build_owner_chart(
                chart_data,
                metric="Ficheros",
                title="Ficheros",
                color="#A8D8EA",
                number_format=".0f",
            ),
            use_container_width=True,
        )

    with chart_col_2:
        st.markdown("**Tiempo promedio**")
        st.altair_chart(
            build_owner_chart(
                chart_data,
                metric="Tiempo promedio",
                title="Tiempo promedio",
                color="#AAE3B5",
                number_format=".1f",
            ),
            use_container_width=True,
        )

    with chart_col_3:
        st.markdown("**Complejidad media**")
        st.altair_chart(
            build_owner_chart(
                chart_data,
                metric="Complejidad media",
                title="Complejidad media (%)",
                color="#F7C8E0",
                number_format=".1f",
            ),
            use_container_width=True,
        )

with tab2:
    st.subheader("Estadísticas por Semana")
    by_week_view = tables["by_week"].copy()
    by_week_view["time_min_avg"] = by_week_view["time_min_avg"].round(1)
    by_week_view["boards_avg"] = by_week_view["boards_avg"].map(lambda value: f"{value:.1f}")
    by_week_view["complex_rate"] = by_week_view["complex_rate"].map(lambda value: f"{value * 100:.1f}%")
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

    week_chart_data = tables["by_week"].copy().rename(
        columns={
            "week": "Semana",
            "files": "Ficheros",
            "time_min_avg": "Tiempo promedio",
            "complex_rate": "Complejidad media",
        }
    )
    week_chart_data["Complejidad media"] = week_chart_data["Complejidad media"] * 100

    def build_week_chart(dataframe, metric, title, color, number_format):
        chart_source = dataframe[["Semana", metric]].sort_values("Semana")
        base_chart = alt.Chart(chart_source).mark_bar(color=color).encode(
            x=alt.X("Semana:N", sort="ascending", title="Semana"),
            y=alt.Y(f"{metric}:Q", title=title),
            tooltip=["Semana", alt.Tooltip(f"{metric}:Q", format=number_format)],
        )

        if metric == "Complejidad media":
            labels = base_chart.mark_text(align="center", baseline="bottom", dy=-4, color="white").transform_calculate(
                label="format(datum['Complejidad media'], '.1f') + '%'"
            ).encode(text="label:N")
        else:
            labels = base_chart.mark_text(align="center", baseline="bottom", dy=-4, color="white").encode(
                text=alt.Text(f"{metric}:Q", format=number_format)
            )

        return base_chart + labels

    st.subheader("Gráficos por Semana")
    week_chart_col_1, week_chart_col_2, week_chart_col_3 = st.columns(3)

    with week_chart_col_1:
        st.markdown("**Ficheros**")
        st.altair_chart(
            build_week_chart(
                week_chart_data,
                metric="Ficheros",
                title="Ficheros",
                color="#CDE7BE",
                number_format=".0f",
            ),
            use_container_width=True,
        )

    with week_chart_col_2:
        st.markdown("**Tiempo promedio**")
        st.altair_chart(
            build_week_chart(
                week_chart_data,
                metric="Tiempo promedio",
                title="Tiempo promedio",
                color="#B5EAEA",
                number_format=".1f",
            ),
            use_container_width=True,
        )

    with week_chart_col_3:
        st.markdown("**Complejidad media**")
        st.altair_chart(
            build_week_chart(
                week_chart_data,
                metric="Complejidad media",
                title="Complejidad media (%)",
                color="#FFCBCB",
                number_format=".1f",
            ),
            use_container_width=True,
        )

with tab3:
    st.subheader("Estadísticas por Proyecto")
    by_project_view = tables["by_project"].copy()

    if "time_min_total" in by_project_view.columns:
        time_minutes = pd.to_numeric(by_project_view["time_min_total"], errors="coerce")

        def format_total_time(value: float) -> str:
            if pd.isna(value):
                return ""
            total_minutes = int(round(value))
            hours = total_minutes // 60
            minutes = total_minutes % 60
            return f"{hours}:{minutes:02d} hs"

        by_project_view["time_min_total"] = time_minutes.map(format_total_time)

    if "complex_files" in by_project_view.columns:
        def format_complex_flag(value) -> str:
            if pd.isna(value):
                return ""
            return "Si" if bool(value) else "No"

        by_project_view["complex_files"] = by_project_view["complex_files"].map(format_complex_flag)

    by_project_view = by_project_view.drop(
        columns=["files", "time_min_avg", "boards_avg", "complex_rate"],
        errors="ignore",
    )

    by_project_view = by_project_view.rename(
        columns={
            "owners": "Responsable",
            "project_id": "Proyecto",
            "weeks": "Semana",
            "time_min_total": "Tiempo total",
            "boards_total": "Tableros totales",
            "complex_files": "Proyecto complejo?",
            "model": "Modelo",
        }
    )

    project_columns_order = [
        "Proyecto",
        "Responsable",
        "Modelo",
        "Semana",
        "Tableros totales",
        "Tiempo total",
        "Proyecto complejo?",
    ]
    visible_project_columns = [column for column in project_columns_order if column in by_project_view.columns]

    st.dataframe(by_project_view[visible_project_columns], use_container_width=True)

with tab4:
    st.subheader("Estadísticas por Modelo")
    by_model_raw = tables["by_model"].copy()
    by_model_view = by_model_raw.copy()

    if "time_min_avg" in by_model_view.columns:
        def format_time_avg(value: float) -> str:
            if pd.isna(value):
                return ""
            return f"{round(value, 1):.1f}".replace(".", ",")

        by_model_view["time_min_avg"] = by_model_view["time_min_avg"].map(format_time_avg)

    if "complex_rate" in by_model_view.columns:
        def format_complex_rate(value: float) -> str:
            if pd.isna(value):
                return ""
            rate_pct = round(value * 100, 1)
            return f"{rate_pct:.1f}%".replace(".", ",")

        by_model_view["complex_rate"] = by_model_view["complex_rate"].map(format_complex_rate)

    if "boards_avg" in by_model_view.columns:
        def format_boards_avg_model(value: float) -> str:
            if pd.isna(value):
                return ""
            return f"{round(value, 2):.2f}".replace(".", ",")

        by_model_view["boards_avg"] = by_model_view["boards_avg"].map(format_boards_avg_model)

    by_model_view = by_model_view.drop(columns=["unique_projects", "time_min_total"], errors="ignore")

    by_model_view = by_model_view.rename(
        columns={
            "model": "Modelo",
            "files": "Cantidad",
            "time_min_avg": "Tiempo medio",
            "boards_total": "Tableros totales",
            "boards_avg": "Tableros promedio",
            "complex_files": "Proyectos complejos",
            "complex_rate": "Rate de complejidad",
        }
    )

    model_columns_order = [
        "Modelo",
        "Cantidad",
        "Tiempo medio",
        "Tableros totales",
        "Tableros promedio",
        "Proyectos complejos",
        "Rate de complejidad",
    ]
    visible_model_columns = [column for column in model_columns_order if column in by_model_view.columns]

    st.dataframe(by_model_view[visible_model_columns], use_container_width=True)

    model_chart_data = by_model_raw.copy()
    if "model" in model_chart_data.columns:
        model_chart_data = model_chart_data[model_chart_data["model"].notna()].copy()
        model_chart_data["model"] = model_chart_data["model"].astype(str).str.strip()
        model_chart_data = model_chart_data[model_chart_data["model"] != ""]

    model_order = sorted(model_chart_data["model"].unique().tolist()) if "model" in model_chart_data.columns else []

    base_model_palette = ["#A8D8EA", "#AAE3B5", "#F7C8E0"]
    model_palette = base_model_palette + ["#FFD6A5"]
    model_color_range = [model_palette[index % len(model_palette)] for index, _ in enumerate(model_order)]

    def build_model_chart(dataframe, metric, title, number_format):
        chart_source = dataframe[["model", metric]].dropna(subset=[metric]).copy()
        chart_source = chart_source.sort_values("model")

        base_chart = alt.Chart(chart_source).mark_bar().encode(
            x=alt.X("model:N", sort=model_order, title="Modelo"),
            y=alt.Y(f"{metric}:Q", title=title),
            color=alt.Color(
                "model:N",
                scale=alt.Scale(domain=model_order, range=model_color_range),
                legend=None,
            ),
            tooltip=["model", alt.Tooltip(f"{metric}:Q", format=number_format)],
        )

        if metric == "complex_rate_pct":
            labels = base_chart.mark_text(align="center", baseline="bottom", dy=-4, color="white").transform_calculate(
                label="format(datum['complex_rate_pct'], '.1f') + '%'"
            ).encode(text="label:N")
        else:
            labels = base_chart.mark_text(align="center", baseline="bottom", dy=-4, color="white").encode(
                text=alt.Text(f"{metric}:Q", format=number_format)
            )

        return base_chart + labels

    if {"model", "files", "time_min_avg", "boards_avg", "complex_rate"}.issubset(model_chart_data.columns):
        model_chart_data = model_chart_data.copy()
        model_chart_data["complex_rate_pct"] = model_chart_data["complex_rate"] * 100

        st.subheader("Gráficos por Modelo")
        model_chart_col_1, model_chart_col_2, model_chart_col_3, model_chart_col_4 = st.columns(4)

        with model_chart_col_1:
            st.markdown("**Cantidad**")
            st.altair_chart(
                build_model_chart(
                    model_chart_data,
                    metric="files",
                    title="Cantidad",
                    number_format=".0f",
                ),
                use_container_width=True,
            )

        with model_chart_col_2:
            st.markdown("**Tiempo medio**")
            st.altair_chart(
                build_model_chart(
                    model_chart_data,
                    metric="time_min_avg",
                    title="Tiempo medio",
                    number_format=".1f",
                ),
                use_container_width=True,
            )

        with model_chart_col_3:
            st.markdown("**Tableros promedio**")
            st.altair_chart(
                build_model_chart(
                    model_chart_data,
                    metric="boards_avg",
                    title="Tableros promedio",
                    number_format=".2f",
                ),
                use_container_width=True,
            )

        with model_chart_col_4:
            st.markdown("**Ratio de complejidad**")
            st.altair_chart(
                build_model_chart(
                    model_chart_data,
                    metric="complex_rate_pct",
                    title="Ratio de complejidad (%)",
                    number_format=".1f",
                ),
                use_container_width=True,
            )

with tab5:
    st.subheader("Complejidad")
    complexity_raw = tables["complexity_overview"].copy()
    complexity_view = complexity_raw.copy()

    complexity_labels = {
        "NON_COMPLEX": "Basic",
        "COMPLEX": "Complejo",
    }

    def map_complexity_label(value) -> str:
        if pd.isna(value):
            return ""
        original_value = str(value)
        normalized_value = original_value.strip().upper()
        return complexity_labels.get(normalized_value, original_value)

    if "complexity" in complexity_view.columns:
        complexity_view["complexity"] = complexity_view["complexity"].map(map_complexity_label)

    if "time_min_avg" in complexity_view.columns:
        def format_time_avg(value: float) -> str:
            if pd.isna(value):
                return ""
            return f"{round(value, 1):.1f}".replace(".", ",")

        complexity_view["time_min_avg"] = complexity_view["time_min_avg"].map(format_time_avg)

    if "boards_avg" in complexity_view.columns:
        def format_boards_avg(value: float) -> str:
            if pd.isna(value):
                return ""
            return f"{round(value, 2):.2f}".replace(".", ",")

        complexity_view["boards_avg"] = complexity_view["boards_avg"].map(format_boards_avg)

    complexity_view = complexity_view.rename(
        columns={
            "complexity": "Complejidad",
            "files": "Cantidad de proyectos",
            "time_min_total": "Tiempo total (min).",
            "time_min_avg": "Tiempo medio (min).",
            "boars_total": "Tableros totales",
            "boards_avg": "Tableros promedio",
        }
    )

    complexity_columns_order = [
        "Complejidad",
        "Cantidad de proyectos",
        "Tiempo total (min).",
        "Tiempo medio (min).",
        "Tableros totales",
        "Tableros promedio",
    ]
    visible_complexity_columns = [column for column in complexity_columns_order if column in complexity_view.columns]

    st.dataframe(complexity_view[visible_complexity_columns], use_container_width=True)

    complexity_chart_data = complexity_raw.copy()
    if "complexity" in complexity_chart_data.columns:
        complexity_chart_data["complexity"] = complexity_chart_data["complexity"].map(map_complexity_label)
        complexity_chart_data = complexity_chart_data[complexity_chart_data["complexity"].notna()].copy()
        complexity_chart_data["complexity"] = complexity_chart_data["complexity"].astype(str).str.strip()
        complexity_chart_data = complexity_chart_data[complexity_chart_data["complexity"] != ""]

    complexity_values = complexity_chart_data["complexity"].tolist() if "complexity" in complexity_chart_data.columns else []
    complexity_order = [category for category in ["Basic", "Complejo"] if category in complexity_values]
    if not complexity_order and "complexity" in complexity_chart_data.columns:
        complexity_order = sorted(complexity_chart_data["complexity"].unique().tolist())

    base_model_palette = ["#A8D8EA", "#AAE3B5", "#F7C8E0"]
    model_palette = base_model_palette + ["#FFD6A5"]
    complexity_color_range = [model_palette[index % len(model_palette)] for index, _ in enumerate(complexity_order)]

    def build_complexity_chart(dataframe, metric, title, number_format):
        chart_source = dataframe[["complexity", metric]].dropna(subset=[metric]).copy()
        chart_source = chart_source.sort_values("complexity")

        base_chart = alt.Chart(chart_source).mark_bar().encode(
            x=alt.X("complexity:N", sort=complexity_order, title="Complejidad"),
            y=alt.Y(f"{metric}:Q", title=title),
            color=alt.Color(
                "complexity:N",
                scale=alt.Scale(domain=complexity_order, range=complexity_color_range),
                legend=None,
            ),
            tooltip=["complexity", alt.Tooltip(f"{metric}:Q", format=number_format)],
        )

        labels = base_chart.mark_text(align="center", baseline="bottom", dy=-4, color="white").encode(
            text=alt.Text(f"{metric}:Q", format=number_format)
        )

        return base_chart + labels

    required_complexity_columns = {"complexity", "files", "time_min_total", "time_min_avg", "boards_avg"}
    if required_complexity_columns.issubset(complexity_chart_data.columns):
        st.subheader("Gráficos de Complejidad")
        complexity_col_1, complexity_col_2, complexity_col_3, complexity_col_4 = st.columns(4)

        with complexity_col_1:
            st.markdown("**Cantidad de proyectos**")
            st.altair_chart(
                build_complexity_chart(
                    complexity_chart_data,
                    metric="files",
                    title="Cantidad de proyectos",
                    number_format=".0f",
                ),
                use_container_width=True,
            )

        with complexity_col_2:
            st.markdown("**Tiempo total**")
            st.altair_chart(
                build_complexity_chart(
                    complexity_chart_data,
                    metric="time_min_total",
                    title="Tiempo total (min).",
                    number_format=".1f",
                ),
                use_container_width=True,
            )

        with complexity_col_3:
            st.markdown("**Tiempo medio**")
            st.altair_chart(
                build_complexity_chart(
                    complexity_chart_data,
                    metric="time_min_avg",
                    title="Tiempo medio (min).",
                    number_format=".1f",
                ),
                use_container_width=True,
            )

        with complexity_col_4:
            st.markdown("**Tableros promedio**")
            st.altair_chart(
                build_complexity_chart(
                    complexity_chart_data,
                    metric="boards_avg",
                    title="Tableros promedio",
                    number_format=".2f",
                ),
                use_container_width=True,
            )
