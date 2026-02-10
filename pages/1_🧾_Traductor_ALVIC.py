import os
import streamlit as st
import pandas as pd

from translator import translate_and_split, load_input_csv
from ui_theme import apply_shared_sidebar

st.set_page_config(page_title="Traductor ALVIC", layout="wide")

apply_shared_sidebar("pages/1_🧾_Traductor_ALVIC.py")
st.markdown("<style>h1 { font-size: 2.2rem !important; }</style>", unsafe_allow_html=True)

st.title("🧾 Traductor ALVIC x CUBRO")

col_back, _ = st.columns([1, 5])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

st.caption("Zenit 06 · 2 outputs: mecanizadas / sin mecanizar · mínimo 100mm por lado")

DEFAULT_DB = "data/base_datos_alvic_2026.csv"
db_path = st.text_input("Ruta base ALVIC", value=DEFAULT_DB)

if st.button("🧪 Probar lectura base ALVIC"):
    if not os.path.exists(db_path):
        st.error(f"No existe el archivo: {db_path}")
    else:
        df_db = pd.read_csv(db_path)
        st.success(f"OK: {len(df_db)} filas | {len(df_db.columns)} columnas")
        st.dataframe(df_db.head(20), use_container_width=True)

uploaded = st.file_uploader("Sube CSV de piezas CUBRO", type=["csv"])
if not uploaded:
    st.info("Sube un CSV para comenzar.")
    st.stop()

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

input_sig = (uploaded.name, uploaded.size)
if st.session_state.get("alvic_input_sig") != input_sig:
    _clear_alvic_results()
    st.session_state["alvic_input_sig"] = input_sig

tmp_in = "input_cubro.csv"
with open(tmp_in, "wb") as f:
    f.write(uploaded.getbuffer())

df = load_input_csv(tmp_in)
st.subheader("Preview input")
st.dataframe(df, use_container_width=True, height=320)

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
            input_filename=uploaded.name,
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
    st.session_state["alvic_csv_m_bytes"] = machined_df.to_csv(index=False).encode("utf-8")
    st.session_state["alvic_csv_nm_bytes"] = non_machined_df.to_csv(index=False).encode("utf-8")
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
    input_base_name = uploaded.name
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
