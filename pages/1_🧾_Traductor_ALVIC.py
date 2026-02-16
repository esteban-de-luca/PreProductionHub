import csv
import io
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

from tools.alvic_verifier import find_code, format_result, load_alvic_db, normalize_code, parse_codes
from translator import translate_and_split, load_input_csv
from ui_theme import apply_shared_sidebar
from utils.gsheets_raw import build_sheet_index, read_sheet_raw

st.set_page_config(page_title="Traductor ALVIC", layout="wide")

apply_shared_sidebar("pages/1_🧾_Traductor_ALVIC.py")
st.markdown("<style>h1 { font-size: 2.2rem !important; }</style>", unsafe_allow_html=True)

st.title("🧾 Traductor ALVIC x CUBRO")

col_back, _ = st.columns([1, 5])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

st.caption("Zenit 06 · 2 outputs: mecanizadas / sin mecanizar · mínimo 100mm por lado")


verifier_db_path = repo_root / "data" / "base_datos_alvic_2026.csv"


@st.cache_data(show_spinner=False)
def _get_alvic_db(path_str: str) -> pd.DataFrame:
    return load_alvic_db(Path(path_str))


SOURCES = {
    "Fuente 1": "1WUgFlI1ea4OcWTyFGfJCcEKWBhaHIDj89GiXN02Fr2w",
    "Fuente 2": "1wa2WrV-iujiwxhiL-Q8rKYoPDcPU-eKR3k0Qc9jqxM0",
    "Fuente 3": "1GW8j6Cg__6qX0Tyh9390_XqGKZBBEk5Bvki7SF4PN7k",
    "Fuente 4": "14U-IJz4V787pLAKmKAtBq7T69GVS86GofwaFamAXN5A",
    "Fuente 5": "1pI_tVeXSFMiKYAZ33Z2_Oa3_-jHmPW5yAzYWDsFbSvQ",
}

uploaded = None
source_filter = "Todas"
search_text = ""

search_expander = st.sidebar.expander("👤 Búsqueda de proyecto", expanded=True)
with search_expander:
    input_mode = st.selectbox("Entrada", ["CSV (manual)", "Google Sheets"], key="input_mode")

    if input_mode == "CSV (manual)":
        uploaded = st.file_uploader("Sube CSV de piezas CUBRO", type=["csv"])
    else:
        if st.button("🔄 Refrescar índice"):
            build_sheet_index.clear()
            st.success("Índice de Google Sheets invalidado. Se recargará en la siguiente lectura.")

        source_options = ["Todas"] + list(SOURCES.keys())
        source_filter = st.selectbox("Fuente", options=source_options)
        search_text = st.text_input(
            "Buscar pestaña",
            placeholder="SP-… / nombre proyecto / cliente…",
        )

with st.sidebar.expander("🔎 Verificador códigos ALVIC", expanded=False):
    st.caption("Pega uno o varios códigos para ver dimensiones estándar y color (DB 2026).")
    codes_text = st.text_area(
        "Códigos ALVIC",
        height=120,
        placeholder="Ej:\nLGPUL91460278397\nLGPUL91460798397",
    )
    verify_btn = st.button("Verificar", key="verify_alvic_codes")

    if verify_btn:
        if not verifier_db_path.exists():
            st.error(f"No se encontró la base ALVIC en: {verifier_db_path}")
        else:
            df_verifier = _get_alvic_db(str(verifier_db_path))
            codes = parse_codes(codes_text)
            if not codes:
                st.warning("Pega al menos un código.")
            else:
                st.divider()
                for c in codes:
                    code_norm = normalize_code(c)
                    item = find_code(df_verifier, code_norm)
                    st.markdown(format_result(item, code_norm))
                    st.divider()

DEFAULT_DB = "data/base_datos_alvic_2026.csv"
db_path = DEFAULT_DB

if st.button("Probar base de datos"):
    try:
        df_db = _get_alvic_db(str(verifier_db_path))
        if df_db.empty:
            raise ValueError("empty_db")
        st.success("✅ Base de datos ALVIC OK.")
    except (FileNotFoundError, ValueError):
        st.error("❌ No se pudo cargar la base de datos ALVIC. Revisa que el archivo exista y sea accesible.")
    except Exception:
        st.error("❌ No se pudo cargar la base de datos ALVIC. Revisa que el archivo exista y sea accesible.")


