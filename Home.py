import streamlit as st

from ui_theme import apply_shared_sidebar

st.set_page_config(page_title="Pre Production Hub", layout="wide")

apply_shared_sidebar()
st.markdown("<style>h1 { font-size: 2.3rem !important; }</style>", unsafe_allow_html=True)

st.title("🏠 Pre Production Hub")
st.caption("Centro de herramientas para el equipo de Pre Producción")

st.markdown("---")
st.subheader("Herramientas")

# Estilo tarjeta
st.markdown("""
<style>
.pph-card {
  border: 1px solid rgba(49, 51, 63, 0.2);
  border-radius: 18px;
  padding: 26px 22px;
  background: rgba(255,255,255,0.02);
  box-shadow: 0 6px 18px rgba(0,0,0,0.05);
}
.pph-title { font-size: 22px; font-weight: 700; margin: 0 0 8px 0; }
.pph-desc { font-size: 15px; opacity: 0.85; margin: 0; }
</style>
""", unsafe_allow_html=True)

c1, c2 = st.columns(2, gap="large")

with c1:
    st.markdown("""
    <div class="pph-card">
      <p class="pph-title">🧾 Traductor ALVIC x CUBRO</p>
      <p class="pph-desc">Traduce piezas LAC a códigos ALVIC y separa mecanizadas / sin mecanizar.</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir Traductor ALVIC", use_container_width=True, type="primary"):
        st.switch_page("pages/1_🧾_Traductor_ALVIC.py")

with c2:
    st.markdown("""
    <div class="pph-card">
      <p class="pph-title">🧩 NestingAppV5</p>
      <p class="pph-desc">Genera layouts/nesting y prepara descargas para producción.</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir NestingAppV5", use_container_width=True, type="primary"):
        st.switch_page("pages/2_🧩_Nesting_App.py")

c3, c4 = st.columns(2, gap="large")

with c3:
    st.markdown("""
    <div class="pph-card">
      <p class="pph-title">KPIS & Data base</p>
      <p class="pph-desc">Acceso a KPIS de equipo, base de datos e información de ficheros de cortes realizados</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir KPIS & Data base", use_container_width=True, type="primary"):
        st.switch_page("pages/3_📊_KPIS_Data_base.py")

with c4:
    st.markdown("""
    <div class="pph-card">
      <p class="pph-title">Ficheros de corte</p>
      <p class="pph-desc">Herramienta para añadir información operativa de ficheros de corte</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir Ficheros de corte", use_container_width=True, type="primary"):
        st.switch_page("pages/4_🗂️_Ficheros_de_corte.py")

c5, c6 = st.columns(2, gap="large")

with c5:
    st.markdown("""
    <div class="pph-card">
      <p class="pph-title">Stock de retales</p>
      <p class="pph-desc">Permite consultar base de datos de retales en taller y añadir o quitar retales (marcar como utilizados)</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir Stock de retales", use_container_width=True, type="primary"):
        st.switch_page("pages/5_🧵_Stock_de_retales.py")

with c6:
    st.markdown("""
    <div class="pph-card">
      <p class="pph-title">Despiece hornacinas</p>
      <p class="pph-desc">Herramienta que permite configurar hornacinas y generar un despiece listo para traspasarlo al proyecto</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir Despiece hornacinas", use_container_width=True, type="primary"):
        st.switch_page("pages/6_🪚_Despiece_hornacinas.py")

c7, c8 = st.columns(2, gap="large")

with c7:
    st.markdown("""
    <div class="pph-card">
      <p class="pph-title">Docs & Links</p>
      <p class="pph-desc">Document hub y central de links importantes</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir Docs & Links", use_container_width=True, type="primary"):
        st.switch_page("pages/7_🔗_Docs_Links.py")

with c8:
    st.markdown("""
    <div class="pph-card">
      <p class="pph-title">Calculadora de semana de corte</p>
      <p class="pph-desc">Herramienta para calcular la semana de corte sugerida en función de la fecha deseada de entrega o fecha de montaje asignada</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir Calculadora de semana de corte", use_container_width=True, type="primary"):
        st.switch_page("pages/8_🗓️_Calculadora_semana_corte.py")

c9, c10 = st.columns(2, gap="large")

with c9:
    st.markdown("""
    <div class="pph-card">
      <p class="pph-title">Configurador de altillos PAX</p>
      <p class="pph-desc">Herramienta que permite seleccionar dimensiones de altillos y genera un PDF con planos de altillo configurado</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir Configurador de altillos PAX", use_container_width=True, type="primary"):
        st.switch_page("pages/9_📐_Configurador_altillos_PAX.py")

with c10:
    st.markdown("""
    <div class="pph-card">
      <p class="pph-title">Configuradores 3D (Shapediver)</p>
      <p class="pph-desc">Sección para visualizar los diferentes configuradores 3D de producto utilizando Shapediver</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Abrir Configuradores 3D (Shapediver)", use_container_width=True, type="primary"):
        st.switch_page("pages/10_🧩_Configuradores_3D_Shapediver.py")

st.markdown("---")
st.info("También puedes navegar usando el menú lateral de Streamlit.")
