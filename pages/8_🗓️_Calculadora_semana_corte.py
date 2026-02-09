import streamlit as st

from ui_theme import apply_shared_sidebar

st.set_page_config(page_title="Calculadora de semana de corte", layout="wide")

apply_shared_sidebar("pages/8_🗓️_Calculadora_semana_corte.py")
st.markdown("<style>h1 { font-size: 2.2rem !important; }</style>", unsafe_allow_html=True)

st.title("Calculadora de semana de corte")

col_back, _ = st.columns([1, 5])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

st.caption(
    "Herramienta para calcular la semana de corte sugerida en función de la fecha deseada de entrega o fecha de montaje asignada"
)
