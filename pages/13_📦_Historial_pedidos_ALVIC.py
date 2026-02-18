import io
import re
import csv
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
CACHE_HEADERS = [
    "file_id",
    "filename",
    "parent_folder_name",
    "modified_time",
    "pieces_count",
    "computed_at",
]


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
            "Falta la configuración 'gcp_service_account' en st.secrets para Google Sheets."
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


def resolve_cache_settings() -> tuple[str, str]:
    try:
        cache_secrets = st.secrets["alvic_orders_cache"]
        sheet_id = str(cache_secrets["sheet_id"])
        worksheet_name = str(cache_secrets.get("worksheet_name", "pieces_cache"))
        return sheet_id, worksheet_name
    except Exception as exc:
        raise RuntimeError(
            "Falta la configuración [alvic_orders_cache] en st.secrets con sheet_id."
        ) from exc


def ensure_cache_worksheet(service, sheet_id: str, worksheet_name: str) -> None:
    metadata = (
        service.spreadsheets()
        .get(spreadsheetId=sheet_id, fields="sheets.properties.sheetId,sheets.properties.title")
        .execute()
    )
    sheets = metadata.get("sheets", [])
    existing_titles = {sheet.get("properties", {}).get("title", "") for sheet in sheets}

    if worksheet_name not in existing_titles:
        (
            service.spreadsheets()
            .batchUpdate(
                spreadsheetId=sheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": worksheet_name}}}]},
            )
            .execute()
        )

    header_resp = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=f"{worksheet_name}!1:1")
        .execute()
    )
    current_header = (header_resp.get("values", []) or [[]])[0]
    if current_header != CACHE_HEADERS:
        (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=sheet_id,
                range=f"{worksheet_name}!A1:F1",
                valueInputOption="RAW",
                body={"values": [CACHE_HEADERS]},
            )
            .execute()
        )


@st.cache_data(ttl=600)
def load_pieces_cache(sheet_id: str, worksheet_name: str) -> dict[str, dict]:
    service = get_sheets_service()
    ensure_cache_worksheet(service, sheet_id, worksheet_name)
    response = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=f"{worksheet_name}!A2:F")
        .execute()
    )

    cache: dict[str, dict] = {}
    for raw_row in response.get("values", []) or []:
        row = list(raw_row) + [""] * (len(CACHE_HEADERS) - len(raw_row))
        file_id = str(row[0]).strip()
        if not file_id:
            continue
        try:
            pieces_count = int(str(row[4]).strip())
        except Exception:
            pieces_count = 0
        cache[file_id] = {
            "pieces_count": pieces_count,
            "modified_time": str(row[3]).strip(),
            "filename": str(row[1]).strip(),
            "parent_folder_name": str(row[2]).strip(),
        }
    return cache


def upsert_cache_rows(sheet_id: str, worksheet_name: str, rows: list[dict]) -> None:
    if not rows:
        return

    service = get_sheets_service()
    ensure_cache_worksheet(service, sheet_id, worksheet_name)
    response = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=f"{worksheet_name}!A2:A")
        .execute()
    )

    existing = response.get("values", []) or []
    file_id_to_row = {
        str(values[0]).strip(): idx + 2
        for idx, values in enumerate(existing)
        if values and str(values[0]).strip()
    }

    updates_data = []
    append_values = []
    seen_file_ids: set[str] = set()
    for row in rows:
        file_id = str(row.get("file_id", "")).strip()
        if not file_id or file_id in seen_file_ids:
            continue
        seen_file_ids.add(file_id)

        values = [
            file_id,
            str(row.get("filename", "")),
            str(row.get("parent_folder_name", "")),
            str(row.get("modified_time", "")),
            int(row.get("pieces_count", 0)),
            str(row.get("computed_at", "")),
        ]

        target_row = file_id_to_row.get(file_id)
        if target_row:
            updates_data.append({"range": f"{worksheet_name}!A{target_row}:F{target_row}", "values": [values]})
        else:
            append_values.append(values)

    if updates_data:
        (
            service.spreadsheets()
            .values()
            .batchUpdate(
                spreadsheetId=sheet_id,
                body={"valueInputOption": "RAW", "data": updates_data},
            )
            .execute()
        )

    if append_values:
        (
            service.spreadsheets()
            .values()
            .append(
                spreadsheetId=sheet_id,
                range=f"{worksheet_name}!A:F",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": append_values},
            )
            .execute()
        )


