import streamlit as st

st.set_page_config(page_title="Pre Production Hub", layout="wide")

st.title("Pre Production Hub")
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

st.markdown("---")
st.info("También puedes navegar usando el menú lateral de Streamlit.")
