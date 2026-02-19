from __future__ import annotations

from datetime import datetime
import io

import pandas as pd
import streamlit as st

from ui_theme import apply_shared_sidebar
from utils.gsheets_raw import read_sheet_raw

SHEET_ID = "1hV37nMLVBeLFapn0bsIlKlDq9LWq52wg5M44Zw5bRH4"
MUEBLES_WORKSHEET = "muebles_cache"
TIPOLOGIAS_WORKSHEET = "Tipologias"
REQUIRED_COLUMNS = ["project_id", "categoria"]

st.set_page_config(page_title="Análisis de tipologías", layout="wide")
apply_shared_sidebar("pages/15_🔎_Analisis_tipologias.py")
st.title("🔎 Análisis de tipologías")
st.caption("Fuente: Google Sheet cache de muebles. Incluye split de tipologías y matriz por proyecto.")


@st.cache_data(ttl=3600, show_spinner=True)
def load_worksheet(spreadsheet_id: str, worksheet_name: str) -> pd.DataFrame:
    raw_df = read_sheet_raw(spreadsheet_id, worksheet_name, range_a1="A:ZZ")
    if raw_df.empty:
        return pd.DataFrame()

    headers = raw_df.iloc[0].astype(str).str.strip().tolist()
    body = raw_df.iloc[1:].copy().reset_index(drop=True)
    body.columns = headers
    body = body.dropna(how="all")
    return body


@st.cache_data(ttl=3600)
def prepare_tipologias_options(df_tipologias: pd.DataFrame) -> list[tuple[str, str]]:
    if df_tipologias.empty:
        return []

    cols = list(df_tipologias.columns)
    code_col = "Abreviatura" if "Abreviatura" in cols else cols[0]
    name_col = "Nombre completo" if "Nombre completo" in cols else (cols[1] if len(cols) > 1 else cols[0])

    options: list[tuple[str, str]] = []
    for _, row in df_tipologias.iterrows():
        code = str(row.get(code_col, "")).strip()
        name = str(row.get(name_col, "")).strip()
        if not code:
            continue
        label = f"{code} — {name}" if name else code
        options.append((code, label))

    dedup: dict[str, str] = {}
    for code, label in options:
        dedup[code] = label

    return sorted(dedup.items(), key=lambda item: item[0])


@st.cache_data(ttl=3600)
def add_calculated_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["project_id"] = out.get("project_id", "").astype(str).str.strip()
    out["categoria"] = out.get("categoria", "").astype(str).str.strip()

    confidence_series = out.get("confidence", "")
    confidence_clean = confidence_series.astype(str).str.replace(",", ".", regex=False).str.strip()
    out["confidence_num"] = pd.to_numeric(confidence_clean, errors="coerce")

    n_cajones_num = pd.to_numeric(out.get("n_cajones"), errors="coerce")
    alto_max_num = pd.to_numeric(out.get("alto_max_mm"), errors="coerce")
    alto_total_num = pd.to_numeric(out.get("alto_total_mm"), errors="coerce")

    out["tipologia_split"] = out["categoria"]

    mask_mbc = out["categoria"].eq("MB-C")
    valid_drawers = n_cajones_num.isin([1, 2, 3, 4])
    out.loc[mask_mbc & valid_drawers, "tipologia_split"] = (
        "MB-" + n_cajones_num[mask_mbc & valid_drawers].astype("Int64").astype(str) + "C"
    )
    out.loc[mask_mbc & ~valid_drawers, "tipologia_split"] = "MB-C-UNK"

    mask_mpr = out["categoria"].eq("MP-R")
    mp_r_height_cm = (alto_max_num / 10).round()
    out.loc[mask_mpr & mp_r_height_cm.notna(), "tipologia_split"] = (
        "MP-R" + mp_r_height_cm[mask_mpr & mp_r_height_cm.notna()].astype("Int64").astype(str)
    )
    out.loc[mask_mpr & mp_r_height_cm.isna(), "tipologia_split"] = "MP-RUNK"

    mask_man = out["categoria"].eq("MA-N")
    ma_n_height_cm = (alto_total_num / 10).round()
    out.loc[mask_man & ma_n_height_cm.notna(), "tipologia_split"] = (
        "MA-N" + ma_n_height_cm[mask_man & ma_n_height_cm.notna()].astype("Int64").astype(str)
    )
    out.loc[mask_man & ma_n_height_cm.isna(), "tipologia_split"] = "MA-NUNK"

    out.loc[out["categoria"].eq("MB-E"), "tipologia_split"] = "MB-E"
    return out