def _decode_csv_text(raw_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw_bytes.decode(encoding)
        except Exception:
            continue
    raise RuntimeError("No se pudo leer el CSV descargado. Revisa codificación del archivo.")


def _guess_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="|;,\t")
        return dialect.delimiter
    except Exception:
        if "|" in sample:
            return "|"
        if ";" in sample:
            return ";"
        return ","


def _looks_like_header(first_row: list[str], second_row: list[str] | None) -> bool:
    cleaned_first = [str(cell).strip() for cell in first_row]
    if not cleaned_first:
        return False
    if all(re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ_]", cell) for cell in cleaned_first if cell):
        return True

    if not second_row:
        return False

    def numeric_ratio(row: list[str]) -> float:
        if not row:
            return 0.0
        numeric = 0
        valid = 0
        for cell in row:
            token = str(cell).strip().replace(",", ".")
            if not token:
                continue
            valid += 1
            try:
                float(token)
                numeric += 1
            except Exception:
                pass
        return (numeric / valid) if valid else 0.0

    return numeric_ratio(cleaned_first) < numeric_ratio([str(cell).strip() for cell in second_row])


def count_csv_pieces_from_bytes(raw_bytes: bytes) -> int:
    text = _decode_csv_text(raw_bytes)
    non_empty_lines = [line for line in text.splitlines() if line.strip()]
    if not non_empty_lines:
        return 0

    sample = "\n".join(non_empty_lines[:20])
    delimiter = _guess_delimiter(sample)
    reader = csv.reader(non_empty_lines, delimiter=delimiter)
    parsed_rows = [row for row in reader if any(str(cell).strip() for cell in row)]
    if not parsed_rows:
        return 0

    has_header = _looks_like_header(parsed_rows[0], parsed_rows[1] if len(parsed_rows) > 1 else None)
    return max(len(parsed_rows) - (1 if has_header else 0), 0)


