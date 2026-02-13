from __future__ import annotations

from typing import Any

import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ui_theme import apply_shared_sidebar
from utils.dxf_reader import count_polylines_by_layer, load_dxf_from_bytes, render_preview_png

st.set_page_config(page_title="Lector de DXF", layout="wide")
apply_shared_sidebar("pages/12_📐_Lector_DXF.py")

st.title("📐 Lector de DXF")
st.caption("Carga y visualiza archivos DXF sin AutoCAD, con diagnóstico por capas.")


SESSION_DEFAULTS = {
    "dxf_source_mode": "Manual",
    "dxf_filename": None,
    "dxf_bytes": None,
    "selected_space": "Modelspace",
    "selected_layout": None,
    "visible_layers": set(),
    "bg_mode": "Claro",
    "drive_folder_id": "",
}
for key, value in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"


def _get_service_account_info() -> dict[str, Any]:
    if "gcp_service_account" in st.secrets:
        return dict(st.secrets["gcp_service_account"])
    raise RuntimeError(
        "No se encontró `gcp_service_account` en secrets. Configura credenciales de service account para usar Google Drive."
    )


@st.cache_resource
def get_drive_service():
    info = _get_service_account_info()
    creds = Credentials.from_service_account_info(info, scopes=[DRIVE_READONLY_SCOPE])
    return build("drive", "v3", credentials=creds)


