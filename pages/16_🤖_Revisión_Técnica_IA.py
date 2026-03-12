from __future__ import annotations

import json
import logging
import math
import re
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

ANALYSIS_MODES = {
    "Análisis rápido": {
        "max_wiki_chunks": 4,
        "max_rows_for_llm": 20,
    },
    "Análisis profundo": {
        "max_wiki_chunks": 8,
        "max_rows_for_llm": 45,
    },
}

MAX_CELL_CHARS = 220
MAX_WIKI_CHUNK_CHARS = 2400
MAX_PROMPT_CHARS = 28000
REPRESENTATIVE_ROWS_COUNT = 6
SUSPICIOUS_ROWS_HARD_LIMIT = 60
TOP_KEY_COLUMNS = 8
DIMENSION_KEYWORDS = ("ancho", "alto", "fondo", "largo", "profund", "diam", "espesor", "medida")
MATERIAL_KEYWORDS = ("material", "madera", "tablero", "metal", "acabado", "color", "melamina", "canto")
QUANTITY_KEYWORDS = ("cantidad", "cant", "uds", "unidades", "qty", "cantidad total")
IMPORTANT_FIELD_KEYWORDS = (
    "id",
    "pieza",
    "material",
    "acabado",
    "cantidad",
    "ancho",
    "alto",
    "fondo",
    "largo",
)
DEFAULT_GEMINI_MODEL_PRIMARY = "gemini-2.0-flash"
DEFAULT_GEMINI_MODEL_FALLBACK = ""

logger = logging.getLogger(__name__)

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


def normalize_project_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    normalized = df.copy()
    normalized.columns = _make_unique_columns([str(col).strip() for col in normalized.columns])
    normalized = normalized.applymap(lambda v: str(v).strip() if pd.notna(v) else pd.NA)
    normalized = normalized.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    return normalized


def clean_project_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    cleaned = normalize_project_dataframe(df)
    cleaned = cleaned.dropna(axis=0, how="all").dropna(axis=1, how="all")

    def _truncate_cell(value: Any) -> Any:
        if pd.isna(value):
            return pd.NA
        value_str = str(value)
        if len(value_str) <= MAX_CELL_CHARS:
            return value_str
        return f"{value_str[: MAX_CELL_CHARS - 1]}…"

    cleaned = cleaned.applymap(_truncate_cell)
    return cleaned.reset_index(drop=True)


def _find_columns_by_keywords(df: pd.DataFrame, keywords: tuple[str, ...]) -> list[str]:
    matches = []
    for col in df.columns:
        col_lower = str(col).lower()
        if any(keyword in col_lower for keyword in keywords):
            matches.append(str(col))
    return matches


