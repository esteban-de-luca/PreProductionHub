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

/* Theme tokens */
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

/* Page link as card */
div[data-testid="stPageLink"] { margin: 0 !important; padding: 0 !important; }

div[data-testid="stPageLink"] a {
  display: flex !important;
  flex-direction: column !important;
  justify-content: space-between !important;

  background: var(--pph-card-bg) !important;
  border: 1px solid var(--pph-card-border) !important;
  border-radius: 16px !important;
  padding: 16px !important;

  height: 175px !important;

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

/* ---- Text layout inside the link (plain text label) ----
We force typography and simulate: Title / Description / CTA.
Streamlit puts the label text inside the <a> as a text node.
We keep new lines, then style via pseudo layout using <p> not available.
So we use these rules:
- Make the whole <a> use pre-line.
- Use a fixed line-height.
- Make title visually strong by adding top padding and using first line via small trick:
  We set all text to desc style, then overlay a "title" effect by making the first line appear larger
  using background-clip is unreliable, so we use a safer approach:
  Put title as the first line and keep it short; make description shorter; keep CTA last line.
*/
div[data-testid="stPageLink"] a {
  white-space: pre-line !important;
  line-height: 1.25 !important;
  font-size: 13px !important;
  color: var(--pph-desc) !important;
}

/* Make the first line (title) look like a title:
   We can't select first line reliably across Streamlit DOM changes, but ::first-line is standard.
*/
div[data-testid="stPageLink"] a::first-line {
  font-size: 16px !important;
  font-weight: 650 !important;
  color: var(--pph-title) !important;
  letter-spacing: -0.01em !important;
}

/* Make CTA (last line) sit visually at bottom:
   We'll reserve space by adding bottom padding and use a divider feel with spacing in the label.
*/
</style>
""", unsafe_allow_html=True)

st.title("🏠 Pre Production Hub")
st.caption("Centro de herramientas para el equipo de Pre Producción")
st.markdown('<div class="hr-soft"></div>', unsafe_allow_html=True)
st.subheader("Herramientas")

# Helper: compose label text with controlled length
def label_text(title: str, desc: str) -> str:
    # Keep description tight so it fits. (Cards are fixed height.)
    # We'll rely on authoring: max ~110 chars tends to fit nicely with 3-4 lines.
    return f"{title}\n{desc}\n\nAbrir herramienta  →"

c1, c2, c3 = st.columns(3, gap="large")
with c1:
    st.page_link("pages/1_🧾_Traductor_ALVIC.py",
                 label=label_text("🧾 Traductor ALVIC x CUBRO",
                                  "Traduce piezas LAC a códigos ALVIC y separa mecanizadas / sin mecanizar."))
with c2:
    st.page_link("pages/2_🧩_Nesting_App.py",
                 label=label_text("🧩 NestingAppV5",
                                  "Genera layouts/nesting y prepara descargas para producción."))
with c3:
    st.page_link("pages/3_📊_KPIS_Data_base.py",
                 label=label_text("📊 KPIS & Data base",
                                  "Acceso a KPIs de equipo, base de datos e info de ficheros de corte."))

c4, c5, c6 = st.columns(3, gap="large")
with c4:
    st.page_link("pages/4_🗂️_Ficheros_de_corte.py",
                 label=label_text("🗂️ Ficheros de corte",
                                  "Añade información operativa de ficheros de corte."))
with c5:
    st.page_link("pages/5_🧵_Stock_de_retales.py",
                 label=label_text("🧵 Stock de retales",
                                  "Consulta retales en taller y marca retales como utilizados."))
with c6:
    st.page_link("pages/6_🪚_Despiece_hornacinas.py",
                 label=label_text("🪚 Despiece hornacinas",
                                  "Configura hornacinas y genera un despiece listo para el proyecto."))

c7, c8, c9 = st.columns(3, gap="large")
with c7:
    st.page_link("pages/7_🔗_Docs_Links.py",
                 label=label_text("🔗 Docs & Links",
                                  "Document hub y central de links importantes."))
with c8:
    st.page_link("pages/8_🗓️_Calculadora_semana_corte.py",
                 label=label_text("🗓️ Calculadora de semana de corte",
                                  "Calcula la semana de corte sugerida según fecha de entrega/montaje."))
with c9:
    st.page_link("pages/9_📐_Configurador_altillos_PAX.py",
                 label=label_text("📐 Configurador de altillos PAX",
                                  "Selecciona dimensiones y genera un PDF con planos del altillo."))

c10, _, _ = st.columns(3, gap="large")
with c10:
    st.page_link("pages/10_🧩_Configuradores_3D_Shapediver.py",
                 label=label_text("🧩 Configuradores 3D (Shapediver)",
                                  "Visualiza configuradores 3D de producto utilizando Shapediver."))

st.markdown('<div class="hr-soft"></div>', unsafe_allow_html=True)
st.info("También puedes navegar usando el menú lateral de Streamlit.")
