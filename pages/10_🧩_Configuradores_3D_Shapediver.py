import streamlit as st

from ui_theme import apply_shared_sidebar

st.set_page_config(page_title="Configuradores 3D (Shapediver)", layout="wide")

apply_shared_sidebar("pages/10_🧩_Configuradores_3D_Shapediver.py")
st.markdown("<style>h1 { font-size: 2.2rem !important; }</style>", unsafe_allow_html=True)

st.title("Configuradores 3D (Shapediver)")

col_back, _ = st.columns([1, 5])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

st.caption(
    "Sección para visualizar los diferentes configuradores 3D de producto utilizando Shapediver"
)
