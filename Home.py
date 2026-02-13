# Home.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import streamlit as st

# Si ya tienes tu helper de sidebar compartida, intenta importarlo.
# (Si no existe, la Home seguirá funcionando igual.)
try:
    from shared.sidebar import apply_shared_sidebar  # type: ignore
except Exception:  # pragma: no cover
    apply_shared_sidebar = None  # type: ignore


# -----------------------------
# Config
# -----------------------------
st.set_page_config(
    page_title="Pre Production Hub",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

ASSETS_DIR = Path(__file__).parent / "assets"


# -----------------------------
# Model
# -----------------------------
@dataclass(frozen=True)
class ToolCard:
    key: str
    title: str
    subtitle: str
    page_path: str
    image_filename: str
    category: str
    badge: str = ""


TOOLS: list[ToolCard] = [
    ToolCard(
        key="traductor",
        title="Traductor",
        subtitle="Traduce piezas y separa outputs operativos.",
        page_path="pages/1_🧩_Traductor.py",
        image_filename="traductor.png",
        category="Producción",
        badge="Core",
    ),
    ToolCard(
        key="nesting",
        title="Nesting",
        subtitle="Layouts + ZIP para corte en 1 click.",
        page_path="pages/2_🧱_Nesting.py",
        image_filename="nesting.png",
        category="Producción",
        badge="Core",
    ),
    ToolCard(
        key="kpis",
        title="KPIs & Data base",
        subtitle="Métricas, tendencias y análisis mensual.",
        page_path="pages/3_📊_KPIS_Data_base.py",
        image_filename="kpis.png",
        category="Analítica",
        badge="Core",
    ),
    ToolCard(
        key="ficheros_corte",
        title="Ficheros de corte",
        subtitle="Indexa, filtra y consulta la base histórica.",
        page_path="pages/4_🗂️_Ficheros_de_corte.py",
        image_filename="ficheros_corte.png",
        category="Analítica",
        badge="Beta",
    ),
    ToolCard(
        key="retales",
        title="Stock de retales",
        subtitle="Inventario y control editable con validaciones.",
        page_path="pages/5_🧵_Stock_de_retales.py",
        image_filename="stock_retales.png",
        category="Operaciones",
        badge="Core",
    ),
    ToolCard(
        key="hornacinas",
        title="Despiece hornacinas",
        subtitle="Genera despieces consistentes y exportables.",
        page_path="pages/6_🧱_Despiece_de_hornacinas.py",
        image_filename="hornacinas.png",
        category="Operaciones",
        badge="Core",
    ),
    ToolCard(
        key="docs_links",
        title="Docs & Links",
        subtitle="Accesos rápidos a documentación y recursos.",
        page_path="pages/7_🔗_Docs_Links.py",
        image_filename="docs_links.png",
        category="Soporte",
        badge="",
    ),
    ToolCard(
        key="semana_corte",
        title="Calculadora semana de corte",
        subtitle="Convierte fechas ↔ semana ISO sin sufrir.",
        page_path="pages/8_🗓️_Calculadora_semana.py",
        image_filename="semana_corte.png",
        category="Soporte",
        badge="",
    ),
    ToolCard(
        key="altillos",
        title="Configurador altillos PAX",
        subtitle="Reglas + módulos listos para producción.",
        page_path="pages/9_🧰_Altillos_PAX.py",
        image_filename="altillos_pax.png",
        category="Configuradores",
        badge="Core",
    ),
    ToolCard(
        key="config_3d",
        title="Configuradores 3D",
        subtitle="Embeds ShapeDiver y utilidades 3D.",
        page_path="pages/10_🧊_Configuradores_3D.py",
        image_filename="configuradores_3d.png",
        category="Configuradores",
        badge="Core",
    ),
]


# -----------------------------
# Helpers
# -----------------------------
def _inject_css() -> None:
    st.markdown(
        """
<style>
/* Layout */
.block-container { padding-top: 1.2rem; padding-bottom: 1.6rem; }

/* Hero */
.hero {
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 18px;
  padding: 18px 18px;
  background: linear-gradient(135deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
}
.hero h1 { margin: 0; font-size: 28px; }
.hero p { margin: 0.25rem 0 0 0; opacity: 0.85; }

/* Card */
.tool-card {
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 18px;
  padding: 14px 14px 12px 14px;
  background: rgba(255,255,255,0.03);
  transition: transform 120ms ease, border-color 120ms ease, background 120ms ease;
  height: 100%;
}
.tool-card:hover {
  transform: translateY(-2px);
  border-color: rgba(255,255,255,0.18);
  background: rgba(255,255,255,0.045);
}
.tool-title { font-size: 16px; font-weight: 650; margin: 8px 0 2px 0; }
.tool-subtitle { font-size: 13px; opacity: 0.78; margin: 0 0 10px 0; }
.tool-meta { display: flex; gap: 8px; align-items: center; margin-top: 8px; opacity: 0.85; font-size: 12px; }
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.10);
  font-size: 12px;
}
.small-muted { font-size: 12px; opacity: 0.70; }
hr.soft { border: none; border-top: 1px solid rgba(255,255,255,0.08); margin: 14px 0; }

/* Buttons: make them feel like actions inside cards */
div.stButton > button {
  width: 100%;
  border-radius: 12px;
  padding: 0.55rem 0.8rem;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _safe_image(path: Path) -> Optional[Path]:
    return path if path.exists() else None


def _open_page(page_path: str) -> None:
    # st.switch_page requiere la ruta relativa a la multipage app.
    # Si el path no existe, Streamlit lanzará error: es deseable (falla rápido).
    st.switch_page(page_path)


def _init_state() -> None:
    st.session_state.setdefault("home_search", "")
    st.session_state.setdefault("home_category", "Todas")
    st.session_state.setdefault("home_favs", set())  # type: ignore


# -----------------------------
# Sidebar (nuevo diseño)
# -----------------------------
_init_state()

if apply_shared_sidebar:
    apply_shared_sidebar(current_page="Home.py")

with st.sidebar:
    st.markdown("### 🧭 Navegación")
    st.caption("Filtra herramientas y entra directo al trabajo.")
    st.text_input("Buscar", key="home_search", placeholder="Ej: retales, nesting, KPIs...")

    categories = ["Todas"] + sorted({t.category for t in TOOLS})
    st.selectbox("Categoría", categories, key="home_category")

    st.markdown("---")
    st.markdown("### ⭐ Favoritos")
    favs: set[str] = st.session_state["home_favs"]  # type: ignore
    fav_tools = [t for t in TOOLS if t.key in favs]

    if not fav_tools:
        st.caption("Aún no tienes favoritos. Marca una tool desde la Home.")
    else:
        for t in fav_tools:
            if st.button(t.title, key=f"fav_go_{t.key}"):
                _open_page(t.page_path)

    st.markdown("---")
    st.caption("Consejo: si todo falla… reinicia y finge que fue un *feature*.")


# -----------------------------
# Main (nuevo layout)
# -----------------------------
_inject_css()

# Hero
left, right = st.columns([0.72, 0.28], vertical_alignment="top")
with left:
    st.markdown(
        """
<div class="hero">
  <h1>Pre Production Hub</h1>
  <p>Un panel único para herramientas de pre-producción: rápido, consistente y sin drama (bueno, casi).</p>
</div>
        """,
        unsafe_allow_html=True,
    )

with right:
    # Mini panel de acciones rápidas (puedes cambiar estas rutas cuando quieras)
    st.markdown('<div class="hero">', unsafe_allow_html=True)
    st.markdown("**Acciones rápidas**")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Abrir Nesting", use_container_width=True):
            _open_page("pages/2_🧱_Nesting.py")
    with c2:
        if st.button("Abrir KPIs", use_container_width=True):
            _open_page("pages/3_📊_KPIS_Data_base.py")
    st.markdown('<hr class="soft">', unsafe_allow_html=True)
    st.caption("Atajos pensados para el día a día.")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<hr class="soft">', unsafe_allow_html=True)

# Filtros aplicados
q = (st.session_state["home_search"] or "").strip().lower()
cat = st.session_state["home_category"]

filtered = TOOLS
if cat != "Todas":
    filtered = [t for t in filtered if t.category == cat]
if q:
    filtered = [
        t
        for t in filtered
        if (q in t.title.lower()) or (q in t.subtitle.lower()) or (q in t.category.lower())
    ]

# Sección: herramientas
st.markdown("## Herramientas")
st.caption("Tarjetas con imagen + acciones. Cambias imágenes en `assets/` y listo.")

if not filtered:
    st.info("No hay resultados con esos filtros. Prueba con otra palabra o vuelve a 'Todas'.")
else:
    # Grid responsivo "manual": 3 columnas (ajústalo a 4 si prefieres)
    cols = st.columns(3, gap="large")

    favs: set[str] = st.session_state["home_favs"]  # type: ignore

    for i, tool in enumerate(filtered):
        col = cols[i % 3]
        with col:
            img_path = _safe_image(ASSETS_DIR / tool.image_filename)

            st.markdown('<div class="tool-card">', unsafe_allow_html=True)

            if img_path:
                st.image(str(img_path), use_container_width=True)
            else:
                st.caption(f"🖼️ Falta `{tool.image_filename}` en `assets/`")

            title_line = tool.title
            if tool.badge:
                title_line = f"{tool.title}  <span class='badge'>{tool.badge}</span>"

            st.markdown(f"<div class='tool-title'>{title_line}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='tool-subtitle'>{tool.subtitle}</div>", unsafe_allow_html=True)

            b1, b2 = st.columns([0.72, 0.28])
            with b1:
                if st.button("Abrir", key=f"open_{tool.key}", use_container_width=True):
                    _open_page(tool.page_path)
            with b2:
                is_fav = tool.key in favs
                label = "★" if is_fav else "☆"
                if st.button(label, key=f"fav_{tool.key}", use_container_width=True):
                    if is_fav:
                        favs.remove(tool.key)
                    else:
                        favs.add(tool.key)
                    st.session_state["home_favs"] = favs  # type: ignore
                    st.rerun()

            st.markdown(
                f"<div class='tool-meta'><span class='small-muted'>Categoría:</span> {tool.category}</div>",
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

# Sección inferior: estado / notas (opcional)
st.markdown('<hr class="soft">', unsafe_allow_html=True)
bL, bR = st.columns([0.6, 0.4], vertical_alignment="top")

with bL:
    st.markdown("### Estado")
    st.write(
        "Esta Home está pensada como **dashboard**: filtros, favoritos y accesos rápidos. "
        "Tu mantenimiento se reduce a dos cosas: **rutas de páginas** y **PNG en `assets/`**."
    )

with bR:
    st.markdown("### Notas rápidas")
    st.caption("Útil para avisos internos, cambios de semana, o ‘hoy no se toca nada que funciona’.")
    st.text_area(
        label="",
        placeholder="Ej: Semana 7 cerrada. Prioridad: hornacinas + laca.",
        height=110,
        key="home_notes",
    )
