from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib import error, parse, request

import pandas as pd
import streamlit as st

from ui_theme import apply_shared_sidebar
from utils.gsheets_io import get_sheets_service

SPREADSHEET_ID = "1WUgFlI1ea4OcWTyFGfJCcEKWBhaHIDj89GiXN02Fr2w"
WIKI_PATH = Path("knowledge/wiki_cubro_ia.md")
DEFAULT_USER_PROMPT = (
    "Analiza este despiece contrastándolo con la Wiki CUBRO IA. Detecta inconsistencias, "
    "riesgos de fabricación o montaje, posibles errores y observaciones relevantes. "
    "No inventes información que no esté en los datos del proyecto o en la wiki."
)

st.set_page_config(page_title="Revisión Técnica IA", layout="wide")
apply_shared_sidebar("pages/16_🤖_Revisión_Técnica_IA.py")


@st.cache_data(ttl=900)
def get_spreadsheet(spreadsheet_id: str) -> dict[str, Any]:
    service = get_sheets_service()
    return (
        service.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            fields="properties.title,sheets.properties.title,sheets.properties.sheetId",
        )
        .execute()
    )


@st.cache_data(ttl=900)
def list_worksheets(spreadsheet_id: str) -> list[str]:
    spreadsheet = get_spreadsheet(spreadsheet_id)
    sheets = spreadsheet.get("sheets", [])
    names = [str(s.get("properties", {}).get("title", "")).strip() for s in sheets]
    return [name for name in names if name]


@st.cache_data(ttl=900)
def read_worksheet_values(spreadsheet_id: str, worksheet_name: str) -> list[list[Any]]:
    service = get_sheets_service()
    response = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=f"'{worksheet_name}'",
            valueRenderOption="UNFORMATTED_VALUE",
        )
        .execute()
    )
    return response.get("values", []) or []


def first_row_is_header(values: list[list[Any]]) -> bool:
    if not values or not values[0]:
        return False
    first_cell = str(values[0][0]).strip()
    return first_cell.startswith("ID Proyecto")


def _make_unique_columns(columns: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    unique_cols: list[str] = []
    for raw in columns:
        col = str(raw).strip() or "col"
        if col not in counts:
            counts[col] = 0
            unique_cols.append(col)
            continue
        counts[col] += 1
        unique_cols.append(f"{col}_{counts[col]}")
    return unique_cols


def _pad_rows(values: list[list[Any]]) -> list[list[Any]]:
    max_cols = max((len(row) for row in values), default=0)
    return [list(row) + [""] * (max_cols - len(row)) for row in values]


def load_sheet_as_dataframe(spreadsheet_id: str, worksheet_name: str) -> pd.DataFrame:
    values = read_worksheet_values(spreadsheet_id, worksheet_name)
    if not values:
        return pd.DataFrame()

    padded_values = _pad_rows(values)
    if not padded_values or not padded_values[0]:
        return pd.DataFrame()

    if first_row_is_header(padded_values):
        headers = _make_unique_columns([str(cell).strip() for cell in padded_values[0]])
        body = padded_values[1:]
        if not body:
            return pd.DataFrame(columns=headers)
        df = pd.DataFrame(body, columns=headers)
    else:
        n_cols = len(padded_values[0])
        auto_cols = [f"col_{idx + 1}" for idx in range(n_cols)]
        df = pd.DataFrame(padded_values, columns=auto_cols)

    return clean_dataframe(df)


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    cleaned = df.copy()
    cleaned.columns = [str(col).strip() for col in cleaned.columns]
    cleaned = cleaned.replace(r"^\s*$", pd.NA, regex=True)
    cleaned = cleaned.dropna(axis=0, how="all").dropna(axis=1, how="all")
    return cleaned.reset_index(drop=True)


def read_local_wiki(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo de wiki: {path}")
    return path.read_text(encoding="utf-8")


def dataframe_to_prompt_block(df: pd.DataFrame, max_rows: int = 2000) -> str:
    sample_df = df.head(max_rows)
    csv_text = sample_df.to_csv(index=False)
    note = ""
    if len(df) > max_rows:
        note = (
            f"\n\n[Nota: se enviaron las primeras {max_rows} filas de {len(df)} por límite de tamaño.]"
        )
    return f"Formato CSV:\n{csv_text}{note}"


def build_gemini_prompt(
    *,
    wiki_text: str,
    project_name: str,
    project_df: pd.DataFrame,
    user_prompt: str,
) -> str:
    effective_user_prompt = user_prompt.strip() or DEFAULT_USER_PROMPT
    project_block = dataframe_to_prompt_block(project_df)

    return f"""
## Rol del modelo
Eres un analista técnico de proyectos CUBRO. Debes revisar despieces de proyecto contrastándolos con la Wiki CUBRO IA.
No inventes reglas. Basa el análisis únicamente en la wiki y en los datos del proyecto.

## Objetivo
Analiza el proyecto, detecta inconsistencias, riesgos, posibles errores y observaciones técnicas relevantes.

## Reglas de salida
- Responde en texto normal o markdown simple.
- No devuelvas JSON.
- Si algo no se puede verificar con la wiki o los datos, indícalo explícitamente.
- Señala claramente qué es certeza y qué es sospecha.

## Wiki CUBRO IA
{wiki_text}

## Proyecto seleccionado
Nombre de proyecto/pestaña: {project_name}

Despiece completo:
{project_block}

## Instrucción libre del usuario
{effective_user_prompt}
""".strip()


def get_gemini_api_key() -> str:
    key_candidates = [
        st.secrets.get("gemini_api_key"),
        st.secrets.get("GEMINI_API_KEY"),
    ]

    gemini_block = st.secrets.get("gemini", {})
    if isinstance(gemini_block, dict):
        key_candidates.extend(
            [
                gemini_block.get("api_key"),
                gemini_block.get("key"),
            ]
        )

    for candidate in key_candidates:
        if candidate:
            return str(candidate).strip()

    raise RuntimeError("No se encontró GEMINI API key en secrets.")


def call_gemini_flash(prompt: str, temperature: float = 0.2) -> str:
    api_key = get_gemini_api_key()
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.0-flash:generateContent"
    )
    url = f"{endpoint}?{parse.urlencode({'key': api_key})}"

    payload = {
        "system_instruction": {
            "parts": [
                {
                    "text": (
                        "Analiza técnicamente el despiece contra la Wiki CUBRO IA. "
                        "Detecta inconsistencias, riesgos de fabricación/montaje, posibles errores, "
                        "y observaciones relevantes. No inventes información y marca como sospecha "
                        "todo lo que no sea concluyente."
                    )
                }
            ]
        },
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 2048,
        },
    }

    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=90) as response:
            raw_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Error de Gemini ({exc.code}): {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"No se pudo conectar con Gemini: {exc}") from exc

    data = json.loads(raw_body)
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini devolvió una respuesta vacía.")

    parts = candidates[0].get("content", {}).get("parts", [])
    text_parts = [str(part.get("text", "")) for part in parts if part.get("text")]
    final_text = "\n".join(text_parts).strip()

    if not final_text:
        raise RuntimeError("Gemini no devolvió texto utilizable.")

    return final_text