def extract_key_columns(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return []

    col_scores: dict[str, float] = {}
    n_rows = max(len(df), 1)
    for col in df.columns:
        col_name = str(col)
        ser = df[col]
        non_null_ratio = ser.notna().mean()
        unique_ratio = min(ser.nunique(dropna=True) / n_rows, 1)
        keyword_bonus = 0.3 if any(k in col_name.lower() for k in IMPORTANT_FIELD_KEYWORDS) else 0.0
        col_scores[col_name] = non_null_ratio * 0.6 + unique_ratio * 0.4 + keyword_bonus

    ordered = sorted(col_scores.items(), key=lambda item: item[1], reverse=True)
    return [col for col, _ in ordered[:TOP_KEY_COLUMNS]]


def _coerce_numeric_series(ser: pd.Series) -> pd.Series:
    raw = ser.astype(str).str.replace(",", ".", regex=False)
    extracted = raw.str.extract(r"([-+]?\d+(?:\.\d+)?)", expand=False)
    return pd.to_numeric(extracted, errors="coerce")


def detect_suspicious_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    flagged_indexes: set[int] = set()

    duplicate_mask = df.duplicated(keep=False)
    flagged_indexes.update(df.index[duplicate_mask].tolist())

    key_cols = extract_key_columns(df)
    critical_cols = [
        c for c in key_cols if any(k in c.lower() for k in IMPORTANT_FIELD_KEYWORDS)
    ][:4]
    if critical_cols:
        critical_null = df[critical_cols].isna().any(axis=1)
        flagged_indexes.update(df.index[critical_null].tolist())

    dim_cols = _find_columns_by_keywords(df, DIMENSION_KEYWORDS)
    for col in dim_cols:
        numeric = _coerce_numeric_series(df[col])
        valid = numeric.dropna()
        if len(valid) < 5:
            continue
        q1, q3 = valid.quantile(0.25), valid.quantile(0.75)
        iqr = q3 - q1
        low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        anomaly_mask = (numeric < low) | (numeric > high)
        flagged_indexes.update(df.index[anomaly_mask.fillna(False)].tolist())

    text_len_mask = df.astype(str).apply(lambda row: row.str.len().max() > (MAX_CELL_CHARS * 0.9), axis=1)
    flagged_indexes.update(df.index[text_len_mask].tolist())

    material_cols = _find_columns_by_keywords(df, MATERIAL_KEYWORDS)
    for col in material_cols:
        freq = df[col].value_counts(dropna=True)
        rare_values = set(freq[freq <= 1].index.tolist())
        rare_mask = df[col].isin(rare_values)
        flagged_indexes.update(df.index[rare_mask.fillna(False)].tolist())

    sorted_indexes = sorted(flagged_indexes)[:SUSPICIOUS_ROWS_HARD_LIMIT]
    return df.loc[sorted_indexes].copy() if sorted_indexes else pd.DataFrame(columns=df.columns)


def _sample_representative_rows(df: pd.DataFrame, n_rows: int) -> pd.DataFrame:
    if df.empty:
        return df
    if len(df) <= n_rows:
        return df
    head_n = max(1, n_rows // 2)
    tail_n = max(1, n_rows - head_n)
    return pd.concat([df.head(head_n), df.tail(tail_n)], ignore_index=True).drop_duplicates().head(n_rows)


def build_project_summary(df: pd.DataFrame, project_name: str) -> dict[str, Any]:
    if df.empty:
        return {
            "project_name": project_name,
            "total_useful_rows": 0,
            "columns": [],
            "notes": ["No hay datos útiles para resumir."],
        }

    quantity_cols = _find_columns_by_keywords(df, QUANTITY_KEYWORDS)
    total_pieces = None
    for col in quantity_cols:
        numeric = _coerce_numeric_series(df[col])
        if numeric.notna().sum() > 0:
            total_pieces = float(numeric.fillna(0).sum())
            break

    material_values: set[str] = set()
    for col in _find_columns_by_keywords(df, ("material", "tablero", "metal", "madera")):
        material_values.update(df[col].dropna().astype(str).str.strip().unique().tolist())

    finish_values: set[str] = set()
    for col in _find_columns_by_keywords(df, ("acabado", "color", "canto", "barniz")):
        finish_values.update(df[col].dropna().astype(str).str.strip().unique().tolist())

    dimensions: dict[str, dict[str, float]] = {}
    for col in _find_columns_by_keywords(df, DIMENSION_KEYWORDS):
        numeric = _coerce_numeric_series(df[col]).dropna()
        if numeric.empty:
            continue
        dimensions[col] = {
            "min": round(float(numeric.min()), 2),
            "max": round(float(numeric.max()), 2),
        }

    duplicate_count = int(df.duplicated().sum())
    key_cols = extract_key_columns(df)
    incomplete_rows = int(df[key_cols[: min(4, len(key_cols))]].isna().any(axis=1).sum()) if key_cols else 0

    return {
        "project_name": project_name,
        "total_useful_rows": len(df),
        "total_columns": len(df.columns),
        "total_pieces": total_pieces,
        "columns": [str(col) for col in df.columns],
        "key_columns": key_cols,
        "materials_detected": sorted(v for v in material_values if v)[:25],
        "finishes_detected": sorted(v for v in finish_values if v)[:25],
        "dimensions_detected": dimensions,
        "duplicate_rows": duplicate_count,
        "rows_with_missing_in_important_columns": incomplete_rows,
    }


def read_local_wiki(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo de wiki: {path}")
    return path.read_text(encoding="utf-8")


def chunk_wiki_text(text: str) -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    current_title = "Introducción"
    current_lines: list[str] = []

    for line in text.splitlines():
        if re.match(r"^#{1,3}\s+", line.strip()):
            if current_lines:
                chunks.append({"title": current_title, "content": "\n".join(current_lines).strip()})
            current_title = re.sub(r"^#{1,3}\s+", "", line.strip())
            current_lines = []
            continue
        current_lines.append(line)

    if current_lines:
        chunks.append({"title": current_title, "content": "\n".join(current_lines).strip()})

    cleaned_chunks = []
    for chunk in chunks:
        body = chunk["content"].strip()
        if not body:
            continue
        if len(body) > MAX_WIKI_CHUNK_CHARS:
            body = f"{body[: MAX_WIKI_CHUNK_CHARS - 1]}…"
        cleaned_chunks.append({"title": chunk["title"], "content": body})
    return cleaned_chunks


def _extract_keywords(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]{3,}", text.lower())
    stopwords = {
        "para",
        "este",
        "esta",
        "sobre",
        "desde",
        "donde",
        "entre",
        "como",
        "analiza",
        "proyecto",
        "wiki",
        "cubro",
    }
    return {tok for tok in tokens if tok not in stopwords}


def select_relevant_wiki_chunks(
    user_prompt: str,
    project_summary: dict[str, Any],
    wiki_chunks: list[dict[str, str]],
    max_chunks: int,
) -> list[dict[str, str]]:
    if not wiki_chunks:
        return []

    summary_text = json.dumps(project_summary, ensure_ascii=False)
    keywords = _extract_keywords(user_prompt) | _extract_keywords(summary_text)

    scored: list[tuple[float, dict[str, str]]] = []
    for chunk in wiki_chunks:
        haystack = f"{chunk['title']}\n{chunk['content']}".lower()
        overlap = sum(1 for k in keywords if k in haystack)
        density = overlap / max(len(keywords), 1)
        title_bonus = 0.2 if any(k in chunk["title"].lower() for k in keywords) else 0.0
        score = density + title_bonus
        scored.append((score, chunk))

    ranked = [chunk for score, chunk in sorted(scored, key=lambda item: item[0], reverse=True) if score > 0]
    if not ranked:
        ranked = wiki_chunks[:]

    return ranked[:max_chunks]


def _rows_to_markdown_table(df: pd.DataFrame, max_rows: int) -> str:
    if df.empty:
        return "(sin filas relevantes)"
    subset = df.head(max_rows).copy()
    subset = subset.fillna("-")
    return subset.to_markdown(index=False)


def estimate_prompt_size(prompt: str, wiki_chunks_count: int, rows_count: int, mode: str) -> dict[str, Any]:
    char_count = len(prompt)
    approx_tokens = math.ceil(char_count / 4)
    return {
        "mode": mode,
        "char_count": char_count,
        "approx_tokens": approx_tokens,
        "wiki_chunks": wiki_chunks_count,
        "rows_sent": rows_count,
    }


def build_compact_prompt(
    *,
    project_summary: dict[str, Any],
    suspicious_rows: pd.DataFrame,
    representative_rows: pd.DataFrame,
    selected_wiki_chunks: list[dict[str, str]],
    user_prompt: str,
    mode_label: str,
    max_rows_for_llm: int,
) -> tuple[str, dict[str, Any]]:
    effective_user_prompt = user_prompt.strip() or DEFAULT_USER_PROMPT
    rows_pool = pd.concat([suspicious_rows, representative_rows], ignore_index=True).drop_duplicates()
    rows_pool = rows_pool.head(max_rows_for_llm)

    wiki_chunks = selected_wiki_chunks[:]
    rows_limit = len(rows_pool)

    def _compose_prompt(rows_n: int, wiki_subset: list[dict[str, str]]) -> str:
        wiki_block = "\n\n".join(
            f"### {chunk['title']}\n{chunk['content']}" for chunk in wiki_subset
        )
        summary_json = json.dumps(project_summary, ensure_ascii=False, indent=2)
        rows_block = _rows_to_markdown_table(rows_pool, rows_n)
        return f"""
## Rol
Eres un analista técnico de proyectos CUBRO. Debes revisar el despiece contrastándolo con la Wiki CUBRO IA. No inventes reglas. Basa el análisis solo en la información proporcionada.

## Objetivo
Detecta inconsistencias, riesgos de fabricación o montaje, posibles errores y observaciones relevantes.

## Fragmentos relevantes de Wiki CUBRO IA
{wiki_block if wiki_block else '(sin fragmentos de wiki seleccionados)'}

## Resumen estructurado del proyecto
{summary_json}

## Filas relevantes
{rows_block}

## Prompt del usuario
{effective_user_prompt}
""".strip()

    prompt = _compose_prompt(rows_limit, wiki_chunks)
    while len(prompt) > MAX_PROMPT_CHARS and wiki_chunks:
        wiki_chunks = wiki_chunks[:-1]
        prompt = _compose_prompt(rows_limit, wiki_chunks)

    while len(prompt) > MAX_PROMPT_CHARS and rows_limit > 5:
        rows_limit -= 3
        prompt = _compose_prompt(rows_limit, wiki_chunks)

    if len(prompt) > MAX_PROMPT_CHARS:
        compact_summary = dict(project_summary)
        compact_summary["columns"] = compact_summary.get("columns", [])[:20]
        compact_summary["materials_detected"] = compact_summary.get("materials_detected", [])[:12]
        compact_summary["finishes_detected"] = compact_summary.get("finishes_detected", [])[:12]
        project_summary.clear()
        project_summary.update(compact_summary)
        prompt = _compose_prompt(min(rows_limit, 8), wiki_chunks)

    stats = estimate_prompt_size(prompt, len(wiki_chunks), rows_limit, mode_label)
    return prompt, stats


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

    return clean_project_dataframe(df)


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


def get_gemini_models() -> tuple[str, str]:
    gemini_block = st.secrets.get("gemini", {})
    primary = st.secrets.get("GEMINI_MODEL_PRIMARY")
    fallback = st.secrets.get("GEMINI_MODEL_FALLBACK")

    if isinstance(gemini_block, dict):
        primary = primary or gemini_block.get("model_primary")
        fallback = fallback or gemini_block.get("model_fallback")

    primary_model = str(primary or DEFAULT_GEMINI_MODEL_PRIMARY).strip()
    fallback_model = str(fallback or DEFAULT_GEMINI_MODEL_FALLBACK).strip()
    return primary_model, fallback_model


def extract_retry_delay_seconds(error_payload_or_text: Any) -> int | None:
    if error_payload_or_text is None:
        return None

    payload_text = error_payload_or_text
    if isinstance(error_payload_or_text, (dict, list)):
        payload_text = json.dumps(error_payload_or_text, ensure_ascii=False)
    payload_text = str(payload_text)

    matches = re.findall(r'"retryDelay"\s*:\s*"([0-9]+)s"', payload_text)
    if matches:
        return int(matches[0])

    fallback_match = re.search(r"reintentar[^0-9]*([0-9]+)\s*seg", payload_text, flags=re.IGNORECASE)
    if fallback_match:
        return int(fallback_match.group(1))

    return None


def is_gemini_quota_error(error_payload_or_text: Any, code: int | None = None) -> bool:
    if code == 429:
        return True

    payload_text = error_payload_or_text
    if isinstance(error_payload_or_text, (dict, list)):
        payload_text = json.dumps(error_payload_or_text, ensure_ascii=False)
    normalized = str(payload_text).upper()
    return "RESOURCE_EXHAUSTED" in normalized or "RATE_LIMIT" in normalized or "QUOTA" in normalized


def format_gemini_user_error(*, is_quota_error: bool, retry_delay_seconds: int | None = None) -> tuple[str, str]:
    if is_quota_error:
        base = (
            "No se pudo completar el análisis porque la cuota actual de Gemini no está disponible "
            "para este proyecto o modelo."
        )
        if retry_delay_seconds:
            base += f" Gemini sugiere reintentar en aproximadamente {retry_delay_seconds} segundos."
        recommendation = (
            "Recomendaciones: revisa la API key, valida el proyecto en Google AI Studio, "
            "comprueba billing/tier y confirma el modelo configurado."
        )
        return base, recommendation

    return (
        "No se pudo completar el análisis con Gemini en este momento.",
        "Revisa configuración de API key/modelo y vuelve a intentarlo en unos minutos.",
    )


class GeminiAPIError(RuntimeError):
    def __init__(self, message: str, *, code: int | None, detail: str, model: str, retry_delay_seconds: int | None = None):
        super().__init__(message)
        self.code = code
        self.detail = detail
        self.model = model
        self.retry_delay_seconds = retry_delay_seconds


class GeminiQuotaError(GeminiAPIError):
    pass


def _call_gemini_model(prompt: str, *, api_key: str, model_name: str, temperature: float) -> str:
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_name}:generateContent"
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
        retry_delay_seconds = extract_retry_delay_seconds(detail)
        logger.warning(
            "Gemini HTTPError | model=%s | code=%s | retry_delay=%s",
            model_name,
            exc.code,
            retry_delay_seconds,
        )
        if is_gemini_quota_error(detail, exc.code):
            raise GeminiQuotaError(
                "Gemini respondió con límite de cuota/rate.",
                code=exc.code,
                detail=detail,
                model=model_name,
                retry_delay_seconds=retry_delay_seconds,
            ) from exc
        raise GeminiAPIError(
            f"Error de Gemini ({exc.code}).",
            code=exc.code,
            detail=detail,
            model=model_name,
            retry_delay_seconds=retry_delay_seconds,
        ) from exc
    except Exception as exc:
        logger.exception("Error de conexión con Gemini | model=%s", model_name)
        raise GeminiAPIError(
            f"No se pudo conectar con Gemini: {exc}",
            code=None,
            detail=str(exc),
            model=model_name,
        ) from exc

    data = json.loads(raw_body)
    candidates = data.get("candidates", [])
    if not candidates:
        raise GeminiAPIError(
            "Gemini devolvió una respuesta vacía.",
            code=None,
            detail=raw_body,
            model=model_name,
        )

    parts = candidates[0].get("content", {}).get("parts", [])
    text_parts = [str(part.get("text", "")) for part in parts if part.get("text")]
    final_text = "\n".join(text_parts).strip()

    if not final_text:
        raise GeminiAPIError(
            "Gemini no devolvió texto utilizable.",
            code=None,
            detail=raw_body,
            model=model_name,
        )

    return final_text


def call_gemini_flash(prompt: str, temperature: float = 0.2) -> str:
    api_key = get_gemini_api_key()
    primary_model, fallback_model = get_gemini_models()
    prompt_chars = len(prompt)
    logger.info("Gemini call start | model=%s | prompt_chars=%s", primary_model, prompt_chars)

    try:
        return _call_gemini_model(prompt, api_key=api_key, model_name=primary_model, temperature=temperature)
    except GeminiQuotaError as primary_exc:
        logger.warning(
            "Gemini quota error | model=%s | code=%s | retry_delay=%s",
            primary_exc.model,
            primary_exc.code,
            primary_exc.retry_delay_seconds,
        )
        if fallback_model and fallback_model != primary_model:
            logger.info("Gemini fallback enabled | fallback_model=%s", fallback_model)
            try:
                return _call_gemini_model(prompt, api_key=api_key, model_name=fallback_model, temperature=temperature)
            except GeminiAPIError as fallback_exc:
                logger.warning(
                    "Gemini fallback failed | fallback_model=%s | code=%s | retry_delay=%s",
                    fallback_exc.model,
                    fallback_exc.code,
                    fallback_exc.retry_delay_seconds,
                )
                raise fallback_exc
        raise primary_exc


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
analysis_mode = st.radio("Modo de análisis", options=list(ANALYSIS_MODES.keys()), horizontal=True)
mode_cfg = ANALYSIS_MODES[analysis_mode]

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
show_prompt_metrics = st.checkbox("Mostrar métricas del contexto enviado", value=True)

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

    project_summary = build_project_summary(project_df, selected_project)
    suspicious_rows = detect_suspicious_rows(project_df)
    representative_rows = _sample_representative_rows(project_df, REPRESENTATIVE_ROWS_COUNT)
    wiki_chunks = chunk_wiki_text(wiki_text)
    selected_wiki_chunks = select_relevant_wiki_chunks(
        user_prompt=user_prompt or DEFAULT_USER_PROMPT,
        project_summary=project_summary,
        wiki_chunks=wiki_chunks,
        max_chunks=mode_cfg["max_wiki_chunks"],
    )

    final_prompt, prompt_stats = build_compact_prompt(
        project_summary=project_summary,
        suspicious_rows=suspicious_rows,
        representative_rows=representative_rows,
        selected_wiki_chunks=selected_wiki_chunks,
        user_prompt=user_prompt,
        mode_label=analysis_mode,
        max_rows_for_llm=mode_cfg["max_rows_for_llm"],
    )

    if show_prompt_metrics:
        st.info(
            " | ".join(
                [
                    f"Modo: {prompt_stats['mode']}",
                    f"Chars prompt: {prompt_stats['char_count']}",
                    f"Tokens aprox: {prompt_stats['approx_tokens']}",
                    f"Bloques wiki: {prompt_stats['wiki_chunks']}",
                    f"Filas enviadas: {prompt_stats['rows_sent']}",
                ]
            )
        )

    with st.spinner("Analizando proyecto con Gemini Flash…"):
        try:
            analysis = call_gemini_flash(final_prompt, temperature=0.2)
        except GeminiQuotaError as exc:
            user_message, recommendation = format_gemini_user_error(
                is_quota_error=True,
                retry_delay_seconds=exc.retry_delay_seconds,
            )
            st.error(user_message)
            st.info(recommendation)
            with st.expander("Detalles técnicos"):
                st.code(
                    json.dumps(
                        {
                            "error_type": exc.__class__.__name__,
                            "model": exc.model,
                            "error_code": exc.code,
                            "retry_delay_seconds": exc.retry_delay_seconds,
                            "detail": exc.detail,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            st.stop()
        except GeminiAPIError as exc:
            user_message, recommendation = format_gemini_user_error(is_quota_error=False)
            st.error(user_message)
            st.info(recommendation)
            with st.expander("Detalles técnicos"):
                st.code(
                    json.dumps(
                        {
                            "error_type": exc.__class__.__name__,
                            "model": exc.model,
                            "error_code": exc.code,
                            "detail": exc.detail,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            st.stop()

    st.subheader("Respuesta IA")
    st.markdown(analysis)
