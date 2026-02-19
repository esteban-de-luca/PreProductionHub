import io
import re
import csv
from collections.abc import Mapping
from datetime import date, datetime, timedelta
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
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DEFAULT_ROOT_FOLDER_ID = "13B6qI-_fL_7aX3H0TI2Gb4aDF2ymXrWf"
PROJECT_KEY_REGEX = re.compile(r"\b(?:MEC[_-]?)?(SP[-_]\d{4,})\b", re.IGNORECASE)
EXACT_PROJECT_QUERY_REGEX = re.compile(r"^SP[-_]\d{4,}$", re.IGNORECASE)


SPAIN_2026_HOLIDAYS = {
    date(2026, 1, 1),
    date(2026, 1, 6),
    date(2026, 4, 3),
    date(2026, 5, 1),
    date(2026, 8, 15),
    date(2026, 10, 12),
    date(2026, 11, 1),
    date(2026, 12, 6),
    date(2026, 12, 8),
    date(2026, 12, 25),
}


def add_business_days(start_date: date, days: int, holidays: set[date]) -> date:
    current = start_date
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() >= 5:
            continue
        if current in holidays:
            continue
        added += 1
    return current


def estimate_departure_date(folder_date_text: str) -> str:
    try:
        order_date = datetime.strptime(folder_date_text, "%d-%m-%y").date()
    except Exception:
        return "s/f"

    estimated = add_business_days(order_date, 8, SPAIN_2026_HOLIDAYS)
    return estimated.strftime("%d-%m-%Y")


def estimate_departure_date_from_date(order_date: date) -> date:
    return add_business_days(order_date, 8, SPAIN_2026_HOLIDAYS)


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


@st.cache_resource
def get_sheets_service():
    try:
        service_account_info = st.secrets["gcp_service_account"]
    except Exception as exc:
        raise RuntimeError(
            "Falta la configuración 'gcp_service_account' en st.secrets. "
            "Añade el JSON de service account para habilitar la caché en Google Sheets."
        ) from exc

    try:
        creds = Credentials.from_service_account_info(
            service_account_info,
            scopes=[SHEETS_SCOPE],
        )
        return build("sheets", "v4", credentials=creds)
    except Exception as exc:
        raise RuntimeError(
            "No se pudo autenticar con Google Sheets. Revisa credenciales y permisos de la service account."
        ) from exc


def resolve_cache_config() -> tuple[str, str]:
    sheet_id = ""
    worksheet_name = "pieces_cache"

    if "alvic_orders_cache" in st.secrets:
        cache_cfg = st.secrets["alvic_orders_cache"]
        if not isinstance(cache_cfg, Mapping):
            raise RuntimeError(
                "La configuración 'alvic_orders_cache' debe ser una tabla en secrets.toml con la clave 'sheet_id'."
            )
        sheet_id = str(cache_cfg.get("sheet_id", "")).strip()
        worksheet_name = str(cache_cfg.get("worksheet_name", "pieces_cache")).strip() or "pieces_cache"

    sheet_id = str(st.secrets.get("ALVIC_ORDERS_CACHE_SHEET_ID", sheet_id)).strip()
    worksheet_name = (
        str(st.secrets.get("ALVIC_ORDERS_CACHE_WORKSHEET_NAME", worksheet_name)).strip() or "pieces_cache"
    )

    if not sheet_id:
        raise RuntimeError(
            "Falta configurar la caché de piezas: define 'alvic_orders_cache.sheet_id' "
            "(o 'ALVIC_ORDERS_CACHE_SHEET_ID') en st.secrets."
        )

    return sheet_id, worksheet_name


def _sheet_header_range(worksheet_name: str) -> str:
    return f"{worksheet_name}!A1:G1"


def _sheet_full_range(worksheet_name: str) -> str:
    return f"{worksheet_name}!A:G"


def parse_sheet_bool(value) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {"true", "1", "yes", "si", "sí", "x"}


