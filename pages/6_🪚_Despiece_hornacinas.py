import streamlit as st

from lib.hornacinas.exporter import to_csv_bytes, to_dataframe
from lib.hornacinas.models import HornacinaInput
from lib.hornacinas.rules import build_pieces, get_material_info
from lib.hornacinas.validators import validate_input
from ui_theme import apply_shared_sidebar

st.set_page_config(page_title="Despiece hornacinas", layout="wide")
apply_shared_sidebar("pages/6_🪚_Despiece_hornacinas.py")
st.markdown("<style>h1 { font-size: 2.2rem !important; }</style>", unsafe_allow_html=True)

st.title("🪚 Despiece hornacinas")

col_back, _ = st.columns([1, 5])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

st.caption("Configura una hornacina y genera el despiece en tabla + CSV.")

if "hornacina_result_df" not in st.session_state:
    st.session_state["hornacina_result_df"] = None
if "hornacina_csv" not in st.session_state:
    st.session_state["hornacina_csv"] = None
if "hornacina_filename" not in st.session_state:
    st.session_state["hornacina_filename"] = "despiece_hornacina.csv"

with st.form("hornacinas_form"):
    c1, c2 = st.columns(2)

    with c1:
        project_id = st.text_input("Project ID", value="", placeholder="Ej: EU-21231")
        h_index_raw = st.text_input("Índice de hornacina H# (opcional)", value="", placeholder="1")
        ancho_mm = st.number_input("Ancho (mm)", min_value=1, value=1, step=1,)
        alto_mm = st.number_input("Alto (mm)", min_value=1, value=1, step=1)
        fondo_mm = st.number_input("Fondo (mm)", min_value=1, value=1, step=1)

    with c2:
        num_baldas = st.number_input("Cantidad de baldas", min_value=0, value=2, step=1)
        material_code = st.selectbox("MaterialCode", options=["LAC", "WOO", "LAM", "LIN"], index=1)
        color = st.text_input("Color", value="Cerezo")
        herraje_colgar = st.toggle("Herraje de colgar", value=False)
        rodapie_mm = st.number_input("Altura de rodapié (mm)", min_value=0, value=0, step=1)

    submitted = st.form_submit_button("Generar despiece", type="primary")

if submitted:
    normalized_h_index = 1
    if h_index_raw.strip():
        try:
            normalized_h_index = int(h_index_raw)
        except ValueError:
            st.error("Índice de hornacina inválido: introduce un entero (ej: 1, 2, 3).")
            st.stop()
        if normalized_h_index <= 0:
            st.error("Índice de hornacina inválido: debe ser mayor que 0.")
            st.stop()

    inp = HornacinaInput(
        project_id=project_id.strip(),
        h_index=normalized_h_index,
        ancho_mm=int(ancho_mm),
        alto_mm=int(alto_mm),
        fondo_mm=int(fondo_mm),
        num_baldas=int(num_baldas),
        material_code=material_code,
        color=color.strip(),
        herraje_colgar=bool(herraje_colgar),
        rodapie_mm=int(rodapie_mm),
    )

    material = get_material_info(inp.material_code)
    errors = validate_input(inp, material)

    if errors:
        st.session_state["hornacina_result_df"] = None
        st.session_state["hornacina_csv"] = None
        for err in errors:
            st.error(err)
    else:
        pieces = build_pieces(inp, material)
        result_df = to_dataframe(inp, material, pieces)
        csv_bytes = to_csv_bytes(result_df)

        safe_project = inp.project_id.replace("/", "-").replace("\\", "-") or "SIN_PROYECTO"
        filename = f"DESPIECE_HORNACINAS_{safe_project}_H{inp.h_index}.csv"

        st.session_state["hornacina_result_df"] = result_df
        st.session_state["hornacina_csv"] = csv_bytes
        st.session_state["hornacina_filename"] = filename
        st.success("Despiece generado correctamente.")

if st.session_state.get("hornacina_result_df") is not None:
    tab_resultado, tab_descarga = st.tabs(["Resultado", "Descarga"])

    with tab_resultado:
        st.dataframe(st.session_state["hornacina_result_df"], use_container_width=True, hide_index=True)

    with tab_descarga:
        st.download_button(
            "Descargar CSV",
            data=st.session_state["hornacina_csv"],
            file_name=st.session_state["hornacina_filename"],
            mime="text/csv",
            type="primary",
        )
        st.caption("Formato listo para abrir en Excel o importar en flujo interno.")
else:
    st.info("Completa los datos y pulsa “Generar despiece” para ver la tabla.")
