import streamlit as st

from ui_theme import apply_shared_sidebar

st.set_page_config(page_title="KPIS & Data base", layout="wide")

apply_shared_sidebar()
st.markdown("<style>h1 { font-size: 2.2rem !important; }</style>", unsafe_allow_html=True)

st.title("KPIS & Data base")

col_back, _ = st.columns([1, 5])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

st.caption("Acceso a KPIS de equipo, base de datos e información de ficheros de cortes realizados")