st.title("🤖 Revisión Técnica IA")
st.caption(
    "Selecciona un proyecto (pestaña), revisa su despiece completo y solicita un análisis técnico con Gemini Flash usando la Wiki CUBRO IA."
)

try:
    project_names = list_worksheets(SPREADSHEET_ID)
except Exception as exc:
    st.error("No se pudo cargar la lista de proyectos desde Google Sheets.")
    st.exception(exc)
    st.stop()

if not project_names:
    st.warning("No se encontraron pestañas/proyectos en el spreadsheet configurado.")
    st.stop()

search_text = st.text_input("Buscar proyecto por nombre de pestaña", placeholder="Escribe parte del nombre…")
filtered_projects = [
    name for name in project_names if search_text.lower().strip() in name.lower()
]

if not filtered_projects:
    st.warning("No hay proyectos que coincidan con el buscador.")
    st.stop()

selected_project = st.selectbox("Selecciona un proyecto", options=filtered_projects, index=0)

if not selected_project:
    st.info("Selecciona un proyecto para cargar su despiece.")
    st.stop()

try:
    project_df = load_sheet_as_dataframe(SPREADSHEET_ID, selected_project)
except Exception as exc:
    st.error(f"No se pudo cargar el despiece de '{selected_project}'.")
    st.exception(exc)
    st.stop()

st.subheader("Vista previa del despiece")
if project_df.empty:
    st.warning("La hoja seleccionada no tiene datos utilizables tras limpieza de vacíos.")
else:
    st.dataframe(project_df, use_container_width=True, hide_index=True)
    st.caption(f"Filas: {len(project_df)} | Columnas: {len(project_df.columns)}")

user_prompt = st.text_area(
    "Prompt libre para la revisión",
    placeholder="Añade contexto o preguntas concretas para el análisis técnico (opcional).",
    height=160,
)

analyze_clicked = st.button("Analizar con Gemini", type="primary", use_container_width=True)

if analyze_clicked:
    if not selected_project:
        st.error("Debes seleccionar un proyecto antes de ejecutar el análisis.")
        st.stop()

    if project_df.empty:
        st.error("No hay datos de despiece para analizar en el proyecto seleccionado.")
        st.stop()

    try:
        wiki_text = read_local_wiki(WIKI_PATH)
    except FileNotFoundError:
        st.error(f"No se encontró el archivo de referencia: {WIKI_PATH}")
        st.stop()
    except Exception as exc:
        st.error("No se pudo leer la wiki local de referencia.")
        st.exception(exc)
        st.stop()

    final_prompt = build_gemini_prompt(
        wiki_text=wiki_text,
        project_name=selected_project,
        project_df=project_df,
        user_prompt=user_prompt,
    )

    with st.spinner("Analizando proyecto con Gemini Flash…"):
        try:
            analysis = call_gemini_flash(final_prompt, temperature=0.2)
        except Exception as exc:
            st.error("Falló el análisis con Gemini.")
            st.exception(exc)
            st.stop()

    st.subheader("Respuesta IA")
    st.markdown(analysis)
