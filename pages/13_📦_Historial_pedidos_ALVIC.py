import io
import re
import csv
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from ui_theme import apply_shared_sidebar

st.set_page_config(page_title="Historial pedidos ALVIC", layout="wide")
apply_shared_sidebar("pages/13_📦_Historial_pedidos_ALVIC.py")

DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
DEFAULT_ROOT_FOLDER_ID = "13B6qI-_fL_7aX3H0TI2Gb4aDF2ymXrWf"
PROJECT_KEY_REGEX = re.compile(r"\b(?:MEC[_-]?)?(SP[-_]\d{4,})\b", re.IGNORECASE)
EXACT_PROJECT_QUERY_REGEX = re.compile(r"^SP[-_]\d{4,}$", re.IGNORECASE)


@st.cache_resource
def get_drive_service():
    try:
        service_account_info = st.secrets["gcp_service_account"]
    except Exception as exc:
        raise RuntimeError(
            "Falta la configuración 'gcp_service_account' en st.secrets. "
            "Añade el JSON de service account para habilitar la lectura de Google Drive."
        ) from exc

    try:
        creds = Credentials.from_service_account_info(
            service_account_info,
            scopes=[DRIVE_READONLY_SCOPE],
        )
        return build("drive", "v3", credentials=creds)
    except Exception as exc:
        raise RuntimeError(
            "No se pudo autenticar con Google Drive. Revisa credenciales y permisos de la service account."
        ) from exc


def resolve_root_folder_id() -> str:
    if "alvic_orders" in st.secrets and isinstance(st.secrets["alvic_orders"], dict):
        nested = st.secrets["alvic_orders"].get("root_folder_id", "")
        if nested:
            return str(nested)

    flat = st.secrets.get("ALVIC_ORDERS_ROOT_FOLDER_ID", "")
    if flat:
        return str(flat)

    if DEFAULT_ROOT_FOLDER_ID:
        return DEFAULT_ROOT_FOLDER_ID

    raise RuntimeError(
        "No se encontró ROOT_FOLDER_ID. Configura st.secrets['alvic_orders']['root_folder_id'] "
        "o st.secrets['ALVIC_ORDERS_ROOT_FOLDER_ID']."
    )


def extract_project_key(filename: str) -> str:
    if not filename:
        return ""
    match = PROJECT_KEY_REGEX.search(filename)
    if not match:
        return ""
    return match.group(1).upper().replace("_", "-")


def list_date_folders(service, root_folder_id: str) -> list[dict]:
    folders: list[dict] = []
    page_token = None
    while True:
        response = (
            service.files()
            .list(
                q=(
                    f"'{root_folder_id}' in parents and "
                    "mimeType='application/vnd.google-apps.folder' and trashed=false"
                ),
                fields="nextPageToken, files(id, name)",
                pageSize=1000,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                pageToken=page_token,
            )
            .execute()
        )
        folders.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return folders


def list_csv_files_in_folder(service, folder_id: str) -> list[dict]:
    files: list[dict] = []
    page_token = None
    while True:
        response = (
            service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, parents, webViewLink)",
                pageSize=1000,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                pageToken=page_token,
            )
            .execute()
        )
        for file_obj in response.get("files", []):
            name = str(file_obj.get("name", ""))
            mime = str(file_obj.get("mimeType", ""))
            if name.lower().endswith(".csv") or "csv" in mime.lower():
                files.append(file_obj)

        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return files


