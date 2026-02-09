import streamlit as st

from ui_theme import apply_shared_sidebar

st.set_page_config(page_title="Configurador de altillos PAX", layout="wide")

apply_shared_sidebar()
st.markdown("<style>h1 { font-size: 2.2rem !important; }</style>", unsafe_allow_html=True)

st.title("Configurador de altillos PAX")

col_back, _ = st.columns([1, 5])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

st.caption("Herramienta que permite seleccionar dimensiones de altillos y genera un PDF con planos de altillo configurado")
