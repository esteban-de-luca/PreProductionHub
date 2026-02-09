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
    st.sidebar.page_link("pages/3_📊_KPIS_Data_base.py", label="📊 KPIS & Data base")
    st.sidebar.page_link("pages/4_🗂️_Ficheros_de_corte.py", label="🗂️ Ficheros de corte")
    st.sidebar.page_link("pages/5_🧵_Stock_de_retales.py", label="🧵 Stock de retales")
    st.sidebar.page_link("pages/6_🪚_Despiece_hornacinas.py", label="🪚 Despiece hornacinas")
    st.sidebar.page_link("pages/7_🔗_Docs_Links.py", label="🔗 Docs & Links")
    st.sidebar.page_link("pages/8_🗓️_Calculadora_semana_corte.py", label="🗓️ Calculadora semana de corte")
    st.sidebar.page_link("pages/9_📐_Configurador_altillos_PAX.py", label="📐 Configurador altillos PAX")
    st.sidebar.page_link("pages/10_🧩_Configuradores_3D_Shapediver.py", label="🧩 Configuradores 3D")
    st.sidebar.markdown("---")
