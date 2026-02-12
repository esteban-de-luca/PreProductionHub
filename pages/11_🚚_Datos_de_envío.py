import pandas as pd
import streamlit as st
from datetime import datetime

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
    .shipping-result-panel {
      border: 1px solid rgba(255,255,255,0.10);
      border-radius: 12px;
      padding: 16px 16px;
      background: rgba(255,255,255,0.03);
      margin-top: 0.5rem;
    }
    .shipping-divider {
      border: none;
      border-top: 1px solid rgba(255,255,255,0.08);
      margin: 12px 0;
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
    st.session_state["shipping_query"] = ""
if "shipping_results" not in st.session_state:
    st.session_state["shipping_results"] = []
if "shipping_selected_idx" not in st.session_state:
    st.session_state["shipping_selected_idx"] = 0
if "shipping_selected_label" not in st.session_state:
    st.session_state["shipping_selected_label"] = None
if "last_update" not in st.session_state:
    st.session_state["last_update"] = datetime.now()


if st.sidebar.button("🔄 Actualizar datos"):
    load_shipping_sheet.clear()
    st.session_state["last_update"] = datetime.now()
    st.toast("Datos actualizados correctamente")
    st.rerun()

st.sidebar.markdown(
    f"""
    <div style="font-size:0.8rem; opacity:0.7; margin-top:0.5rem;">
        Última actualización:<br>
        <strong>{st.session_state["last_update"].strftime("%H:%M:%S")}</strong>
    </div>
    """,
    unsafe_allow_html=True,
)


def _render_plain_value(value: str) -> None:
    st.markdown(
        f"""
        <div style="
            background-color: transparent;
            padding: 0.6rem 0;
            font-size: 0.95rem;
            color: white;
            word-break: break-word;
        ">
            {value}
        </div>
        """,
        unsafe_allow_html=True,
    )


def run_search() -> None:
    query = st.session_state["shipping_query"].strip()
    if not query:
        st.session_state["shipping_results"] = []
        st.session_state["shipping_selected_idx"] = 0
        st.session_state["shipping_selected_label"] = None
        return

    try:
        data = load_shipping_sheet()
        st.session_state["shipping_results"] = search_shipping_data(data, query)
        st.session_state["shipping_selected_idx"] = 0
        st.session_state["shipping_selected_label"] = None
    except Exception as exc:
        st.session_state["shipping_results"] = []
        st.error("No se pudo cargar la información de envíos desde Google Sheets.")
        st.code(repr(exc))


def clear_shipping_state() -> None:
    st.session_state["shipping_query"] = ""
    st.session_state["shipping_results"] = None
    st.session_state["shipping_selected_idx"] = None
    st.session_state["shipping_selected_label"] = None


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
    st.button("Limpiar", use_container_width=True, on_click=clear_shipping_state)


def _render_business_name(business_name: str) -> None:
    if not business_name:
        return

    st.markdown(
        f"""
        <div style="margin-top:0.5rem; margin-bottom:0.8rem;">
            <div style="font-size:0.75rem; letter-spacing:0.06em; opacity:0.7;">
                PROYECTO / NEGOCIO
            </div>
            <div style="font-size:1.05rem; font-weight:600; color:white;">
                {business_name}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


results = st.session_state.get("shipping_results") or []
query = (st.session_state.get("shipping_query") or "").strip()

if not query:
    st.markdown('<div class="shipping-card">', unsafe_allow_html=True)
    st.markdown("- Introduce un ID (SP-xxxxx) o un nombre de cliente.")
    st.markdown("- Si hay varias coincidencias, podrás seleccionar la correcta.")
    st.markdown("</div>", unsafe_allow_html=True)
elif not results:
    st.warning("No se encontraron coincidencias.")
    st.caption("Sugerencia: prueba sin acentos, usa parte del nombre o revisa el ID.")

selected_business_name = ""
if len(results) == 1:
    selected_business_name = build_display_fields(results[0]).get("business_name", "")
elif len(results) > 1:
    selected_idx = st.session_state.get("shipping_selected_idx")
    if selected_idx is None:
        selected_idx = 0
    selected_idx = min(selected_idx, len(results) - 1)
    selected_business_name = build_display_fields(results[selected_idx]).get("business_name", "")

if selected_business_name:
    _render_business_name(selected_business_name)


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

    st.markdown('<div class="shipping-result-panel">', unsafe_allow_html=True)

    st.markdown('<div class="shipping-label">Dirección</div>', unsafe_allow_html=True)
    _render_plain_value(fields["direccion"])
    st.markdown('<hr class="shipping-divider" />', unsafe_allow_html=True)

    st.markdown('<div class="shipping-label">CP y población</div>', unsafe_allow_html=True)
    _render_plain_value(fields["cp_poblacion"])
    st.markdown('<hr class="shipping-divider" />', unsafe_allow_html=True)

    st.markdown('<div class="shipping-label">País</div>', unsafe_allow_html=True)
    _render_plain_value(fields["pais"])

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
    for row in results:
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
    current_idx = st.session_state.get("shipping_selected_idx")
    if current_idx is None:
        current_idx = 0
    selected_idx = min(current_idx, max_index)

    selected_label = st.selectbox("Selecciona una coincidencia", options=options, index=selected_idx, key="shipping_selected_label")
    st.session_state["shipping_selected_idx"] = options.index(selected_label)
    st.markdown("</div>", unsafe_allow_html=True)

    render_detail(results[st.session_state["shipping_selected_idx"]])
