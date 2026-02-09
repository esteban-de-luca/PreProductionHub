import streamlit as st

from ui_theme import apply_shared_sidebar

st.set_page_config(page_title="Stock de retales", layout="wide")

apply_shared_sidebar("pages/5_🧵_Stock_de_retales.py")
st.markdown("<style>h1 { font-size: 2.2rem !important; }</style>", unsafe_allow_html=True)

st.title("Stock de retales")

col_back, _ = st.columns([1, 5])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

st.caption("Permite consultar base de datos de retales en taller y añadir o quitar retales (marcar como utilizados)")
