import streamlit as st
from pathlib import Path


def apply_shared_sidebar(current_page: str = "Home.py") -> None:
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

    # --- LOGO CUBRO (añadido) ---
    with st.sidebar:
        logo_path = Path(__file__).parent / "assets" / "cubro_logo.png"
        st.image(str(logo_path), use_container_width=True)
        st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)
    # --- FIN LOGO ---

    tool_pages = [
        ("🏠 Home", "Home.py"),
        ("🧾 Traductor ALVIC", "pages/1_🧾_Traductor_ALVIC.py"),
        ("🧩 Nesting App", "pages/2_🧩_Nesting_App.py"),
        ("📊 KPIS & Data base", "pages/3_📊_KPIS_Data_base.py"),
        ("🗂️ Ficheros de corte", "pages/4_🗂️_Ficheros_de_corte.py"),
        ("🧵 Stock de retales", "pages/5_🧵_Stock_de_retales.py"),
        ("🪚 Despiece hornacinas", "pages/6_🪚_Despiece_hornacinas.py"),
        ("🔗 Docs & Links", "pages/7_🔗_Docs_Links.py"),
        ("🗓️ Calculadora semana de corte", "pages/8_🗓️_Calculadora_semana_corte.py"),
        ("📐 Configurador altillos PAX", "pages/9_📐_Configurador_altillos_PAX.py"),
        ("🧩 Configuradores 3D", "pages/10_🧩_Configuradores_3D_Shapediver.py"),
    ]

    tool_paths = [path for _, path in tool_pages]
    tool_labels = {path: label for label, path in tool_pages}
    current_index = tool_paths.index(current_page) if current_page in tool_paths else 0

    selected_page = st.sidebar.selectbox(
        "Acceso rápido",
        options=tool_paths,
        index=current_index,
        format_func=lambda path: tool_labels.get(path, path),
    )

    if selected_page != current_page:
        st.switch_page(selected_page)

    st.sidebar.markdown("---")