def _download_csv_bytes_with_service(service, file_id: str) -> bytes:
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with io.BytesIO() as buffer:
        downloader = MediaIoBaseDownload(buffer, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        return buffer.getvalue()


def get_pieces_count_with_cache(
    drive_service,
    sheets_service,
    cache: dict[str, dict],
    file_id: str,
    filename: str,
    parent_folder_name: str,
    drive_modified_time: str,
) -> int:
    cached = cache.get(file_id)
    if cached and str(cached.get("modified_time", "")) == str(drive_modified_time):
        return int(cached.get("pieces_count", 0))

    pieces_count = count_csv_pieces_from_bytes(_download_csv_bytes_with_service(drive_service, file_id))
    row = {
        "file_id": file_id,
        "filename": filename,
        "parent_folder_name": parent_folder_name,
        "modified_time": drive_modified_time,
        "pieces_count": pieces_count,
        "computed_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    if "alvic_cache_pending_rows" not in st.session_state:
        st.session_state["alvic_cache_pending_rows"] = []
    st.session_state["alvic_cache_pending_rows"].append(row)
    cache[file_id] = {
        "pieces_count": pieces_count,
        "modified_time": drive_modified_time,
        "filename": filename,
        "parent_folder_name": parent_folder_name,
    }
    return pieces_count


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
    return _download_csv_bytes_with_service(service, file_id)


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

            with io.BytesIO(raw_bytes) as data_stream:
                return pd.read_csv(data_stream, encoding=encoding, sep=sep)
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
if "alvic_cache_pending_rows" not in st.session_state:
    st.session_state["alvic_cache_pending_rows"] = []

if st.sidebar.button("🔄 Actualizar índice", use_container_width=True):
    build_index.clear()
    load_pieces_cache.clear()
    st.toast("Índice invalidado. Reconstruyendo…", icon="🔄")
    st.rerun()

cache_ready = True
cache_error_message = ""
pieces_cache: dict[str, dict] = {}
cache_sheet_id = ""
cache_worksheet_name = ""
sheets_service = None

try:
    cache_sheet_id, cache_worksheet_name = resolve_cache_settings()
    sheets_service = get_sheets_service()
    pieces_cache = load_pieces_cache(cache_sheet_id, cache_worksheet_name)
except Exception as exc:
    cache_ready = False
    cache_error_message = str(exc)
    pieces_cache = {}
    st.warning(f"La caché de piezas no está disponible. Se mostrará '—' hasta poder calcular. Detalle: {exc}")

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


def flush_pending_cache_rows() -> None:
    pending_rows = st.session_state.get("alvic_cache_pending_rows", [])
    if not pending_rows or not cache_ready or not sheets_service:
        return

    dedup: dict[str, dict] = {}
    for row in pending_rows:
        row_file_id = str(row.get("file_id", "")).strip()
        if row_file_id:
            dedup[row_file_id] = row

    if not dedup:
        st.session_state["alvic_cache_pending_rows"] = []
        return

    upsert_cache_rows(cache_sheet_id, cache_worksheet_name, list(dedup.values()))
    st.session_state["alvic_cache_pending_rows"] = []
    load_pieces_cache.clear()

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
    display_df["Piezas"] = file_id_series.apply(
        lambda fid: pieces_cache.get(fid, {}).get("pieces_count", "—") if fid and cache_ready else "—"
    )
    display_df["Fecha de pedido"] = (
        pd.to_datetime(order_date_series, format="%d-%m-%y", errors="coerce").dt.strftime("%d-%m-%Y").fillna("s/f")
    )
    display_df["Fecha estimada de salida"] = order_date_series.fillna("").astype(str).apply(estimate_departure_date)

    modified_dt_series = pd.to_datetime(modified_series, errors="coerce", utc=True)
    display_df["Última modificación"] = modified_dt_series.apply(
        lambda dt: dt.tz_convert("Europe/Madrid").strftime("%d-%m-%Y %H:%M:%S") if pd.notna(dt) else "s/f"
    )

    display_df = display_df[
        [
            "Archivo",
            "Piezas",
            "Fecha de pedido",
            "Fecha estimada de salida",
            "Última modificación",
        ]
    ]

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    if st.sidebar.button("⚡ Calcular piezas (solo nuevos/modificados)", use_container_width=True):
        if not cache_ready or not sheets_service:
            st.warning(
                "No se puede calcular piezas porque la caché de Google Sheets no está disponible. "
                f"Detalle: {cache_error_message or 'Sin detalle adicional.'}"
            )
        else:
            try:
                drive_service = get_drive_service()
                processed_count = 0
                recalculated_count = 0
                for row in results_df.itertuples(index=False):
                    row_file_id = str(getattr(row, "file_id", "")).strip()
                    if not row_file_id:
                        continue
                    row_modified = str(getattr(row, "modified_time", ""))
                    cached = pieces_cache.get(row_file_id)
                    if cached and str(cached.get("modified_time", "")) == row_modified:
                        continue
                    get_pieces_count_with_cache(
                        drive_service,
                        sheets_service,
                        pieces_cache,
                        row_file_id,
                        str(getattr(row, "filename", "")),
                        str(getattr(row, "parent_folder_name", "")),
                        row_modified,
                    )
                    processed_count += 1
                    recalculated_count += 1

                flush_pending_cache_rows()
                st.success(
                    f"Cálculo completado. Recalculados: {recalculated_count}. "
                    f"Pedidos revisados: {len(results_df)}."
                )
                if processed_count > 0:
                    st.rerun()
            except HttpError as exc:
                st.warning("No se pudieron calcular piezas por un error de Google API.")
                st.code(repr(exc))
            except Exception as exc:
                st.warning("Error inesperado al calcular piezas incrementales.")
                st.code(repr(exc))

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

if cache_ready and sheets_service:
    try:
        detail_pieces = get_pieces_count_with_cache(
            get_drive_service(),
            sheets_service,
            pieces_cache,
            selected_file_id,
            str(selected_row.get("filename", "")),
            str(selected_row.get("parent_folder_name", "")),
            str(selected_row.get("modified_time", "")),
        )
        flush_pending_cache_rows()
        st.markdown(f"**Piezas:** `{detail_pieces}`")
    except Exception as exc:
        st.warning(f"No se pudo calcular piezas en detalle: {exc}")
else:
    st.markdown("**Piezas:** `—`")

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
