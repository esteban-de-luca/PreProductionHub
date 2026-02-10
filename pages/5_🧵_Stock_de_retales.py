# pages/5_🧵_Stock_de_retales.py
# Streamlit page: Stock de retales (Google Sheet read + edit)
# Requisitos: gspread, google-auth, pandas
# Secrets requeridos:
# [gdrive]
# retales_sheet_id = "1N1LVszjtuwfsdN4sl6AQ6Yw7nfJXZd2XByCrKVgNljA"
# retales_gid = "1069329295"
# [gdrive_sa]  (service account json completo)

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError

from ui_theme import apply_shared_sidebar

# =========================
# Config
# =========================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADER_ROW_1BASED = 5  # headers están en la fila 5; datos desde fila 6


# =========================
# Auth + Sheet helpers
# =========================
def _get_service_account_info() -> dict:
    sa_info = dict(st.secrets["gdrive_sa"])
    # Normaliza private_key por si viene con "\\n"
    if "private_key" in sa_info and isinstance(sa_info["private_key"], str):
        sa_info["private_key"] = sa_info["private_key"].replace("\\n", "\n")
    return sa_info


@st.cache_resource
def get_gspread_client() -> gspread.Client:
    sa_info = _get_service_account_info()
    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    return gspread.authorize(creds)


def open_retales_worksheet(gc: gspread.Client) -> gspread.Worksheet:
    gdrive_cfg = dict(st.secrets["gdrive"])
    sheet_id = gdrive_cfg.get("retales_sheet_id")
    gid = int(gdrive_cfg.get("retales_gid"))

    if not sheet_id:
        raise ValueError("Falta st.secrets['gdrive']['retales_sheet_id']")
    if not gid:
        raise ValueError("Falta st.secrets['gdrive']['retales_gid']")

    sh = gc.open_by_key(sheet_id)
    ws = next((w for w in sh.worksheets() if w.id == gid), None)
    if ws is None:
        available = [(w.title, w.id) for w in sh.worksheets()]
        raise ValueError(
            f"No encuentro worksheet con gid={gid}. Disponibles: {available}"
        )
    return ws


def _normalize_headers(raw_headers: list[str]) -> list[str]:
    headers: list[str] = []
    seen: dict[str, int] = {}

    for i, h in enumerate(raw_headers):
        name = (h or "").strip()
        if not name:
            name = f"col_{i+1}"

        base = name
        if base in seen:
            seen[base] += 1
            name = f"{base}_{seen[base]}"
        else:
            seen[base] = 0

        headers.append(name)

    return headers


def worksheet_to_df(values: list[list[str]], header_row_1based: int = HEADER_ROW_1BASED) -> pd.DataFrame:
    """
    values: lista de filas (cada fila lista de celdas) tal como ws.get_all_values().
    header_row_1based: fila del sheet que contiene los headers.
    """
    if not values:
        return pd.DataFrame()

    header_idx = header_row_1based - 1
    if len(values) <= header_idx:
        return pd.DataFrame()

    raw_headers = values[header_idx]
    data_rows = values[header_idx + 1 :]

    headers = _normalize_headers(raw_headers)

    n = len(headers)
    fixed_rows: list[list[str]] = []
    for r in data_rows:
        r = r or []
        if len(r) < n:
            r = r + [""] * (n - len(r))
        elif len(r) > n:
            r = r[:n]
        fixed_rows.append(r)

    df = pd.DataFrame(fixed_rows, columns=headers)

    # Elimina filas totalmente vacías (todas celdas vacías)
    if not df.empty:
        df_str = df.fillna("").astype(str).apply(lambda col: col.str.strip())
        df = df.loc[~df_str.eq("").all(axis=1)].reset_index(drop=True)

    return df