@st.cache_data(ttl=900)
def build_index(root_folder_id: str) -> pd.DataFrame:
    service = get_drive_service()

    try:
        service.files().get(
            fileId=root_folder_id,
            fields="id, name, mimeType",
            supportsAllDrives=True,
        ).execute()
    except HttpError as exc:
        raise RuntimeError(
            "La carpeta raíz configurada no existe o no es accesible para la service account."
        ) from exc

    rows: list[dict] = []
    date_folders = list_date_folders(service, root_folder_id)

    for folder in date_folders:
        folder_id = folder.get("id", "")
        folder_name = str(folder.get("name", "")).strip()
        if not folder_id:
            continue

        for csv_file in list_csv_files_in_folder(service, folder_id):
            filename = str(csv_file.get("name", "")).strip()
            rows.append(
                {
                    "filename": filename,
                    "file_id": csv_file.get("id", ""),
                    "parent_folder_name": folder_name,
                    "parent_folder_id": folder_id,
                    "modified_time": csv_file.get("modifiedTime", ""),
                    "project_key": extract_project_key(filename),
                    "drive_link": csv_file.get("webViewLink", ""),
                }
            )

    df = pd.DataFrame(
        rows,
        columns=[
            "filename",
            "file_id",
            "parent_folder_name",
            "parent_folder_id",
            "modified_time",
            "project_key",
            "drive_link",
        ],
    )

    if df.empty:
        return df

    df["modified_dt"] = pd.to_datetime(df["modified_time"], errors="coerce", utc=True)
    df["folder_sort_dt"] = pd.to_datetime(df["parent_folder_name"], format="%d-%m-%y", errors="coerce")

    df = df.sort_values(
        by=["folder_sort_dt", "parent_folder_name", "modified_dt"],
        ascending=[False, False, False],
        kind="mergesort",
    ).reset_index(drop=True)

    return df


def search_index(
    index: pd.DataFrame,
    query_text: str,
    selected_dates: list[str],
    exact_mode: bool,
) -> pd.DataFrame:
    if index.empty:
        return index

    q = query_text.strip()
    out = index.copy()

    if selected_dates and "Todas" not in selected_dates:
        out = out[out["parent_folder_name"].isin(selected_dates)]

    if not q:
        return out

    filename_lower = out["filename"].str.lower()
    query_lower = q.lower()

    if exact_mode:
        match_filename = filename_lower == query_lower
        match_project = False
        if EXACT_PROJECT_QUERY_REGEX.match(q):
            normalized = q.upper().replace("_", "-")
            match_project = out["project_key"].str.upper().fillna("") == normalized
        out = out[match_filename | match_project]
    else:
        out = out[filename_lower.str.contains(query_lower, na=False)]

    return out


@st.cache_data(ttl=600)
def download_csv_bytes(file_id: str) -> bytes:
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    return buffer.getvalue()


@st.cache_data(ttl=600)
def count_csv_pieces_from_drive(file_id: str) -> int:
    raw_bytes = download_csv_bytes(file_id)
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            text = raw_bytes.decode(encoding)
            non_empty_lines = [line for line in text.splitlines() if line.strip()]
            return max(len(non_empty_lines) - 1, 0)
        except Exception:
            continue

    raise RuntimeError("No se pudo contar el contenido del CSV descargado. Revisa codificación del archivo.")


@st.cache_data(ttl=600)
def load_csv_from_drive(file_id: str) -> pd.DataFrame:
    raw_bytes = download_csv_bytes(file_id)
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            sample = raw_bytes.decode(encoding, errors="ignore")[:4096]
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters="|;,\t")
                sep = dialect.delimiter
            except Exception:
                sep = "|" if "|" in sample else ","

            return pd.read_csv(io.BytesIO(raw_bytes), encoding=encoding, sep=sep)
        except Exception:
            continue

    raise RuntimeError("No se pudo leer el CSV descargado. Revisa codificación y separadores del archivo.")


st.title("📦 Historial pedidos ALVIC")
st.caption("Busca pedidos por nombre de archivo y conserva la trazabilidad por subcarpeta de envío en Drive.")

col_back, _ = st.columns([1, 6])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

if "selected_file_id" not in st.session_state:
    st.session_state["selected_file_id"] = ""

if st.sidebar.button("🔄 Actualizar índice", use_container_width=True):
    build_index.clear()
    st.toast("Índice invalidado. Reconstruyendo…", icon="🔄")
    st.rerun()

try:
    ROOT_FOLDER_ID = resolve_root_folder_id()
    index_df = build_index(ROOT_FOLDER_ID)
except RuntimeError as exc:
    st.error(str(exc))
    st.stop()
