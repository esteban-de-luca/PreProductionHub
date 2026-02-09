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

tmp_in = "input_cubro.csv"
with open(tmp_in, "wb") as f:
    f.write(uploaded.getbuffer())

df = load_input_csv(tmp_in)
st.subheader("Preview input")
st.dataframe(df, use_container_width=True, height=320)

if st.button("Traducir y separar", type="primary"):
    if not os.path.exists(db_path):
        st.error(f"No existe el archivo de base ALVIC en: {db_path}")
        st.stop()

    out_m = "output_mecanizadas.csv"
    out_nm = "output_sin_mecanizar.csv"

    machined_df, non_machined_df, summary, no_match_df = translate_and_split(
        tmp_in,
        db_path,
        out_m,
        out_nm,
    )
    st.success("Listo. Se generaron dos outputs (solo piezas LAC).")

    st.subheader("Resumen")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total LAC", summary["total_lac"])
    s2.metric("Total MEC", summary["total_mec"])
    s3.metric("Total SIN MEC", summary["total_sin_mec"])
    s4.metric("Total NO_MATCH", summary["total_no_match"])

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Mecanizadas")
        st.dataframe(machined_df, use_container_width=True, height=360)
        with open(out_m, "rb") as f:
            st.download_button("Descargar mecanizadas", f, file_name=out_m, mime="text/csv")

    with c2:
        st.subheader("Sin mecanizar")
        st.dataframe(non_machined_df, use_container_width=True, height=360)
        with open(out_nm, "rb") as f:
            st.download_button("Descargar sin mecanizar", f, file_name=out_nm, mime="text/csv")

    if not no_match_df.empty:
        st.subheader("No match / pendientes")
        st.dataframe(no_match_df, use_container_width=True, height=320)
