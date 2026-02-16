import streamlit as st
from ui_theme import apply_shared_sidebar
from urllib.parse import quote

st.set_page_config(page_title="Pre Production Hub", layout="wide")
apply_shared_sidebar("Home.py")

# -------------------------
# FIX navegación: usar query param ?go=... y luego st.switch_page
# -------------------------
go = st.query_params.get("go")
if go:
    # st.query_params puede devolver str o list según versión
    page = go[0] if isinstance(go, list) else go
    try:
        st.query_params.clear()
    except Exception:
        st.query_params["go"] = ""
    st.switch_page(page)

# -------------------------
# UI (la dejamos como estaba: hover/active + dark auto + texto)
# -------------------------
st.markdown("""
<style>
/* Layout */
.block-container { padding-top: 1.6rem; padding-bottom: 2.2rem; max-width: 1250px; }
h1 { font-size: 2.25rem !important; letter-spacing: -0.02em; }

/* Divider */
.hr-soft { height: 1px; border: 0; background: rgba(0,0,0,0.08); margin: 0.9rem 0 1.2rem 0; }

/* Theme tokens (Dark mode DEFAULT) */
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

/* Card as link */
a.pph-card-link, a.pph-card-link:visited, a.pph-card-link:hover, a.pph-card-link:active {
  text-decoration: none !important;
  color: inherit !important;
  display: block;
}

/* Card */
.pph-card {
  background: var(--pph-card-bg);
  border: 1px solid var(--pph-card-border);
  border-radius: 16px;
  padding: 16px;
  height: 175px; /* fijo para todas (ref: la más grande) */
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: transform 160ms ease, box-shadow 180ms ease, background 180ms ease, border-color 180ms ease;
  will-change: transform;
  cursor: pointer;
  margin-bottom: 18px;
}

.pph-card:hover {
  background: var(--pph-card-hover-bg);
  box-shadow: var(--pph-shadow);
  transform: translateY(-1px);
  border-color: var(--pph-card-hover-border);
}

.pph-card:active {
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
</style>
""", unsafe_allow_html=True)

# -------------------------
# Header
# -------------------------
st.title("🏠 Pre Production Hub")
st.caption("Centro de herramientas para el equipo de Pre Producción")
st.markdown('<div class="hr-soft"></div>', unsafe_allow_html=True)
st.subheader("Herramientas")

def tool_card_link(icon: str, title: str, desc: str, page_path: str):
    # Link válido dentro del mismo Home: setea query param y Home redirige con st.switch_page
    href = f"?go={quote(page_path)}"
    st.markdown(f"""
<a class="pph-card-link" href="{href}" target="_self">
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
</a>
""", unsafe_allow_html=True)

# -------------------------
# Grid (mismo orden + mismas rutas)
# -------------------------
c1, c2, c3 = st.columns(3, gap="large")

with c1:
    tool_card_link("🧾", "Traductor ALVIC x CUBRO",
                   "Traduce piezas LAC a códigos ALVIC y separa mecanizadas / sin mecanizar.",
                   "pages/1_🧾_Traductor_ALVIC.py")

with c2:
    tool_card_link("📦", "Historial pedidos ALVIC",
                   "Busca pedidos CSV en Google Drive por nombre y revisa su trazabilidad por fecha de envío.",
                   "pages/13_📦_Historial_pedidos_ALVIC.py")

with c3:
    tool_card_link("📊", "KPIS & Data base",
                   "Acceso a KPIS de equipo, base de datos e información de ficheros de cortes realizados.",
                   "pages/3_📊_KPIS_Data_base.py")

c4, c5, c6 = st.columns(3, gap="large")

with c4:
    tool_card_link("🗂️", "Ficheros de corte",
                   "Herramienta para añadir información operativa de ficheros de corte",
                   "pages/4_🗂️_Ficheros_de_corte.py")

with c5:
    tool_card_link("🧵", "Stock de retales",
                   "Permite consultar base de datos de retales en taller y añadir o quitar retales (marcar como utilizados)",
                   "pages/5_🧵_Stock_de_retales.py")

with c6:
    tool_card_link("🪚", "Despiece hornacinas",
                   "Herramienta que permite configurar hornacinas y generar un despiece listo para traspasarlo al proyecto",
                   "pages/6_🪚_Despiece_hornacinas.py")

c7, c8, c9 = st.columns(3, gap="large")

with c7:
    tool_card_link("🔗", "Docs & Links",
                   "Document hub y central de links importantes",
                   "pages/7_🔗_Docs_Links.py")

with c8:
    tool_card_link("🗓️", "Calculadora de semana de corte",
                   "Herramienta para calcular la semana de corte sugerida en función de la fecha deseada de entrega o fecha de montaje asignada",
                   "pages/8_🗓️_Calculadora_semana_corte.py")

with c9:
    tool_card_link("📐", "Configurador de altillos PAX",
                   "Herramienta que permite seleccionar dimensiones de altillos y genera un PDF con planos de altillo configurado",
                   "pages/9_📐_Configurador_altillos_PAX.py")

c10, c11, c12 = st.columns(3, gap="large")

with c10:
    tool_card_link("🧩", "Configuradores 3D (Shapediver)",
                   "Sección para visualizar los diferentes configuradores 3D de producto utilizando Shapediver",
                   "pages/10_🧩_Configuradores_3D_Shapediver.py")

with c11:
    tool_card_link("🚚", "Datos de envío",
                   "Busca por ID CUBRO o cliente y copia la dirección lista para envío.",
                   "pages/11_🚚_Datos_de_envío.py")


with c12:
    tool_card_link("📐", "Lector de DXF",
                   "Visualiza archivos DXF, filtra capas y obtén un diagnóstico de polilíneas por layer.",
                   "pages/12_📐_Lector_DXF.py")

c13, c14, c15 = st.columns(3, gap="large")

with c13:
    tool_card_link("🧩", "NestingAppV5",
                   "Genera layouts/nesting y prepara descargas para producción.",
                   "pages/2_🧩_Nesting_App.py")

st.markdown('<div class="hr-soft"></div>', unsafe_allow_html=True)
st.info("También puedes navegar usando el menú lateral de Streamlit.")