except HttpError as exc:
    st.error("Error de Google Drive API al construir el índice. Verifica acceso a la carpeta y cuotas.")
    st.code(repr(exc))
    st.stop()
except Exception as exc:
    st.error("Error inesperado al construir el índice de pedidos.")
    st.code(repr(exc))
    st.stop()

available_dates = sorted(index_df["parent_folder_name"].dropna().unique().tolist(), reverse=True) if not index_df.empty else []

st.sidebar.text_input(
    "Buscar pedido (nombre archivo)",
    key="alvic_search_query",
    placeholder="Ej: SP-12345",
)

selected_dates = st.sidebar.multiselect(
    "Filtrar por fechas (subcarpetas)",
    options=["Todas", *available_dates],
    default=["Todas"],
)

exact_mode = st.sidebar.toggle("Búsqueda exacta", value=False)

query_text = st.session_state.get("alvic_search_query", "")
results_df = search_index(index_df, query_text, selected_dates, exact_mode)

st.subheader("Resultados")

if results_df.empty:
    st.info("No se encontraron pedidos con ese criterio.")
else:
    if len(results_df) == 1:
        st.session_state["selected_file_id"] = str(results_df.iloc[0]["file_id"])

    display_df = results_df[["filename", "parent_folder_name", "modified_dt", "file_id"]].copy()
    display_df["piezas"] = display_df["file_id"].apply(count_csv_pieces_from_drive)
    display_df.rename(
        columns={
            "filename": "Archivo",
            "parent_folder_name": "Fecha pedido",
            "modified_dt": "Última modificación",
            "piezas": "Piezas",
        },
        inplace=True,
    )
    display_df["Última modificación"] = (
        display_df["Última modificación"].dt.tz_convert("Europe/Madrid").dt.strftime("%d-%m-%Y %H:%M:%S")
    )
    display_df.drop(columns=["file_id"], inplace=True)

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    result_options = [
        {
            "label": (
                f"{row.filename} -> {count_csv_pieces_from_drive(row.file_id)} piezas · {row.parent_folder_name} · "
                f"{row.modified_dt.tz_convert('Europe/Madrid').strftime('%d-%m-%Y %H:%M:%S') if pd.notna(row.modified_dt) else 's/f'}"
            ),
            "file_id": row.file_id,
        }
        for row in results_df.itertuples(index=False)
    ]

    selected_label = st.selectbox(
        "Selecciona un resultado para ver detalle",
        options=[opt["label"] for opt in result_options],
    )

    selected_option = next(opt for opt in result_options if opt["label"] == selected_label)
    st.session_state["selected_file_id"] = selected_option["file_id"]

selected_file_id = st.session_state.get("selected_file_id", "")
if not selected_file_id:
    st.stop()

selected_rows = index_df[index_df["file_id"] == selected_file_id]
if selected_rows.empty:
    st.warning("El pedido seleccionado ya no está disponible en el índice actual.")
    st.stop()

selected_row = selected_rows.iloc[0]
st.markdown("---")
st.subheader("Detalle")

st.markdown(f"**Proyecto detectado:** `{selected_row.get('project_key', '') or 'No detectado'}`")
st.markdown(f"**Archivo completo:** `{selected_row['filename']}`")
st.markdown(f"**Pedido enviado el:** `{selected_row['parent_folder_name']}`")
if selected_row.get("drive_link"):
    st.markdown(f"[🔗 Abrir en Drive]({selected_row['drive_link']})")

try:
    csv_df = load_csv_from_drive(selected_file_id)
    st.dataframe(csv_df, use_container_width=True, hide_index=True)

    csv_buffer = io.StringIO()
    csv_df.to_csv(csv_buffer, index=False)
    st.download_button(
        "⬇ Descargar CSV",
        data=csv_buffer.getvalue(),
        file_name=selected_row["filename"],
        mime="text/csv",
        use_container_width=False,
    )
except HttpError as exc:
    st.error("No se pudo descargar el CSV desde Drive. Revisa permisos de la service account.")
    st.code(repr(exc))
except Exception as exc:
    st.error("No se pudo leer el CSV seleccionado.")
    st.code(repr(exc))
