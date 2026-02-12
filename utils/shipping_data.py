from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from utils.gsheets_io import get_sheets_service

SHIPPING_SHEET_ID = "1J75KO8_EMZ-_15DJfeXmsQDQPStJTD18TOYOHWrXzgA"

COUNTRY_MAP = {
    "ES": "España",
    "PT": "Portugal",
    "FR": "Francia",
    "BE": "Bélgica",
    "NL": "Países Bajos",
    "DE": "Alemania",
    "IT": "Italia",
    "CH": "Suiza",
    "AT": "Austria",
    "GB": "Reino Unido",
    "IE": "Irlanda",
    "DK": "Dinamarca",
    "SE": "Suecia",
    "NO": "Noruega",
    "FI": "Finlandia",
    "PL": "Polonia",
    "CZ": "Chequia",
    "SK": "Eslovaquia",
    "HU": "Hungría",
    "RO": "Rumanía",
    "BG": "Bulgaria",
    "GR": "Grecia",
    "HR": "Croacia",
    "SI": "Eslovenia",
    "RS": "Serbia",
    "BA": "Bosnia y Herzegovina",
    "ME": "Montenegro",
    "MK": "Macedonia del Norte",
    "AL": "Albania",
    "EE": "Estonia",
    "LV": "Letonia",
    "LT": "Lituania",
    "LU": "Luxemburgo",
    "IS": "Islandia",
    "MT": "Malta",
    "CY": "Chipre",
    "TR": "Turquía",
    "UA": "Ucrania",
}

COUNTRY_ALIASES = {
    "SPAIN": "España",
    "ESPANA": "España",
    "ESPAÑA": "España",
    "FRANCE": "Francia",
    "BELGIUM": "Bélgica",
    "NETHERLANDS": "Países Bajos",
    "HOLLAND": "Países Bajos",
    "UK": "Reino Unido",
    "UNITED KINGDOM": "Reino Unido",
}

ID_PREFIXES = ("SP", "EU", "UK", "FR", "PT", "ES", "DE", "IT", "BE", "NL")


def normalize_text(value: str) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).strip().split())
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.lower()


def format_address(text: str) -> str:
    if not text:
        return ""

    cleaned = " ".join(str(text).split()).lower()
    if not cleaned:
        return ""

    chars = list(cleaned)
    for idx, char in enumerate(chars):
        if char.isalpha():
            chars[idx] = char.upper()
            break
    return "".join(chars)


def translate_country(value: str) -> str:
    if not value:
        return ""

    cleaned = " ".join(str(value).strip().split())
    if not cleaned:
        return ""

    if len(cleaned) == 2:
        return COUNTRY_MAP.get(cleaned.upper(), cleaned)

    normalized_upper = normalize_text(cleaned).upper()
    if normalized_upper in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[normalized_upper]

    return cleaned


def _guess_column(df: pd.DataFrame, candidates: tuple[str, ...], fallback_idx: int | None = None) -> str | None:
    normalized_headers = {normalize_text(col): col for col in df.columns}
    for candidate in candidates:
        col = normalized_headers.get(normalize_text(candidate))
        if col:
            return col

    if fallback_idx is not None and 0 <= fallback_idx < len(df.columns):
        return df.columns[fallback_idx]
    return None


