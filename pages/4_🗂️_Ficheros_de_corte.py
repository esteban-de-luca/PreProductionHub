import streamlit as st

from ui_theme import apply_shared_sidebar

st.set_page_config(page_title="Ficheros de corte", layout="wide")

apply_shared_sidebar("pages/4_🗂️_Ficheros_de_corte.py")
st.markdown("<style>h1 { font-size: 2.2rem !important; }</style>", unsafe_allow_html=True)

st.title("Ficheros de corte")

col_back, _ = st.columns([1, 5])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

st.caption("Herramienta para añadir información operativa de ficheros de corte")