@st.cache_data(ttl=900)
def load_pieces_cache(sheet_id: str, worksheet_name: str) -> dict[str, dict]:
    service = get_sheets_service()
    values_api = service.spreadsheets().values()

    headers = [
        "file_id",
        "filename",
        "parent_folder_name",
        "modified_time",
        "pieces_count",
        "computed_at",
        "pedido_confirmado",
    ]

    try:
        header_resp = values_api.get(
            spreadsheetId=sheet_id,
            range=_sheet_header_range(worksheet_name),
        ).execute()
        existing_header = header_resp.get("values", [[]])
        if not existing_header or existing_header[0] != headers:
            values_api.update(
                spreadsheetId=sheet_id,
                range=_sheet_header_range(worksheet_name),
                valueInputOption="RAW",
                body={"values": [headers]},
            ).execute()

        rows_resp = values_api.get(
            spreadsheetId=sheet_id,
            range=_sheet_full_range(worksheet_name),
        ).execute()
    except HttpError as exc:
        raise RuntimeError("No se pudo leer/escribir la caché de piezas en Google Sheets.") from exc

    rows = rows_resp.get("values", [])
    cache: dict[str, dict] = {}
    for row in rows[1:]:
        padded = row + [""] * (7 - len(row))
        file_id = str(padded[0]).strip()
        if not file_id:
            continue
        pedido_confirmado = parse_sheet_bool(padded[6])
        try:
            pieces_value = int(float(str(padded[4]).strip()))
        except Exception:
            pieces_value = None

        cache[file_id] = {
            "file_id": file_id,
            "filename": str(padded[1]),
            "parent_folder_name": str(padded[2]),
            "modified_time": str(padded[3]),
            "pieces_count": pieces_value,
            "computed_at": str(padded[5]),
            "pedido_confirmado": pedido_confirmado,
        }
    return cache


def upsert_piece_cache_row(sheet_id: str, worksheet_name: str, row_data: dict) -> None:
    service = get_sheets_service()
    values_api = service.spreadsheets().values()

    try:
        rows_resp = values_api.get(
            spreadsheetId=sheet_id,
            range=f"{worksheet_name}!A:A",
        ).execute()
    except HttpError as exc:
        raise RuntimeError("No se pudo consultar la caché de piezas para actualizarla.") from exc

    rows = rows_resp.get("values", [])
    row_index = None
    for idx, row in enumerate(rows, start=1):
        if row and str(row[0]).strip() == row_data["file_id"]:
            row_index = idx
            break

    payload = [
        row_data["file_id"],
        row_data.get("filename", ""),
        row_data.get("parent_folder_name", ""),
        row_data.get("modified_time", ""),
        int(row_data.get("pieces_count", 0)),
        row_data.get("computed_at", ""),
        bool(row_data.get("pedido_confirmado", False)),
    ]

    if row_index is None:
        update_range = f"{worksheet_name}!A:G"
        method = values_api.append
        extra_args = {"insertDataOption": "INSERT_ROWS"}
    else:
        update_range = f"{worksheet_name}!A{row_index}:G{row_index}"
        method = values_api.update
        extra_args = {}

    try:
        method(
            spreadsheetId=sheet_id,
            range=update_range,
            valueInputOption="RAW",
            body={"values": [payload]},
            **extra_args,
        ).execute()
    except HttpError as exc:
        raise RuntimeError("No se pudo guardar la caché de piezas en Google Sheets.") from exc