@st.cache_data(ttl=300)
def load_shipping_sheet() -> pd.DataFrame:
    service = get_sheets_service()

    metadata = service.spreadsheets().get(spreadsheetId=SHIPPING_SHEET_ID, fields="sheets.properties.title").execute()
    sheets = metadata.get("sheets", [])
    if not sheets:
        return pd.DataFrame()

    first_sheet_name = sheets[0].get("properties", {}).get("title", "")
    if not first_sheet_name:
        return pd.DataFrame()

    values_resp = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=SHIPPING_SHEET_ID,
            range=f"{first_sheet_name}!A:Z",
            valueRenderOption="UNFORMATTED_VALUE",
        )
        .execute()
    )
    values = values_resp.get("values", []) or []
    if not values:
        return pd.DataFrame()

    header = [str(h).strip() for h in values[0]]
    if not any(header):
        header = [f"col_{idx + 1}" for idx in range(len(values[0]))]

    rows: List[List[Any]] = []
    width = len(header)
    for row in values[1:]:
        r = list(row)
        if len(r) < width:
            r += [""] * (width - len(r))
        rows.append(r[:width])

    df = pd.DataFrame(rows, columns=header)
    if df.empty:
        return df

    for col in df.columns:
        df[col] = df[col].fillna("").astype(str)

    id_col = _guess_column(df, ("id cubro", "id", "pedido", "numero", "nº"), fallback_idx=0)
    client_col = _guess_column(df, ("cliente", "customer", "nombre", "name"), fallback_idx=1)
    business_name_col = df.columns[1] if len(df.columns) > 1 else None
    addr_c_col = df.columns[2] if len(df.columns) > 2 else None
    addr_d_col = df.columns[3] if len(df.columns) > 3 else None
    cp_col = df.columns[4] if len(df.columns) > 4 else None
    city_col = df.columns[5] if len(df.columns) > 5 else None
    country_col = _guess_column(df, ("pais", "país", "country"), fallback_idx=6 if len(df.columns) > 6 else None)

    prepared = pd.DataFrame(
        {
            "id": df[id_col] if id_col else "",
            "cliente": df[client_col] if client_col else "",
            "business_name": df[business_name_col] if business_name_col else "",
            "direccion_c": df[addr_c_col] if addr_c_col else "",
            "direccion_d": df[addr_d_col] if addr_d_col else "",
            "cp": df[cp_col] if cp_col else "",
            "poblacion": df[city_col] if city_col else "",
            "pais_raw": df[country_col] if country_col else "",
        }
    )

    prepared = prepared.fillna("").astype(str)
    mask_not_empty = ~prepared.apply(lambda row: normalize_text(" ".join(row.values)) == "", axis=1)
    return prepared.loc[mask_not_empty].reset_index(drop=True)


def _is_id_like(query: str) -> bool:
    cleaned = query.strip().upper()
    return bool(re.match(r"^[A-Z]{2,3}-", cleaned)) or any(cleaned.startswith(f"{prefix}-") for prefix in ID_PREFIXES)


def _score_field(normalized_query: str, normalized_value: str) -> int:
    if not normalized_query or not normalized_value:
        return 0
    if normalized_value == normalized_query:
        return 300
    if normalized_value.startswith(normalized_query):
        return 200
    if normalized_query in normalized_value:
        return 100
    return 0


def search_shipping_data(df: pd.DataFrame, query: str) -> List[Dict[str, str]]:
    normalized_query = normalize_text(query)
    if df.empty or not normalized_query:
        return []

    id_priority = _is_id_like(query)
    ranked_rows: List[tuple[int, int, Dict[str, str]]] = []

    for idx, row in df.iterrows():
        row_dict = {k: str(v) for k, v in row.to_dict().items()}
        id_norm = normalize_text(row_dict.get("id", ""))
        client_norm = normalize_text(row_dict.get("cliente", ""))

        id_score = _score_field(normalized_query, id_norm)
        client_score = _score_field(normalized_query, client_norm)

        if id_priority:
            total_score = id_score * 3 + client_score
        else:
            total_score = client_score * 2 + id_score

        if total_score <= 0:
            continue

        ranked_rows.append((total_score, -idx, row_dict))

    ranked_rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [row for _, _, row in ranked_rows]


def build_display_fields(row: Dict[str, str]) -> Dict[str, str]:
    address_raw = f"{row.get('direccion_c', '').strip()} {row.get('direccion_d', '').strip()}".strip()
    cp_city_raw = f"{row.get('cp', '').strip()} {row.get('poblacion', '').strip()}".strip()

    return {
        "business_name": " ".join(str(row.get("business_name", "")).strip().split()),
        "direccion": format_address(address_raw),
        "cp_poblacion": " ".join(cp_city_raw.split()),
        "pais": translate_country(row.get("pais_raw", "")),
    }