@st.cache_data(ttl=90)
def list_dxf_files(folder_id: str) -> list[dict[str, Any]]:
    service = get_drive_service()
    query = (
        f"'{folder_id}' in parents and trashed = false and "
        "(mimeType = 'application/dxf' or name contains '.dxf')"
    )
    resp = (
        service.files()
        .list(
            q=query,
            fields="files(id,name,modifiedTime,size,mimeType)",
            orderBy="modifiedTime desc",
            pageSize=200,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    files = resp.get("files", [])
    return [f for f in files if str(f.get("name", "")).lower().endswith(".dxf")]


def download_file(file_id: str) -> bytes:
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    return request.execute()


def _format_size(size_raw: Any) -> str:
    try:
        size = int(size_raw)
    except Exception:
        return "-"
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


with st.sidebar:
    st.header("Lector de DXF")
    mode = st.radio(
        "Modo de entrada",
        ["Manual", "Automático (Google Drive)"],
        key="dxf_source_mode",
    )

    if mode == "Manual":
        uploaded_file = st.file_uploader("Sube un archivo .dxf", type=["dxf"])
        if uploaded_file is not None:
            st.session_state["dxf_filename"] = uploaded_file.name
            st.session_state["dxf_bytes"] = uploaded_file.getvalue()

    else:
        default_folder = ""
        if "dxf_drive_folder_id" in st.secrets:
            default_folder = st.secrets["dxf_drive_folder_id"]
        elif "google_drive" in st.secrets and "folder_id" in st.secrets["google_drive"]:
            default_folder = st.secrets["google_drive"]["folder_id"]

        if not st.session_state["drive_folder_id"] and default_folder:
            st.session_state["drive_folder_id"] = default_folder

        folder_id = st.text_input("Folder ID de Drive", key="drive_folder_id")

        if st.button("Listar DXF", use_container_width=True):
            st.session_state["drive_files"] = []
            if folder_id.strip():
                try:
                    st.session_state["drive_files"] = list_dxf_files(folder_id.strip())
                except HttpError as exc:
                    st.error("No se pudieron listar los DXF. Verifica permisos del service account y el folder_id.")
                    st.code(str(exc))
                except Exception as exc:
                    st.error("Error inesperado al listar archivos de Drive.")
                    st.code(repr(exc))
            else:
                st.warning("Introduce un folder_id válido.")

        drive_files = st.session_state.get("drive_files", [])
        if drive_files:
            labels = {
                item["id"]: f"{item.get('name', '-') } · {item.get('modifiedTime', '-') } · {_format_size(item.get('size'))}"
                for item in drive_files
            }
            selected_file_id = st.selectbox(
                "DXF en Drive",
                options=[item["id"] for item in drive_files],
                format_func=lambda fid: labels.get(fid, fid),
            )

            if st.button("Cargar seleccionado", type="primary", use_container_width=True):
                try:
                    file_bytes = download_file(selected_file_id)
                    selected_meta = next((f for f in drive_files if f["id"] == selected_file_id), {})
                    st.session_state["dxf_filename"] = selected_meta.get("name", "archivo_drive.dxf")
                    st.session_state["dxf_bytes"] = file_bytes
                except HttpError as exc:
                    st.error("No se pudo descargar el DXF seleccionado desde Drive.")
                    st.code(str(exc))
                except Exception as exc:
                    st.error("Error inesperado al descargar el archivo.")
                    st.code(repr(exc))
        else:
            st.caption("Lista vacía. Pulsa **Listar DXF** para consultar la carpeta.")


dxf_bytes = st.session_state.get("dxf_bytes")
if not dxf_bytes:
    st.info("Carga un archivo DXF desde tu ordenador o desde Google Drive para empezar.")
    st.stop()

try:
    doc = load_dxf_from_bytes(dxf_bytes)
except Exception as exc:
    st.error("No se pudo leer el DXF. Comprueba que el archivo sea válido.")
    st.code(repr(exc))
    st.stop()

filename = st.session_state.get("dxf_filename") or "(sin nombre)"
st.subheader(f"Archivo cargado: {filename}")

st.session_state["selected_space"] = "Modelspace"
model_layers = sorted({(getattr(entity.dxf, 'layer', '0') or '0') for entity in doc.modelspace()})
all_layers = model_layers

if not st.session_state["visible_layers"]:
    st.session_state["visible_layers"] = set(all_layers)

with st.sidebar:
    st.markdown("---")
    st.markdown("### Capas")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Mostrar todas", use_container_width=True):
            st.session_state["visible_layers"] = set(all_layers)
    with c2:
        if st.button("Ocultar todas", use_container_width=True):
            st.session_state["visible_layers"] = set()

    with st.expander("Capas visibles", expanded=False):
        selected_layers = st.multiselect(
            "Selecciona capas",
            options=all_layers,
            default=[layer for layer in all_layers if layer in st.session_state["visible_layers"]],
            label_visibility="collapsed",
        )
    st.session_state["visible_layers"] = set(selected_layers)

    st.markdown("### Preview")
    st.radio("Fondo", ["Claro", "Oscuro"], key="bg_mode", horizontal=True)

space_key = "model"
layout_name = None

counts_df = count_polylines_by_layer(doc, space=space_key, layout_name=layout_name)

st.markdown("### Diagnóstico")
st.dataframe(counts_df, use_container_width=True, hide_index=True)
st.metric("Total polilíneas", int(counts_df["Polylines"].sum()) if not counts_df.empty else 0)
st.caption("Incluye entidades LWPOLYLINE + POLYLINE del espacio seleccionado (sin explotar bloques INSERT).")

bg_mode = "white" if st.session_state["bg_mode"] == "Claro" else "dark"
preview_png = render_preview_png(
    doc,
    space=space_key,
    layout_name=layout_name,
    visible_layers=st.session_state["visible_layers"],
    bg=bg_mode,
)

st.markdown("### Visualización")
st.image(preview_png, use_container_width=True)
st.download_button(
    "Descargar PNG",
    data=preview_png,
    file_name=f"{filename.rsplit('.', 1)[0]}_preview.png",
    mime="image/png",
)

st.markdown(
    """
    #### Nota de configuración (Google Drive)
    Para el modo automático, añade en `st.secrets`:
    - `gcp_service_account` (json del service account)
    - opcional `dxf_drive_folder_id` o `google_drive.folder_id`
    """
)