def update_confirmations_in_cache(
    sheets_service,
    sheet_id: str,
    worksheet_name: str,
    updates: list[dict],
    current_cache: dict[str, dict],
    rows_index: dict[str, int] | None = None,
) -> dict[str, int]:
    if not updates:
        return rows_index or {}

    values_api = sheets_service.spreadsheets().values()
    normalized_updates = {
        str(item.get("file_id", "")).strip(): bool(item.get("pedido_confirmado", False))
        for item in updates
        if str(item.get("file_id", "")).strip()
    }
    if not normalized_updates:
        return rows_index or {}

    if rows_index is None:
        rows_resp = values_api.get(spreadsheetId=sheet_id, range=f"{worksheet_name}!A:A").execute()
        rows = rows_resp.get("values", [])
        rows_index = {
            str(row[0]).strip(): idx
            for idx, row in enumerate(rows, start=1)
            if row and str(row[0]).strip()
        }

    write_ranges: list[dict] = []
    append_rows: list[list] = []
    for file_id, is_confirmed in normalized_updates.items():
        row_number = rows_index.get(file_id)
        if row_number is not None:
            write_ranges.append(
                {
                    "range": f"{worksheet_name}!G{row_number}",
                    "values": [[bool(is_confirmed)]],
                }
            )
            continue

        cached = current_cache.get(file_id, {})
        append_rows.append(
            [
                file_id,
                cached.get("filename", ""),
                cached.get("parent_folder_name", ""),
                cached.get("modified_time", ""),
                "" if cached.get("pieces_count") is None else int(cached.get("pieces_count", 0)),
                cached.get("computed_at", ""),
                bool(is_confirmed),
            ]
        )

    if write_ranges:
        values_api.batchUpdate(
            spreadsheetId=sheet_id,
            body={"valueInputOption": "USER_ENTERED", "data": write_ranges},
        ).execute()

    if append_rows:
        values_api.append(
            spreadsheetId=sheet_id,
            range=f"{worksheet_name}!A:G",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": append_rows},
        ).execute()

        rows_resp = values_api.get(spreadsheetId=sheet_id, range=f"{worksheet_name}!A:A").execute()
        rows = rows_resp.get("values", [])
        rows_index = {
            str(row[0]).strip(): idx
            for idx, row in enumerate(rows, start=1)
            if row and str(row[0]).strip()
        }

    return rows_index

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

if "pieces_cache" not in st.session_state:
    st.session_state["pieces_cache"] = {}

if "pieces_cache_rows_index" not in st.session_state:
    st.session_state["pieces_cache_rows_index"] = {}

if "sheets_cache_available" not in st.session_state:
    st.session_state["sheets_cache_available"] = True

if st.sidebar.button("🔄 Actualizar índice", use_container_width=True):
    build_index.clear()
    load_pieces_cache.clear()
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

CACHE_SHEET_ID = ""
CACHE_WORKSHEET_NAME = ""
try:
    CACHE_SHEET_ID, CACHE_WORKSHEET_NAME = resolve_cache_config()
    st.session_state["pieces_cache"] = load_pieces_cache(CACHE_SHEET_ID, CACHE_WORKSHEET_NAME)
    st.session_state["sheets_cache_available"] = True
except Exception as exc:
    st.session_state["pieces_cache"] = {}
    st.session_state["pieces_cache_rows_index"] = {}
    st.session_state["sheets_cache_available"] = False
    st.warning(
        "La caché de Google Sheets no está disponible ahora mismo. "
        "La columna de confirmación se mostrará en solo lectura.")
    st.caption(f"Detalle: {exc}")

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

st.sidebar.markdown("---")
st.sidebar.markdown("### 🗓️ Calculadora fecha estimada")
sidebar_order_date = st.sidebar.date_input("Fecha de pedido", value=date.today(), format="DD/MM/YYYY")
if isinstance(sidebar_order_date, date):
    sidebar_estimated = estimate_departure_date_from_date(sidebar_order_date)
    st.sidebar.markdown(
        f"<p style='font-size:1em; margin:0.25rem 0 0.5rem 0;'>Fecha estimada de salida (+8 días laborables): <strong>{sidebar_estimated.strftime('%d/%m/%Y')}</strong></p>",
        unsafe_allow_html=True,
    )
    if sidebar_order_date.year != 2026 or sidebar_estimated.year != 2026:
        st.sidebar.warning("La calculadora aplica festivos nacionales de 2026; fuera de ese año solo se excluyen fines de semana y festivos 2026.")

query_text = st.session_state.get("alvic_search_query", "")
results_df = search_index(index_df, query_text, selected_dates, exact_mode)