def _clear_alvic_results() -> None:
    # Limpia el estado para forzar un nuevo cálculo.
    for key in [
        "alvic_done",
        "alvic_out_m",
        "alvic_out_nm",
        "alvic_summary",
        "alvic_no_match",
        "alvic_diag",
        "alvic_csv_m_bytes",
        "alvic_csv_nm_bytes",
    ]:
        st.session_state.pop(key, None)
    st.session_state["alvic_done"] = False


def _to_alvic_csv_bytes(df: pd.DataFrame) -> bytes:
    export_df = df.copy()
    for col in ["alargo", "aancho", "agrueso"]:
        if col in export_df.columns:
            export_df[col] = pd.to_numeric(
                export_df[col].astype(str).str.strip().str.replace(",", ".", regex=False),
                errors="coerce",
            )
    csv_buffer = io.BytesIO()
    export_df.to_csv(
        csv_buffer,
        index=False,
        sep="|",
        decimal=",",
        float_format="%.3f",
        lineterminator="\n",
        encoding="utf-8-sig",
        quoting=csv.QUOTE_NONE,
        escapechar="\\",
    )
    return csv_buffer.getvalue()


tmp_in = "input_cubro.csv"
df = st.session_state.get("input_df")
input_filename = st.session_state.get("input_filename", "input_cubro.csv")

if input_mode == "CSV (manual)":
    if not uploaded:
        st.info("Sube un CSV para comenzar.")
        st.stop()

    input_sig = ("csv", uploaded.name, uploaded.size)
    if st.session_state.get("alvic_input_sig") != input_sig:
        _clear_alvic_results()
        st.session_state["alvic_input_sig"] = input_sig

    with open(tmp_in, "wb") as f:
        f.write(uploaded.getbuffer())

    df = load_input_csv(tmp_in)
    st.session_state["input_df"] = df
    st.session_state["input_filename"] = uploaded.name
    input_filename = uploaded.name

else:
    try:
        sheets_index = build_sheet_index(SOURCES)
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()

    filtered = sheets_index.copy()
    if source_filter != "Todas":
        filtered = filtered[filtered["source_name"] == source_filter]

    query = str(search_text).strip().lower()
    filtered["sheet_title_norm"] = filtered["sheet_title"].astype(str).str.lower()
    if query:
        filtered = filtered[filtered["sheet_title_norm"].str.contains(query, na=False)]

    filtered = filtered.sort_values(["source_name", "sheet_title"]).reset_index(drop=True)

    selected_row = None
    with search_expander:
        if filtered.empty:
            st.info("No hay pestañas que coincidan con la búsqueda.")
        else:
            options = {
                f"{row.sheet_title} — {row.source_name}": idx
                for idx, row in filtered.iterrows()
            }
            selected_label = st.selectbox("Resultados", options=list(options.keys()))
            selected_row = filtered.iloc[options[selected_label]]

        load_sheet_clicked = st.button("📥 Cargar como input", type="primary")

    if selected_row is not None and load_sheet_clicked:
        sheet_title = str(selected_row["sheet_title"])
        spreadsheet_id = str(selected_row["spreadsheet_id"])
        try:
            df_raw = read_sheet_raw(spreadsheet_id, sheet_title, range_a1="A:Q")
            if df_raw.empty:
                st.warning("La pestaña no tiene datos en A:Q")
            else:
                st.session_state["input_df"] = df_raw
                st.session_state["input_filename"] = f"{sheet_title}.csv"
                st.session_state["alvic_input_sig"] = (
                    "gsheet",
                    spreadsheet_id,
                    selected_row.get("sheet_id"),
                )
                _clear_alvic_results()
                st.success("Input cargado desde Google Sheets (RAW).")
        except RuntimeError as exc:
            st.error(str(exc))

    df = st.session_state.get("input_df")
    input_filename = st.session_state.get("input_filename", "input_cubro.csv")

if df is None or df.empty:
    st.info("Carga un CSV o una pestaña de Google Sheets para continuar.")
    st.stop()

df.to_csv(tmp_in, index=False)
st.subheader("Preview input")
st.dataframe(df.head(50), use_container_width=True, height=320)
st.caption(f"Filas: {len(df)} | Columnas: {len(df.columns)}")

actions_col, clear_col = st.columns([1, 1])
with actions_col:
    run_translate = st.button("Traducir y separar", type="primary")
