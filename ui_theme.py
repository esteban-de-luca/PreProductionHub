from pathlib import Path

import streamlit as st

SIDEBAR_LOGO_PATH = Path("assets/logo.svg")


def apply_shared_sidebar(logo_path: Path = SIDEBAR_LOGO_PATH) -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {
            background-color: rgb(166, 166, 166);
        }

        [data-testid="stSidebarNav"] a,
        [data-testid="stSidebarNav"] span {
            color: #111111 !important;
            font-size: 1.15rem !important;
            font-weight: 700 !important;
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div {
            color: #111111;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if logo_path.exists():
        st.sidebar.image(str(logo_path), use_container_width=True)