st.subheader("Resultados")

if results_df.empty:
    st.info("No se encontraron pedidos con ese criterio.")
else:
    if len(results_df) == 1:
        st.session_state["selected_file_id"] = str(results_df.iloc[0]["file_id"])

    filename_series = (
        results_df["filename"]
        if "filename" in results_df.columns
        else results_df.get("Archivo", pd.Series([""] * len(results_df), index=results_df.index))
    )
    order_date_series = (
        results_df["parent_folder_name"]
        if "parent_folder_name" in results_df.columns
        else results_df.get("Fecha pedido", pd.Series([""] * len(results_df), index=results_df.index))
    )
    modified_series = (
        results_df["modified_dt"]
        if "modified_dt" in results_df.columns
        else results_df.get("Última modificación", pd.Series([pd.NaT] * len(results_df), index=results_df.index))
    )
    file_id_series = results_df.get("file_id", pd.Series([""] * len(results_df), index=results_df.index))

    display_df = pd.DataFrame(index=results_df.index)
    display_df["Archivo"] = filename_series.fillna("").astype(str)
    pieces_cache = st.session_state.get("pieces_cache", {})

    def resolve_cached_pieces(row) -> str:
        file_id = str(getattr(row, "file_id", "") or "").strip()
        if not file_id:
            return "—"
        cached = pieces_cache.get(file_id)
        if not cached:
            return "—"

        current_modified = str(getattr(row, "modified_time", "") or "")
        cached_modified = str(cached.get("modified_time", "") or "")
        if current_modified and cached_modified and current_modified == cached_modified:
            return str(cached.get("pieces_count", "—"))
        return "—"

    display_df["Piezas"] = [resolve_cached_pieces(row) for row in results_df.itertuples(index=False)]
    display_df["Fecha de pedido"] = (
        pd.to_datetime(order_date_series, format="%d-%m-%y", errors="coerce").dt.strftime("%d-%m-%Y").fillna("s/f")
    )
    display_df["Fecha estimada de salida"] = order_date_series.fillna("").astype(str).apply(estimate_departure_date)

    modified_dt_series = pd.to_datetime(modified_series, errors="coerce", utc=True)
    display_df["Última modificación"] = modified_dt_series.apply(
        lambda dt: dt.tz_convert("Europe/Madrid").strftime("%d-%m-%Y %H:%M:%S") if pd.notna(dt) else "s/f"
    )

    display_df["file_id"] = file_id_series.fillna("").astype(str)
    display_df["Confirmado"] = display_df["file_id"].apply(
        lambda file_id: bool(st.session_state.get("pieces_cache", {}).get(file_id, {}).get("pedido_confirmado", False))
    )

    display_df = display_df[
        [
            "Archivo",
            "Piezas",
            "Fecha de pedido",
            "Fecha estimada de salida",
            "Última modificación",
            "file_id",
            "Confirmado",
        ]
    ]

    table_df = display_df.set_index("file_id", drop=True)
    editor_key = "alvic_historial_confirmado_editor"
    edited_df = st.data_editor(
        table_df,
        use_container_width=True,
        hide_index=True,
        key=editor_key,
        column_config={
            "Archivo": st.column_config.TextColumn(disabled=True),
            "Piezas": st.column_config.TextColumn(disabled=True),
            "Fecha de pedido": st.column_config.TextColumn(disabled=True),
            "Fecha estimada de salida": st.column_config.TextColumn(disabled=True),
            "Última modificación": st.column_config.TextColumn(disabled=True),
            "Confirmado": st.column_config.CheckboxColumn(
                "Confirmado",
                disabled=not st.session_state.get("sheets_cache_available", False),
            ),
        },
        disabled=[
            "Archivo",
            "Piezas",
            "Fecha de pedido",
            "Fecha estimada de salida",
            "Última modificación",
        ],
    )

    before_confirmed = table_df["Confirmado"].fillna(False).astype(bool)
    after_confirmed = edited_df["Confirmado"].fillna(False).astype(bool)
    changed_file_ids = before_confirmed.index[before_confirmed != after_confirmed]

    if len(changed_file_ids) > 0 and st.session_state.get("sheets_cache_available", False):
        updates = [
            {
                "file_id": file_id,
                "pedido_confirmado": bool(after_confirmed.loc[file_id]),
            }
            for file_id in changed_file_ids
        ]
        try:
            sheets_service = get_sheets_service()
            new_rows_index = update_confirmations_in_cache(
                sheets_service=sheets_service,
                sheet_id=CACHE_SHEET_ID,
                worksheet_name=CACHE_WORKSHEET_NAME,
                updates=updates,
                current_cache=st.session_state.get("pieces_cache", {}),
                rows_index=st.session_state.get("pieces_cache_rows_index") or None,
            )
            st.session_state["pieces_cache_rows_index"] = new_rows_index
            for item in updates:
                file_id = item["file_id"]
                existing = st.session_state["pieces_cache"].get(file_id, {})
                source_rows = results_df[results_df["file_id"] == file_id]
                source_row = source_rows.iloc[0] if not source_rows.empty else {}
                st.session_state["pieces_cache"][file_id] = {
                    "file_id": file_id,
                    "filename": existing.get("filename") or source_row.get("filename", ""),
                    "parent_folder_name": existing.get("parent_folder_name") or source_row.get("parent_folder_name", ""),
                    "modified_time": existing.get("modified_time") or source_row.get("modified_time", ""),
                    "pieces_count": existing.get("pieces_count"),
                    "computed_at": existing.get("computed_at", ""),
                    "pedido_confirmado": bool(item["pedido_confirmado"]),
                }
        except Exception as exc:
            st.warning("No se pudo guardar la confirmación en Google Sheets.")
            st.caption(f"Detalle: {exc}")
            st.session_state["sheets_cache_available"] = False
            st.rerun()

    result_options = [
        {
            "label": getattr(row, "filename", getattr(row, "Archivo", "")),
            "file_id": getattr(row, "file_id", ""),
        }
        for row in results_df.itertuples(index=False)
    ]

    selected_option = st.selectbox(
        "Selecciona un resultado para ver detalle",
        options=result_options,
        format_func=lambda opt: opt["label"],
    )

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

