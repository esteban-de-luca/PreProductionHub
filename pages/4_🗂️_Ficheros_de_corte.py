import streamlit as st
from ui.hover_tabs_sidebar import navigate_from_hover_tabs


st.set_page_config(page_title="Ficheros de corte", layout="wide")
navigate_from_hover_tabs("Ficheros de corte")

st.markdown("<style>h1 { font-size: 2.2rem !important; }</style>", unsafe_allow_html=True)

st.title("Ficheros de corte")

col_back, _ = st.columns([1, 5])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

st.caption("Herramienta para añadir información operativa de ficheros de corte")
