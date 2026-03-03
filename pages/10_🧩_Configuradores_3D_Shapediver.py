import streamlit as st
import streamlit.components.v1 as components
from ui.hover_tabs_sidebar import navigate_from_hover_tabs


st.set_page_config(page_title="Configuradores 3D (Shapediver)", layout="wide")
navigate_from_hover_tabs("Configuradores 3D")

st.markdown("<style>h1 { font-size: 2.2rem !important; }</style>", unsafe_allow_html=True)

st.title("Configuradores 3D (Shapediver)")

col_back, _ = st.columns([1, 5])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

st.caption(
    "Sección para visualizar los diferentes configuradores 3D de producto utilizando Shapediver"
)

CONFIGURADORES = {
    "CUBRO · Muebles abiertos": (
        "https://www.shapediver.com/app/iframe/cubro-muebles-abiertos"
        "?primaryColor=%23317DD4&secondaryColor=%23393A45&surfaceColor=%23FFFFFF"
        "&backgroundColor=%23F8F8F8&showControls=1&showZoomButton=1"
        "&showFullscreenButton=1&showToggleControlsButton=1"
        "&hideDataOutputsIframe=1&hideAttributeVisualizationIframe=1"
        "&parametersDisable=1&parametersValidation=0"
    ),
    "CUBRO · Configurador de cómodas": (
        "https://www.shapediver.com/app/iframe/cubro-configurador-comodas"
        "?primaryColor=%23317DD4&secondaryColor=%23393A45&surfaceColor=%23FFFFFF"
        "&backgroundColor=%23F8F8F8&showControls=1&showZoomButton=1"
        "&showFullscreenButton=1&showToggleControlsButton=1"
        "&hideDataOutputsIframe=1&hideAttributeVisualizationIframe=1"
        "&parametersDisable=1&parametersValidation=0"
    ),
    "CUBRO · Configurador de baños": (
        "https://www.shapediver.com/app/iframe/banos-cubro-shapediver-v2"
        "?primaryColor=%23317DD4&secondaryColor=%23393A45&surfaceColor=%23FFFFFF"
        "&backgroundColor=%23F8F8F8&showControls=1&showZoomButton=1"
        "&showFullscreenButton=1&showToggleControlsButton=1"
        "&hideDataOutputsIframe=1&hideAttributeVisualizationIframe=1"
        "&parametersDisable=1&parametersValidation=0"
    ),
}

st.subheader("Selecciona un configurador")
configurador_seleccionado = st.selectbox(
    "Configurador",
    options=list(CONFIGURADORES.keys()),
)
st.info("Añade nuevos configuradores incorporando una nueva entrada en CONFIGURADORES.")

configurador_url = CONFIGURADORES[configurador_seleccionado]
components.html(
    f"""
    <div style="width:100%; height:80vh;">
      <iframe
        src="{configurador_url}"
        style="width:100%; height:100%; border:0; border-radius:12px;"
        allowfullscreen
      ></iframe>
    </div>
    """,
    height=800,
    scrolling=False,
)
