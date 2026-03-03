from __future__ import annotations

from pathlib import Path

import streamlit as st

TABS = [
    {"label": "Home", "icon": "home", "page": "Home.py"},
    {"label": "Traductor ALVIC", "icon": "swap_horiz", "page": "pages/1_🧾_Traductor_ALVIC.py"},
    {"label": "Nesting", "icon": "grid_on", "page": "pages/2_🧩_Nesting_App.py"},
    {"label": "KPIs & Data Base", "icon": "bar_chart", "page": "pages/3_📊_KPIS_Data_base.py"},
    {"label": "Ficheros de corte", "icon": "folder", "page": "pages/4_🗂️_Ficheros_de_corte.py"},
    {"label": "Stock de retales", "icon": "content_cut", "page": "pages/5_🧵_Stock_de_retales.py"},
    {"label": "Despiece hornacinas", "icon": "carpenter", "page": "pages/6_🪚_Despiece_hornacinas.py"},
    {"label": "Docs & Links", "icon": "description", "page": "pages/7_🔗_Docs_Links.py"},
    {"label": "Calculadora semana corte", "icon": "event", "page": "pages/8_🗓️_Calculadora_semana_corte.py"},
    {"label": "Config altillos PAX", "icon": "straighten", "page": "pages/9_📐_Configurador_altillos_PAX.py"},
    {"label": "Configuradores 3D", "icon": "view_in_ar", "page": "pages/10_🧩_Configuradores_3D_Shapediver.py"},
    {"label": "Datos de envío", "icon": "local_shipping", "page": "pages/11_🚚_Datos_de_envío.py"},
    {"label": "Lector DXF", "icon": "architecture", "page": "pages/12_📐_Lector_DXF.py"},
    {"label": "Historial pedidos ALVIC", "icon": "inventory_2", "page": "pages/13_📦_Historial_pedidos_ALVIC.py"},
    {"label": "Inspector de proyectos", "icon": "manage_search", "page": "pages/14_🕵️_Inspector_de_proyectos.py"},
    {"label": "Análisis tipologías", "icon": "analytics", "page": "pages/15_🔎_Analisis_tipologias.py"},
]


def load_css(path: str) -> None:
    css_path = Path(path)
    if not css_path.exists():
        st.error("No se encontró assets/style_on_hover_tabs.css. Añade el CSS del repo Socvest/streamlit-on-Hover-tabs.")
        st.stop()

    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_hover_tabs(active_label: str | None = None) -> str:
    try:
        from st_on_hover_tabs import on_hover_tabs
    except ImportError:
        st.error(
            "Falta dependencia streamlit-on-Hover-tabs. Añade a requirements.txt: streamlit-on-Hover-tabs==1.0.1"
        )
        st.stop()

    load_css("assets/style_on_hover_tabs.css")

    label_to_idx = {tab["label"]: idx for idx, tab in enumerate(TABS)}
    default_idx = label_to_idx.get(active_label, 0)

    with st.sidebar:
        chosen_label = on_hover_tabs(
            tabName=[tab["label"] for tab in TABS],
            iconName=[tab["icon"] for tab in TABS],
            default_choice=default_idx,
        )
        st.markdown("---")
        st.caption("Pre Production Hub · v1.0")

    return chosen_label


def navigate_from_hover_tabs(active_label: str | None = None) -> None:
    chosen_label = render_hover_tabs(active_label=active_label)
    label_to_page = {tab["label"]: tab["page"] for tab in TABS}

    if not chosen_label:
        return

    target_page = label_to_page.get(chosen_label)
    current_page = label_to_page.get(active_label) if active_label else None

    if target_page and target_page != current_page:
        st.switch_page(target_page)
