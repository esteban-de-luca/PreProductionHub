import streamlit as st
from ui_theme import apply_shared_sidebar

st.set_page_config(page_title="Pre Production Hub", layout="wide")
apply_shared_sidebar("Home.py")

# -------------------------
# UI (NO CAMBIADA)
# -------------------------
st.markdown("""
<style>
/* Layout */
.block-container { padding-top: 1.6rem; padding-bottom: 2.2rem; max-width: 1250px; }
h1 { font-size: 2.25rem !important; letter-spacing: -0.02em; }

/* Divider */
.hr-soft { height: 1px; border: 0; background: rgba(0,0,0,0.08); margin: 0.9rem 0 1.2rem 0; }

/* Theme tokens (Light default) */
:root {
  --pph-card-bg: #F6F6F7;
  --pph-card-border: rgba(0,0,0,0.06);
  --pph-card-hover-bg: #FFFFFF;
  --pph-card-hover-border: rgba(0,0,0,0.10);
  --pph-shadow: 0 10px 28px rgba(0,0,0,0.08);
  --pph-title: rgba(0,0,0,0.92);
  --pph-desc: rgba(0,0,0,0.62);
  --pph-cta: rgba(0,0,0,0.78);
  --pph-arrow: rgba(0,0,0,0.45);
  --pph-divider: rgba(0,0,0,0.08);
}

/* Auto Dark Mode */
@media (prefers-color-scheme: dark) {
  :root {
    --pph-card-bg: rgba(255,255,255,0.06);
    --pph-card-border: rgba(255,255,255,0.10);
    --pph-card-hover-bg: rgba(255,255,255,0.10);
    --pph-card-hover-border: rgba(255,255,255,0.16);
    --pph-shadow: 0 12px 34px rgba(0,0,0,0.45);
    --pph-title: rgba(255,255,255,0.92);
    --pph-desc: rgba(255,255,255,0.65);
    --pph-cta: rgba(255,255,255,0.78);
    --pph-arrow: rgba(255,255,255,0.45);
    --pph-divider: rgba(255,255,255,0.12);
  }
  .hr-soft { background: var(--pph-divider) !important; }
}

/* ---- Page link styled as card ---- */
div[data-testid="stPageLink"] { margin: 0 !important; padding: 0 !important; }

div[data-testid="stPageLink"] a {
  display: flex !important;
  flex-direction: column !important;
  justify-content: space-between !important;

  background: var(--pph-card-bg) !important;
  border: 1px solid var(--pph-card-border) !important;
  border-radius: 16px !important;
  padding: 16px !important;

  height: 175px !important; /* tamaño fijo para todas */

  text-decoration: none !important;
  color: inherit !important;

  white-space: pre-line !important; /* 👈 FIX TEXTO PLANO */

  transition: transform 160ms ease, box-shadow 180ms ease, background 180ms ease, border-color 180ms ease !important;
  will-change: transform;
  cursor: pointer;
}

/* Hover */
div[data-testid="stPageLink"] a:hover {
  background: var(--pph-card-hover-bg) !important;
  box-shadow: var(--pph-shadow) !important;
  transform: translateY(-1px) !important;
  border-color: var(--pph-card-hover-border) !important;
}

/* Active */
div[data-testid="stPageLink"] a:active {
  transform: translateY(0px) scale(0.992) !important;
  box-shadow: none !important;
}
</style>
""", unsafe_allow_html=True)

# -------------------------
# Header
# -------------------------
st.title("🏠 Pre Production Hub")
st.caption("Centro de herramientas para el equipo de Pre Producción")
st.markdown('<div class="hr-soft"></div>', unsafe_allow_html=True)
st.subheader("Herramientas")

# -------------------------
# Grid (MISMO ORDEN / MISMAS RUTAS)
# -------------------------
c1, c2, c3 = st.columns(3, gap="large")

with c1:
    st.page_link(
        "pages/1_🧾_Traductor_ALVIC.py",
        label="🧾 Traductor ALVIC x CUBRO\n"
              "Traduce piezas LAC a códigos ALVIC y separa mecanizadas / sin mecanizar.\n\n"
              "Abrir herramienta  →"
    )

with c2:
    st.page_link(
        "pages/2_🧩_Nesting_App.py",
        label="🧩 NestingAppV5\n"
              "Genera layouts/nesting y prepara descargas para producción.\n\n"
              "Abrir herramienta  →"
    )

with c3:
    st.page_link(
        "pages/3_📊_KPIS_Data_base.py",
        label="📊 KPIS & Data base\n"
              "Acceso a KPIS de equipo, base de datos e información de ficheros de cortes realizados.\n\n"
              "Abrir herramienta  →"
    )

c4, c5, c6 = st.columns(3, gap="large")

with c4:
    st.page_link(
        "pages/4_🗂️_Ficheros_de_corte.py",
        label="🗂️ Ficheros de corte\n"
              "Herramienta para añadir información operativa de ficheros de corte.\n\n"
              "Abrir herramienta  →"
    )

with c5:
    st.page_link(
        "pages/5_🧵_Stock_de_retales.py",
        label="🧵 Stock de retales\n"
              "Permite consultar base de datos de retales en taller y añadir o quitar retales.\n\n"
              "Abrir herramienta  →"
    )

with c6:
    st.page_link(
        "pages/6_🪚_Despiece_hornacinas.py",
        label="🪚 Despiece hornacinas\n"
              "Configura hornacinas y genera un despiece listo para traspasarlo al proyecto.\n\n"
              "Abrir herramienta  →"
    )

c7, c8, c9 = st.columns(3, gap="large")

with c7:
    st.page_link(
        "pages/7_🔗_Docs_Links.py",
        label="🔗 Docs & Links\n"
              "Document hub y central de links importantes.\n\n"
              "Abrir herramienta  →"
    )

with c8:
    st.page_link(
        "pages/8_🗓️_Calculadora_semana_corte.py",
        label="🗓️ Calculadora de semana de corte\n"
              "Calcula la semana de corte sugerida en función de la fecha deseada de entrega.\n\n"
              "Abrir herramienta  →"
    )

with c9:
    st.page_link(
        "pages/9_📐_Configurador_altillos_PAX.py",
        label="📐 Configurador de altillos PAX\n"
              "Selecciona dimensiones de altillos y genera un PDF con planos del altillo configurado.\n\n"
              "Abrir herramienta  →"
    )

c10, _, _ = st.columns(3, gap="large")

with c10:
    st.page_link(
        "pages/10_🧩_Configuradores_3D_Shapediver.py",
        label="🧩 Configuradores 3D (Shapediver)\n"
              "Visualiza los diferentes configuradores 3D de producto utilizando Shapediver.\n\n"
              "Abrir herramienta  →"
    )

st.markdown('<div class="hr-soft"></div>', unsafe_allow_html=True)
st.info("También puedes navegar usando el menú lateral de Streamlit.")

