import pandas as pd
import streamlit as st

from ui_theme import apply_shared_sidebar
from utils.shipping_data import build_display_fields, load_shipping_sheet, search_shipping_data

st.set_page_config(page_title="Datos de envío", layout="wide")
apply_shared_sidebar("pages/11_🚚_Datos_de_envío.py")

st.markdown(
    """
    <style>
    h1 { font-size: 2.2rem !important; }
    .shipping-card {
      border: 1px solid rgba(120, 120, 120, 0.28);
      border-radius: 12px;
      padding: 1rem 1.1rem;
      background: rgba(250, 250, 250, 0.02);
      margin-bottom: 0.8rem;
    }
    .shipping-label {
      font-size: 0.73rem;
      letter-spacing: .08em;
      text-transform: uppercase;
      font-weight: 700;
      opacity: 0.72;
      margin-bottom: 0.2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🚚 Datos de envío")

col_back, _ = st.columns([1, 5])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

st.caption("Busca por ID CUBRO o cliente y copia la dirección lista para envío.")

if "shipping_query" not in st.session_state:
    st.session_state.shipping_query = ""
if "shipping_results" not in st.session_state:
    st.session_state.shipping_results = []
if "shipping_selected_idx" not in st.session_state:
    st.session_state.shipping_selected_idx = 0


def run_search() -> None:
    query = st.session_state.shipping_query.strip()
    if not query:
        st.session_state.shipping_results = []
        st.session_state.shipping_selected_idx = 0
        return

    try:
        data = load_shipping_sheet()
        st.session_state.shipping_results = search_shipping_data(data, query)
        st.session_state.shipping_selected_idx = 0
    except Exception as exc:
        st.session_state.shipping_results = []
        st.error("No se pudo cargar la información de envíos desde Google Sheets.")
        st.code(repr(exc))


col_q, col_search, col_clear = st.columns([6, 1.4, 1.3])
with col_q:
    st.text_input(
        "Buscar",
        key="shipping_query",
        placeholder="Ej: SP-12345 o Nuria",
        label_visibility="collapsed",
    )
with col_search:
    st.button("Buscar", type="primary", use_container_width=True, on_click=run_search)
with col_clear:
    if st.button("Limpiar", use_container_width=True):
        st.session_state.shipping_query = ""
        st.session_state.shipping_results = []
        st.session_state.shipping_selected_idx = 0
        st.rerun()


results = st.session_state.shipping_results
query = st.session_state.shipping_query.strip()

if not query:
    st.markdown('<div class="shipping-card">', unsafe_allow_html=True)
    st.markdown("- Introduce un ID (SP-xxxxx) o un nombre de cliente.")
    st.markdown("- Si hay varias coincidencias, podrás seleccionar la correcta.")
    st.markdown("</div>", unsafe_allow_html=True)
elif not results:
    st.warning("No se encontraron coincidencias.")
    st.caption("Sugerencia: prueba sin acentos, usa parte del nombre o revisa el ID.")


def _copy_actions(values: dict[str, str]) -> None:
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Copiar dirección", use_container_width=True, key=f"copy_addr_{values['direccion']}"):
            st.toast("Copiado (selecciona y Ctrl+C)", icon="📋")
    with c2:
        if st.button("Copiar CP y población", use_container_width=True, key=f"copy_cp_{values['cp_poblacion']}"):
            st.toast("Copiado (selecciona y Ctrl+C)", icon="📋")
    with c3:
        if st.button("Copiar todo", use_container_width=True, key=f"copy_all_{values['direccion']}_{values['cp_poblacion']}"):
            st.toast("Copiado (selecciona y Ctrl+C)", icon="📋")


def render_detail(row_data: dict[str, str]) -> None:
    fields = build_display_fields(row_data)
    full_text = "\n".join(filter(None, [fields["direccion"], fields["cp_poblacion"], fields["pais"]]))

    st.markdown('<div class="shipping-card">', unsafe_allow_html=True)

    st.markdown('<div class="shipping-label">Dirección</div>', unsafe_allow_html=True)
    st.code(fields["direccion"])

    st.markdown('<div class="shipping-label">CP y población</div>', unsafe_allow_html=True)
    st.code(fields["cp_poblacion"])

    st.markdown('<div class="shipping-label">País</div>', unsafe_allow_html=True)
    st.code(fields["pais"])

    _copy_actions(
        {
            "direccion": fields["direccion"],
            "cp_poblacion": fields["cp_poblacion"],
            "todo": full_text,
        }
    )
    st.markdown("</div>", unsafe_allow_html=True)


if len(results) == 1:
    render_detail(results[0])
elif len(results) > 1:
    st.markdown('<div class="shipping-card">', unsafe_allow_html=True)
    st.markdown("### Selección de coincidencia")

    rows_for_table = []
    options = []
    for i, row in enumerate(results):
        fields = build_display_fields(row)
        rows_for_table.append(
            {
                "ID": row.get("id", ""),
                "Cliente": row.get("cliente", ""),
                "Dirección": fields["direccion"],
                "CP + Población": fields["cp_poblacion"],
                "País": fields["pais"],
            }
        )
        options.append(f"{row.get('id', '')} — {row.get('cliente', '')} — {fields['direccion']}")

    table_df = pd.DataFrame(rows_for_table)
    st.dataframe(table_df, use_container_width=True, hide_index=True)

    max_index = len(options) - 1
    selected_idx = min(st.session_state.shipping_selected_idx, max_index)
    selected_label = st.selectbox("Selecciona una coincidencia", options=options, index=selected_idx)
    st.session_state.shipping_selected_idx = options.index(selected_label)
    st.markdown("</div>", unsafe_allow_html=True)

    render_detail(results[st.session_state.shipping_selected_idx])
