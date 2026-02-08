import streamlit as st


def apply_shared_sidebar() -> None:
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

    st.sidebar.page_link("Home.py", label="🏠 Home")
    st.sidebar.page_link("pages/1_🧾_Traductor_ALVIC.py", label="🧾 Traductor ALVIC")
    st.sidebar.page_link("pages/2_🧩_Nesting_App.py", label="🧩 Nesting App")
    st.sidebar.markdown("---")