@st.cache_data(ttl=3600)
def build_summary(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    total_projects = df["project_id"].nunique()
    grouped = (
        df.groupby(group_col, dropna=False)
        .agg(
            total_apariciones=("project_id", "count"),
            proyectos_con_presencia=("project_id", "nunique"),
        )
        .reset_index()
        .rename(columns={group_col: "tipologia"})
    )
    grouped["porcentaje_proyectos"] = (
        grouped["proyectos_con_presencia"] / total_projects if total_projects else 0
    )
    grouped["promedio_por_proyecto"] = (
        grouped["total_apariciones"] / total_projects if total_projects else 0
    )
    return grouped.sort_values("total_apariciones", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=3600)
def build_pivot(df: pd.DataFrame) -> pd.DataFrame:
    return pd.pivot_table(
        df,
        index="project_id",
        columns="tipologia_split",
        values="categoria",
        aggfunc="count",
        fill_value=0,
    ).reset_index()


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def dataframe_to_html(df: pd.DataFrame, max_rows: int | None = None) -> str:
    view = df.head(max_rows) if max_rows else df
    return view.to_html(index=False, border=0, justify="left")


@st.cache_data(ttl=3600)
def build_html_report(
    generated_at: str,
    kpis: dict[str, str | int | float],
    base_summary: pd.DataFrame,
    split_summary: pd.DataFrame,
    unk_summary: pd.DataFrame,
    pivot_df: pd.DataFrame,
) -> str:
    kpi_html = "".join(
        [f"<li><strong>{name}:</strong> {value}</li>" for name, value in kpis.items()]
    )

    return f"""
<!DOCTYPE html>
<html lang=\"es\">
<head>
  <meta charset=\"UTF-8\" />
  <title>Informe de tipologías</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #222; }}
    h1, h2 {{ color: #113355; }}
    table {{ border-collapse: collapse; width: 100%; margin: 10px 0 24px 0; }}
    th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; font-size: 12px; }}
    th {{ background: #f2f2f2; }}
    ul {{ margin-top: 0; }}
    .note {{ color: #444; font-size: 12px; }}
  </style>
</head>
<body>
  <h1>🔎 Informe de análisis de tipologías</h1>
  <p><strong>Generado:</strong> {generated_at}</p>

  <h2>KPIs globales</h2>
  <ul>{kpi_html}</ul>

  <h2>Resumen por tipología base</h2>
  {dataframe_to_html(base_summary)}

  <h2>Resumen por tipología split</h2>
  {dataframe_to_html(split_summary)}

  <h2>Calidad de split (UNK)</h2>
  {dataframe_to_html(unk_summary)}

  <h2>Matriz proyecto x tipología split (top columnas)</h2>
  <p class=\"note\">Se incluyen hasta 20 columnas de tipología para mantener un HTML liviano.</p>
  {dataframe_to_html(pivot_df)}
</body>
</html>
"""


with st.sidebar:
    st.subheader("Filtros")
    if st.button("🔄 Recargar datos", use_container_width=True):
        st.cache_data.clear()
        st.toast("Cache invalidada. Recargando…", icon="✅")
        st.rerun()

try:
    muebles_df = load_worksheet(SHEET_ID, MUEBLES_WORKSHEET)
    tipologias_df = load_worksheet(SHEET_ID, TIPOLOGIAS_WORKSHEET)
except Exception as exc:
    st.error("No se pudo leer Google Sheets. Revisa credenciales/permisos e inténtalo de nuevo.")
    st.exception(exc)
    st.stop()

if muebles_df.empty:
    st.warning("La hoja 'muebles_cache' está vacía o no tiene datos utilizables.")
    st.stop()

missing_required = [col for col in REQUIRED_COLUMNS if col not in muebles_df.columns]
if missing_required:
    st.error(f"Faltan columnas obligatorias en 'muebles_cache': {', '.join(missing_required)}")
    st.stop()

working_df = add_calculated_columns(muebles_df)

if "tipologia_split" not in working_df.columns:
    st.error("No se pudo calcular la columna tipologia_split.")
    st.stop()

options = prepare_tipologias_options(tipologias_df)
option_codes = [code for code, _ in options]
option_labels = {code: label for code, label in options}

with st.sidebar:
    selected_tipologias = st.multiselect(
        "Tipologías (base)",
        options=option_codes,
        format_func=lambda item: option_labels.get(item, item),
    )
    apply_to_split = st.toggle("Aplicar filtro a tipología split", value=False)

    project_options = ["Todos"] + sorted(working_df["project_id"].dropna().astype(str).unique().tolist())
    selected_project = st.selectbox("Proyecto (detalle opcional)", options=project_options)

    min_apparitions = st.slider(
        "Mostrar solo columnas con al menos N apariciones",
        min_value=1,
        max_value=max(1, int(len(working_df))),
        value=1,
        step=1,
    )

filtered_df = working_df.copy()
if selected_tipologias:
    if apply_to_split:
        selected_set = tuple(selected_tipologias)
        filtered_df = filtered_df[
            filtered_df["tipologia_split"].astype(str).apply(
                lambda value: any(value.startswith(code) for code in selected_set)
            )
        ]
    else:
        filtered_df = filtered_df[filtered_df["categoria"].isin(selected_tipologias)]

if selected_project != "Todos":
    filtered_df = filtered_df[filtered_df["project_id"] == selected_project]

if filtered_df.empty:
    st.warning("No hay datos para la combinación de filtros seleccionada.")
    st.stop()

total_projects = int(filtered_df["project_id"].nunique())
total_rows = int(len(filtered_df))
base_unique = int(filtered_df["categoria"].nunique())
split_unique = int(filtered_df["tipologia_split"].nunique())
unk_pct = float(filtered_df["tipologia_split"].astype(str).str.contains("UNK", na=False).mean() * 100)

base_summary = build_summary(filtered_df, "categoria")
split_summary = build_summary(filtered_df, "tipologia_split")
unk_breakdown = (
    filtered_df[filtered_df["tipologia_split"].astype(str).str.contains("UNK", na=False)]
    .groupby("tipologia_split")
    .size()
    .reset_index(name="total_apariciones")
    .sort_values("total_apariciones", ascending=False)
)

pivot_df = build_pivot(filtered_df)
pivot_totals = pivot_df.drop(columns=["project_id"]).sum(axis=0)
cols_keep = ["project_id"] + pivot_totals[pivot_totals >= min_apparitions].index.tolist()
pivot_filtered = pivot_df[cols_keep]

tab_resumen, tab_matriz, tab_export = st.tabs(["Resumen", "Matriz", "Informe/Export"])

with tab_resumen:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total proyectos", total_projects)
    c2.metric("Total muebles", total_rows)
    c3.metric("Tipologías base únicas", base_unique)
    c4.metric("Tipologías split únicas", split_unique)

    st.info("Split no disponible actualmente: MB-E 198/298 y MB-C por ancho 40/60/80 (no existen esos datos en el cache).")

    q1, q2 = st.columns([1, 2])
    q1.metric("% filas con UNK", f"{unk_pct:.2f}%")
    q2.dataframe(unk_breakdown, use_container_width=True, hide_index=True)

    st.subheader("Resumen por tipología base")
    st.dataframe(base_summary, use_container_width=True, hide_index=True)

    st.subheader("Resumen por tipología split")
    st.dataframe(split_summary, use_container_width=True, hide_index=True)

    st.subheader("Datos enriquecidos (preview)")
    preview_cols = [col for col in ["project_id", "categoria", "tipologia_split", "n_cajones", "alto_total_mm", "alto_max_mm", "confidence", "confidence_num", "rule_id", "razon"] if col in filtered_df.columns]
    st.dataframe(filtered_df[preview_cols].head(200), use_container_width=True, hide_index=True)

with tab_matriz:
    st.caption("Conteo de muebles por proyecto y tipología split.")
    with st.expander("Matriz por proyecto (tipología split)", expanded=True):
        st.dataframe(pivot_filtered, use_container_width=True, hide_index=True)

with tab_export:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kpi_dict = {
        "Total proyectos": total_projects,
        "Total muebles": total_rows,
        "Tipologías base únicas": base_unique,
        "Tipologías split únicas": split_unique,
        "% filas con UNK": f"{unk_pct:.2f}%",
    }

    top_columns = ["project_id"]
    ordered_split_cols = pivot_totals.sort_values(ascending=False).index.tolist()
    top_columns.extend(ordered_split_cols[:20])
    pivot_top20 = pivot_df[[col for col in top_columns if col in pivot_df.columns]]

    if st.button("Generar informe", type="primary", use_container_width=True):
        st.session_state["tipologias_html_report"] = build_html_report(
            generated_at=generated_at,
            kpis=kpi_dict,
            base_summary=base_summary,
            split_summary=split_summary,
            unk_summary=unk_breakdown,
            pivot_df=pivot_top20,
        )
        st.success("Informe generado. Ya puedes descargarlo.")

    html_report = st.session_state.get("tipologias_html_report")

    st.download_button(
        "⬇️ Descargar CSV resumen tipología base",
        data=dataframe_to_csv_bytes(base_summary),
        file_name="resumen_tipologia_base.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.download_button(
        "⬇️ Descargar CSV resumen tipología split",
        data=dataframe_to_csv_bytes(split_summary),
        file_name="resumen_tipologia_split.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.download_button(
        "⬇️ Descargar CSV matriz proyecto_x_tipologia_split",
        data=dataframe_to_csv_bytes(pivot_df),
        file_name="matriz_proyecto_tipologia_split.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.download_button(
        "⬇️ Descargar informe HTML",
        data=io.BytesIO((html_report or "").encode("utf-8")),
        file_name="informe_analisis_tipologias.html",
        mime="text/html",
        use_container_width=True,
        disabled=html_report is None,
    )