st.markdown(f"**Archivo completo:** `{selected_row['filename']}`")
st.markdown(f"**Pedido enviado el:** `{selected_row['parent_folder_name']}`")
if selected_row.get("drive_link"):
    st.markdown(f"[🔗 Abrir en Drive]({selected_row['drive_link']})")

try:
    pieces_cache = st.session_state.get("pieces_cache", {})
    cached_entry = pieces_cache.get(selected_file_id)
    current_modified_time = str(selected_row.get("modified_time", "") or "")

    selected_pieces = None
    if cached_entry and str(cached_entry.get("modified_time", "") or "") == current_modified_time:
        selected_pieces = int(cached_entry.get("pieces_count", 0))
    else:
        st.info("Calculando piezas para este pedido…")
        selected_pieces = count_csv_pieces_from_drive(selected_file_id)
        updated_cache_row = {
            "file_id": selected_file_id,
            "filename": str(selected_row.get("filename", "") or ""),
            "parent_folder_name": str(selected_row.get("parent_folder_name", "") or ""),
            "modified_time": current_modified_time,
            "pieces_count": int(selected_pieces),
            "computed_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
        if st.session_state.get("sheets_cache_available", False) and CACHE_SHEET_ID:
            upsert_piece_cache_row(CACHE_SHEET_ID, CACHE_WORKSHEET_NAME, updated_cache_row)
            load_pieces_cache.clear()
        pieces_cache[selected_file_id] = {
            **updated_cache_row,
            "pedido_confirmado": bool(cached_entry.get("pedido_confirmado", False)) if cached_entry else False,
        }
        st.session_state["pieces_cache"] = pieces_cache

    st.markdown(f"**Piezas:** `{selected_pieces}`")

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
