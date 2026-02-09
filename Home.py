import streamlit as st
from ui_theme import apply_shared_sidebar

st.set_page_config(page_title="Pre Production Hub", layout="wide")
apply_shared_sidebar("Home.py")

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

/* ---- st.page_link styled as card ---- */
div[data-testid="stPageLink"] { margin: 0 !important; padding: 0 !important; }

div[data-testid="stPageLink"] a {
  display: flex !important;
  flex-direction: column !important;
  justify-content: space-between !important;

  background: var(--pph-card-bg) !important;
  border: 1px solid var(--pph-card-border) !important;
  border-radius: 16px !important;
  padding: 16px !important;

  height: 175px !important; /* fijo para todas */

  text-decoration: none !important;
  color: inherit !important;

  transition: transform 160ms ease, box-shadow 180ms ease, background 180ms ease, border-color 180ms ease !important;
  will-change: transform;
  cursor: pointer;
}

div[data-testid="stPageLink"] a:hover {
  background: var(--pph-card-hover-bg) !important;
  box-shadow: var(--pph-shadow) !important;
  transform: translateY(-1px) !important;
  border-color: var(--pph-card-hover-border) !important;
}

div[data-testid="stPageLink"] a:active {
  transform: translateY(0px) scale(0.992) !important;
  box-shadow: none !important;
}

/* ---- Text layout inside the card (THIS is the "nice text" fix) ---- */
div[data-testid="stPageLink"] a p {
  margin: 0 !important;
  padding: 0 !important;
}

/* Title paragraph (1st) */
div[data-testid="stPageLink"] a p:first-child {
  font-size: 16px !important;
  font-weight: 650 !important;
  color: var(--pph-title) !important;
  letter-spacing: -0.01em !important;
  line-height: 1.2 !important;
}

/* Title bold (if markdown strong is used) */
div[data-testid="stPageLink"] a p:first-child strong {
  font-weight: 650 !important;
}

/* Description paragraph (2nd) */
div[data-testid="stPageLink"] a p:nth-child(2) {
  margin-top: 8px !important;
  font-size: 13px !important;
  color: var(--pph-desc) !important;
  line-height: 1.35 !important;

  display: -webkit-box !important;
  -webkit-line-clamp: 3 !important;
  -webkit-box-orient: vertical !important;
  overflow: hidden !important;
}

/* CTA paragraph (last) pinned to bottom */
div[data-testid="stPageLink"] a p:last-child {
  margin-top: auto !important;
  padding-top: 10px !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  color: var(--pph-cta) !important;

  display: flex !important;
  justify-content: space-between !important;
  align-items: center !important;
}

/* Add the arrow via CSS so we can align it perfectly */
div[data-testid="stPageLink"] a p:last-child::after {
  content: "→";
  color: var(--pph-arrow);
  font-size: 15px;
  font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

st.title("🏠 Pre Production Hub")
st.caption("Centro de herramientas para el equipo de Pre Producción")
st.markdown('<div class="hr-soft"></div>', unsafe_allow_html=True)
st.subheader("Herramientas")

def card_label(title: str, desc: str) -> str:
    # 3 paragraphs (Markdown): Title / Description / CTA
    # Esto permite al CSS maquetar “bonito” dentro de la tarjeta.
    return f"**{title}**\n\n{desc}\n\nAbrir herramienta"

c1, c2, c3 = st.columns(3, gap="large")

with c1:
    st.page_link(
        "pages/1_🧾_Traductor_ALVIC.py",
        label=card_label("🧾 Traductor ALVIC x CUBRO",
                         "Traduce piezas LAC a códigos ALVIC y separa mecanizadas / sin mecanizar.")
    )

with c2:
    st.page_link(
        "pages/2_🧩_Nesting_App.py",
        label=card_label("🧩 NestingAppV5",
                         "Genera layouts/nesting y prepara descargas para producción.")
    )

with c3:
    st.page_link(
        "pages/3_📊_KPIS_Data_base.py",
        label=card_label("📊 KPIS & Data base",
                         "Acceso a KPIS de equipo, base de datos e información de ficheros de cortes realizados.")
    )

c4, c5, c6 = st.columns(3, gap="large")

with c4:
    st.page_link(
        "pages/4_🗂️_Ficheros_de_corte.py",
        label=card_label("🗂️ Ficheros de corte",
                         "Herramienta para añadir información operativa de ficheros de corte.")
    )

with c5:
    st.page_link(
        "pages/5_🧵_Stock_de_retales.py",
        label=card_label("🧵 Stock de retales",
                         "Permite consultar base de datos de retales en taller y añadir o quitar retales (marcar como utilizados).")
    )

with c6:
    st.page_link(
        "pages/6_🪚_Despiece_hornacinas.py",
        label=card_label("🪚 Despiece hornacinas",
                         "Herramienta que permite configurar hornacinas y generar un despiece listo para traspasarlo al proyecto.")
    )

c7, c8, c9 = st.columns(3, gap="large")

with c7:
    st.page_link(
        "pages/7_🔗_Docs_Links.py",
        label=card_label("🔗 Docs & Links",
                         "Document hub y central de links importantes.")
    )

with c8:
    st.page_link(
        "pages/8_🗓️_Calculadora_semana_corte.py",
        label=card_label("🗓️ Calculadora de semana de corte",
                         "Herramienta para calcular la semana de corte sugerida en función de la fecha deseada de entrega o fecha de montaje asignada.")
    )

with c9:
    st.page_link(
        "pages/9_📐_Configurador_altillos_PAX.py",
        label=card_label("📐 Configurador de altillos PAX",
                         "Herramienta que permite seleccionar dimensiones de altillos y genera un PDF con planos de altillo configurado.")
    )

c10, _, _ = st.columns(3, gap="large")

with c10:
    st.page_link(
        "pages/10_🧩_Configuradores_3D_Shapediver.py",
        label=card_label("🧩 Configuradores 3D (Shapediver)",
                         "Sección para visualizar los diferentes configuradores 3D de producto utilizando Shapediver.")
    )

st.markdown('<div class="hr-soft"></div>', unsafe_allow_html=True)
st.info("También puedes navegar usando el menú lateral de Streamlit.")