with clear_col:
    if st.session_state.get("alvic_done"):
        if st.button("🧹 Limpiar resultados"):
            _clear_alvic_results()

if run_translate:
    if not os.path.exists(db_path):
        st.error(f"No existe el archivo de base ALVIC en: {db_path}")
        st.stop()

    out_m = "output_mecanizadas.csv"
    out_nm = "output_sin_mecanizar.csv"

    try:
        machined_df, non_machined_df, summary, no_match_df, diag_df = translate_and_split(
            tmp_in,
            db_path,
            out_m,
            out_nm,
            input_filename=input_filename,
        )
    except TypeError as exc:
        if "unexpected keyword argument 'input_filename'" not in str(exc):
            raise
        machined_df, non_machined_df, summary, no_match_df, diag_df = translate_and_split(
            tmp_in,
            db_path,
            out_m,
            out_nm,
        )
    # Persistencia en session_state para evitar perder resultados tras downloads.
    st.session_state["alvic_out_m"] = machined_df
    st.session_state["alvic_out_nm"] = non_machined_df
    st.session_state["alvic_summary"] = summary
    st.session_state["alvic_no_match"] = no_match_df
    st.session_state["alvic_diag"] = diag_df
    st.session_state["alvic_csv_m_bytes"] = _to_alvic_csv_bytes(machined_df)
    st.session_state["alvic_csv_nm_bytes"] = _to_alvic_csv_bytes(non_machined_df)
    st.session_state["alvic_done"] = True

if st.session_state.get("alvic_done"):
    st.success("Listo. Se generaron dos outputs (solo piezas LAC).")

    project_id = ""
    for id_col in ["ID de Proyecto", "ProjectID"]:
        if id_col in df.columns:
            series = df[id_col].dropna()
            if not series.empty:
                project_id = str(series.iloc[0]).strip()
                break

    project_id = project_id.replace("/", "-").replace("\\", "-")
    input_base_name = input_filename
    if input_base_name.lower().endswith(".csv"):
        input_base_name = input_base_name[:-4]
    filename_suffix = ""
    if "_" in input_base_name:
        _, filename_suffix = input_base_name.split("_", 1)

    ref_base = f"{project_id}_{filename_suffix}" if filename_suffix else project_id
    non_mec_ref = ref_base[:20]
    mec_ref = "MEC_" + ref_base[:16]

    mec_download_name = f"{mec_ref}.csv" if mec_ref != "MEC_" else "MEC.csv"
    non_mec_download_name = f"{non_mec_ref}.csv" if non_mec_ref else "sin_mecanizar.csv"

    st.subheader("Resumen")
    summary = st.session_state["alvic_summary"]
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Total LAC", summary["total_lac"])
    s2.metric("Total MEC", summary["total_mec"])
    s3.metric("Total SIN MEC", summary["total_sin_mec"])
    s4.metric("Total NO_MATCH", summary["total_no_match"])
    s5.metric("Total BAD_DIMS", summary["total_bad_dims"])

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Mecanizadas")
        st.dataframe(st.session_state["alvic_out_m"], use_container_width=True, height=360)
        st.download_button(
            "Descargar mecanizadas",
            st.session_state["alvic_csv_m_bytes"],
            file_name=mec_download_name,
            mime="text/csv",
        )

    with c2:
        st.subheader("Sin mecanizar")
        st.dataframe(st.session_state["alvic_out_nm"], use_container_width=True, height=360)
        st.download_button(
            "Descargar sin mecanizar",
            st.session_state["alvic_csv_nm_bytes"],
            file_name=non_mec_download_name,
            mime="text/csv",
        )

    no_match_df = st.session_state["alvic_no_match"]
    if not no_match_df.empty:
        st.subheader("No match / pendientes")
        st.dataframe(no_match_df, use_container_width=True, height=320)

    st.subheader("Diagnóstico de split")
    diag_df = st.session_state["alvic_diag"]
    id_col = "ID de pieza" if "ID de pieza" in diag_df.columns else diag_df.columns[0]
    diag_cols = [
        id_col,
        "Ancho_raw",
        "Alto_raw",
        "Ancho_parsed_mm",
        "Alto_parsed_mm",
        "Es_Mecanizada",
        "Mec_reason",
        "Match_type",
        "Codigo_ALVIC",
    ]
    diag_cols = [c for c in diag_cols if c in diag_df.columns]
    st.dataframe(diag_df[diag_cols], use_container_width=True, height=360)
