import streamlit as st
from ui_theme import apply_shared_sidebar

st.set_page_config(page_title="Pre Production Hub", layout="wide")
apply_shared_sidebar("Home.py")

# -------------------------
# UI (la dejamos tal y como está)
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

/* Card shell (needed for overlay) */
.pph-shell { position: relative; }

/* Card */
.pph-card {
  background: var(--pph-card-bg);
  border: 1px solid var(--pph-card-border);
  border-radius: 16px;
  padding: 16px;
  height: 175px; /* fijo para todas */
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: transform 160ms ease, box-shadow 180ms ease, background 180ms ease, border-color 180ms ease;
  will-change: transform;
  cursor: pointer;
}

.pph-shell:hover .pph-card {
  background: var(--pph-card-hover-bg);
  box-shadow: var(--pph-shadow);
  transform: translateY(-1px);
  border-color: var(--pph-card-hover-border);
}

.pph-shell:active .pph-card {
  transform: translateY(0px) scale(0.992);
  box-shadow: none;
}

/* Content */
.pph-top { display: flex; gap: 10px; }
.pph-emoji { font-size: 18px; margin-top: 2px; }
.pph-title {
  font-size: 16px; font-weight: 650; margin: 0;
  color: var(--pph-title); line-height: 1.2;
}
.pph-desc {
  font-size: 13px; margin-top: 6px;
  color: var(--pph-desc); line-height: 1.35;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
  overflow: hidden;
}
.pph-cta {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 13px; font-weight: 600; color: var(--pph-cta);
}
.pph-cta span:last-child { color: var(--pph-arrow); }

/* ---- THE FIX ----
   Make st.page_link cover the whole card, invisible, but clickable
*/
.pph-shell div[data-testid="stPageLink"] {
  position: absolute;
  inset: 0;
  z-index: 10;
  margin: 0 !important;
}
.pph-shell div[data-testid="stPageLink"] a {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0;         /* invisible overlay */
  text-decoration: none !important;
}

/* Remove any extra spacing below page_link */
.pph-shell div[data-testid="stPageLink"] > div { margin: 0 !important; padding: 0 !important; }
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
# Clickable card helper (uses st.page_link overlay)
# -------------------------
def clickable_tool_card(key: str, icon: str, title: str, desc: str, page: str):
    # Open a wrapper so we can absolutely-position the page_link above the card
    st.markdown(f'<div class="pph-shell" id="pph_{key}">', unsafe_allow_html=True)

    # The visible card (unchanged UI)
    st.markdown(f"""
      <div class="pph-card">
        <div class="pph-top">
          <div class="pph-emoji">{icon}</div>
          <div>
            <p class="pph-title">{title}</p>
            <p class="pph-desc">{desc}</p>
          </div>
        </div>
        <div class="pph-cta">
          <span>Abrir herramienta</span>
          <span>→</span>
        </div>
      </div>
    """, unsafe_allow_html=True)

    # The REAL navigation (correct Streamlit routing)
    st.page_link(page, label=" ", icon=None)

    # Close wrapper
    st.markdown("</div>", unsafe_allow_html=True)


# -------------------------
# Grid (mismo orden + mismas rutas)
# -------------------------
c1, c2, c3 = st.columns(3, gap="large")

with c1:
    clickable_tool_card(
        "alvic", "🧾", "Traductor ALVIC x CUBRO",
        "Traduce piezas LAC a códigos ALVIC y separa mecanizadas / sin mecanizar.",
        "pages/1_🧾_Traductor_ALVIC.py",
    )

with c2:
    clickable_tool_card(
        "nesting", "🧩", "NestingAppV5",
        "Genera layouts/nesting y prepara descargas para producción.",
        "pages/2_🧩_Nesting_App.py",
    )

with c3:
    clickable_tool_card(
        "kpis", "📊", "KPIS & Data base",
        "Acceso a KPIS de equipo, base de datos e información de ficheros de cortes realizados.",
        "pages/3_📊_KPIS_Data_base.py",
    )

c4, c5, c6 = st.columns(3, gap="large")

with c4:
    clickable_tool_card(
        "cutfiles", "🗂️", "Ficheros de corte",
        "Herramienta para añadir información operativa de ficheros de corte.",
        "pages/4_🗂️_Ficheros_de_corte.py",
    )

with c5:
    clickable_tool_card(
        "retales", "🧵", "Stock de retales",
        "Permite consultar base de datos de retales en taller y añadir o quitar retales (marcar como utilizados).",
        "pages/5_🧵_Stock_de_retales.py",
    )

with c6:
    clickable_tool_card(
        "hornacinas", "🪚", "Despiece hornacinas",
        "Configura hornacinas y genera un despiece listo para traspasarlo al proyecto.",
        "pages/6_🪚_Despiece_hornacinas.py",
    )

c7, c8, c9 = st.columns(3, gap="large")

with c7:
    clickable_tool_card(
        "docs", "🔗", "Docs & Links",
        "Document hub y central de links importantes.",
        "pages/7_🔗_Docs_Links.py",
    )

with c8:
    clickable_tool_card(
        "weekcalc", "🗓️", "Calculadora de semana de corte",
        "Calcula la semana de corte sugerida en función de la fecha deseada de entrega o fecha de montaje asignada.",
        "pages/8_🗓️_Calculadora_semana_corte.py",
    )

with c9:
    clickable_tool_card(
        "pax", "📐", "Configurador de altillos PAX",
        "Selecciona dimensiones de altillos y genera un PDF con planos del altillo configurado.",
        "pages/9_📐_Configurador_altillos_PAX.py",
    )

c10, _, _ = st.columns(3, gap="large")

with c10:
    clickable_tool_card(
        "shapediver", "🧩", "Configuradores 3D (Shapediver)",
        "Sección para visualizar los diferentes configuradores 3D de producto utilizando Shapediver.",
        "pages/10_🧩_Configuradores_3D_Shapediver.py",
    )

st.markdown('<div class="hr-soft"></div>', unsafe_allow_html=True)
st.info("También puedes navegar usando el menú lateral de Streamlit.")
