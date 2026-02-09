import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

from ui_theme import apply_shared_sidebar

st.set_page_config(page_title="Stock de retales", layout="wide")

apply_shared_sidebar("pages/5_🧵_Stock_de_retales.py")
st.markdown("<style>h1 { font-size: 2.2rem !important; }</style>", unsafe_allow_html=True)

st.title("Stock de retales")

col_back, _ = st.columns([1, 5])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

st.caption("Permite consultar base de datos de retales en taller y añadir o quitar retales (marcar como utilizados)")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_gspread_client() -> gspread.Client:
    credentials = Credentials.from_service_account_info(
        st.secrets["gdrive_sa"],
        scopes=SCOPES,
    )
    return gspread.authorize(credentials)


def get_worksheet(sheet_id: str, gid: int) -> gspread.Worksheet:
    client = get_gspread_client()
    spreadsheet = client.open_by_key(sheet_id)
    for worksheet in spreadsheet.worksheets():
        if worksheet.id == gid:
            return worksheet
    raise ValueError(f"No existe un worksheet con gid={gid}.")


@st.cache_data(ttl=300)
def read_retales_sheet(sheet_id: str, gid: int) -> pd.DataFrame:
    worksheet = get_worksheet(sheet_id, gid)
    values = worksheet.get_all_values()
    if not values:
        return pd.DataFrame()
    header, *rows = values
    if not header:
        return pd.DataFrame()
    return pd.DataFrame(rows, columns=header)


gdrive_config = st.secrets.get("gdrive", {})
sheet_id = gdrive_config.get("retales_sheet_id")
gid = gdrive_config.get("retales_gid")
if not sheet_id or gid is None:
    st.error(
        "Faltan las claves en secrets: gdrive.retales_sheet_id y gdrive.retales_gid."
    )
    st.stop()

try:
    gid_int = int(gid)
except (TypeError, ValueError) as exc:
    st.error(f"El valor de gdrive.retales_gid debe ser un entero. Error: {exc}")
    st.stop()

try:
    retales_df = read_retales_sheet(sheet_id, gid_int)
except Exception as exc:
    st.error(f"No se pudo leer el Google Sheet: {exc}")
    st.stop()

edited_df = st.data_editor(
    retales_df,
    use_container_width=True,
    num_rows="dynamic",
    key="retales_editor",
)

col_save, col_reload, _ = st.columns([1, 1, 5])
with col_save:
    if st.button("Guardar cambios", type="primary"):
        try:
            worksheet = get_worksheet(sheet_id, gid_int)
            cleaned_df = edited_df.fillna("").astype(str)
            if cleaned_df.columns.size:
                output = [list(cleaned_df.columns)] + cleaned_df.values.tolist()
            else:
                output = [[]]
            worksheet.clear()
            worksheet.update(output)
            read_retales_sheet.clear()
            st.success("Cambios guardados correctamente.")
            st.rerun()
        except Exception as exc:
            st.error(f"No se pudieron guardar los cambios: {exc}")

with col_reload:
    if st.button("Recargar"):
        st.rerun()
