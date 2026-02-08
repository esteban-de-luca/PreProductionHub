from pathlib import Path

import streamlit as st

SIDEBAR_LOGO_PATH = Path("assets/logo.png")


def apply_shared_sidebar(logo_path: Path = SIDEBAR_LOGO_PATH) -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"] {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if logo_path.exists():
        st.sidebar.image(str(logo_path), use_container_width=True)

    st.sidebar.page_link("Home.py", label="🏠 Home")
    st.sidebar.page_link("pages/1_🧾_Traductor_ALVIC.py", label="🧾 Traductor ALVIC")
    st.sidebar.page_link("pages/2_🧩_Nesting_App.py", label="🧩 Nesting App")
    st.sidebar.markdown("---")
