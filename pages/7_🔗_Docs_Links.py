import streamlit as st

from ui_theme import apply_shared_sidebar

st.set_page_config(page_title="Docs & Links", layout="wide")

apply_shared_sidebar("pages/7_🔗_Docs_Links.py")
st.markdown("<style>h1 { font-size: 2.2rem !important; }</style>", unsafe_allow_html=True)

st.title("Docs & Links")

col_back, _ = st.columns([1, 5])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

st.caption("Document hub y central de links importantes")