@st.cache_data(ttl=300)
def read_retales_sheet_cached(sheet_id: str, gid: int) -> tuple[str, int, list[list[str]]]:
    """
    Cachea únicamente el 'get_all_values' (data cruda).
    Devolvemos sheet_id y gid también para que el cache sea estable.
    """
    gc = get_gspread_client()
    sh = gc.open_by_key(sheet_id)
    ws = next((w for w in sh.worksheets() if w.id == gid), None)
    if ws is None:
        raise ValueError(f"No encuentro worksheet con gid={gid}")
    values = ws.get_all_values()
    return sheet_id, gid, values


def update_sheet_from_df(ws: gspread.Worksheet, df: pd.DataFrame, header_row_1based: int = HEADER_ROW_1BASED) -> None:
    """
    Mantiene intactas filas 1..(header_row_1based-1).
    Escribe headers en header_row_1based y datos desde header_row_1based+1.
    Nota: No hace ws.clear() para no borrar títulos/metadata en filas superiores.
    """
    df2 = df.copy()
    df2 = df2.fillna("").astype(str)

    start_row = header_row_1based  # headers aquí
    out = [df2.columns.tolist()] + df2.values.tolist()

    # Escribe a partir de columna A, fila start_row
    ws.update(f"A{start_row}", out)


# =========================
# UI
# =========================
st.set_page_config(page_title="Stock de retales", layout="wide")
apply_shared_sidebar("pages/5_🧵_Stock_de_retales.py")
st.title("🧵 Stock de retales")

# Leer secrets
gdrive_cfg = dict(st.secrets.get("gdrive", {}))
sheet_id = gdrive_cfg.get("retales_sheet_id", "")
gid_int = int(gdrive_cfg.get("retales_gid", "0") or 0)
sa_email = dict(st.secrets.get("gdrive_sa", {})).get("client_email", "¿desconocido?")

if not sheet_id or not gid_int:
    st.error(
        "Faltan secretos. Asegúrate de tener:\n"
        "- st.secrets['gdrive']['retales_sheet_id']\n"
        "- st.secrets['gdrive']['retales_gid']"
    )
    st.stop()

# Cargar worksheet y datos
try:
    gc = get_gspread_client()
    ws = open_retales_worksheet(gc)

    # Cacheamos la lectura cruda
    _, _, raw_values = read_retales_sheet_cached(sheet_id, gid_int)
    retales_df = worksheet_to_df(raw_values, header_row_1based=HEADER_ROW_1BASED)

except APIError as exc:
    st.error("Google Sheets APIError (probable permisos / 403).")
    st.code(
        f"sheet_id={sheet_id}\n"
        f"gid={gid_int}\n"
        f"service_account={sa_email}\n\n"
        f"{exc}"
    )
    st.stop()
except Exception as exc:
    st.error(f"No se pudo leer el Google Sheet ({type(exc).__name__}).")
    st.code(
        f"sheet_id={sheet_id}\n"
        f"gid={gid_int}\n"
        f"service_account={sa_email}\n"
        f"raw_error={exc!r}"
    )
    st.stop()

st.caption(f"Conectado a: {ws.title} (gid={ws.id}) · Service Account: {sa_email}")

# Editor
edited_df = st.data_editor(
    retales_df,
    use_container_width=True,
    num_rows="dynamic",
    key="retales_editor",
)

# Acciones
c1, c2, c3 = st.columns([1, 1, 6])

with c1:
    if st.button("Guardar cambios", type="primary"):
        try:
            update_sheet_from_df(ws, edited_df, header_row_1based=HEADER_ROW_1BASED)
            # Invalida cache de lectura y recarga
            read_retales_sheet_cached.clear()
            st.success("Cambios guardados ✅")
            st.rerun()
        except APIError as exc:
            st.error("No se pudo guardar (APIError).")
            st.code(str(exc))
        except Exception as exc:
            st.error(f"No se pudo guardar ({type(exc).__name__}).")
            st.code(repr(exc))

with c2:
    if st.button("Recargar"):
        read_retales_sheet_cached.clear()
        st.rerun()

with c3:
    st.info(
        "Headers leídos desde fila 5. Datos desde fila 6. "
        "Al guardar, se actualiza el bloque desde la fila 5 (sin borrar filas 1–4)."
    )
