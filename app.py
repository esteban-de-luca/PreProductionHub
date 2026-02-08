
import streamlit as st

st.set_page_config(page_title="Pre Production Hub", layout="wide")

st.title("Pre Production Hub")
st.caption("Centro de herramientas para el equipo de Pre Producción")

st.markdown("---")

# Navegación por query params (simple y robusta)
def go(page: str):
    st.query_params["page"] = page
    st.rerun()

page = st.query_params.get("page", "home")

if page == "home":
    st.subheader("Herramientas")
    st.write("Elige una herramienta para comenzar:")

    c1, c2 = st.columns(2, gap="large")

    card_css = """
    <style>
    .pph-card {
        border: 1px solid rgba(49, 51, 63, 0.2);
        border-radius: 18px;
        padding: 26px 22px;
        background: rgba(255,255,255,0.02);
        box-shadow: 0 6px 18px rgba(0,0,0,0.05);
        margin-bottom: 12px;
    }
    .pph-title { font-size: 22px; font-weight: 700; margin: 0 0 8px 0; }
    .pph-desc { font-size: 15px; opacity: 0.85; margin: 0; }
    </style>
    """
    st.markdown(card_css, unsafe_allow_html=True)

    with c1:
        st.markdown(
            """
            <div class="pph-card">
              <p class="pph-title">🧾 Traductor ALVIC x CUBRO</p>
              <p class="pph-desc">Traduce piezas LAC a códigos ALVIC y separa mecanizadas / sin mecanizar.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Abrir Traductor ALVIC", use_container_width=True):
            go("alvic")

    with c2:
        st.markdown(
            """
            <div class="pph-card">
              <p class="pph-title">🧩 NestingAppV5</p>
              <p class="pph-desc">Genera layouts/nesting y prepara descargas para producción.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Abrir NestingAppV5", use_container_width=True):
            go("nesting")

    st.markdown("---")
    st.info("Tip: si algo falla, revisa primero la pestaña de logs en Streamlit Cloud.")

elif page == "alvic":
    from tools.alvic_translator.page import render as render_alvic
    render_alvic()

elif page == "nesting":
    from tools.nestingappv5.page import render as render_nesting
    render_nesting()

else:
    st.error("Página no encontrada.")
    if st.button("Volver al inicio"):
        go("home")
