from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


def normalize_code(code: str) -> str:
    return str(code).replace("\t", " ").strip().upper()


def parse_codes(text: str) -> list[str]:
    raw_parts = re.split(r"[\n,;]+|\s+", text or "")
    items: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        token = normalize_code(part)
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        items.append(token)
    return items


def _norm_colname(name: str) -> str:
    clean = str(name).strip().lower()
    clean = clean.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    return re.sub(r"[^a-z0-9]+", "", clean)


def detect_code_column(df: pd.DataFrame) -> str:
    priority = ["codigo", "codigo", "code", "referencia", "ref", "id", "cod"]
    norm_map = {_norm_colname(col): col for col in df.columns}
    for candidate in priority:
        if candidate in norm_map:
            return norm_map[candidate]

    best_col = None
    best_score = -1.0
    for col in df.columns:
        series = df[col]
        if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
            continue
        non_na = series.dropna().astype(str).str.strip()
        if non_na.empty:
            continue
        ratio = non_na.nunique() / len(non_na)
        if ratio > best_score:
            best_col = col
            best_score = ratio

    if best_col is None:
        return df.columns[0]
    return best_col


def detect_dim_columns(df: pd.DataFrame) -> dict:
    synonyms = {
        "alto_mm": ["alto", "altura", "h", "height"],
        "ancho_mm": ["ancho", "anchura", "w", "width"],
        "grueso_mm": ["grueso", "espesor", "e", "thickness"],
    }
    norm_map = {_norm_colname(col): col for col in df.columns}
    result = {"alto_mm": None, "ancho_mm": None, "grueso_mm": None, "medidas": None}

    for key, words in synonyms.items():
        for word in words:
            if word in norm_map:
                result[key] = norm_map[word]
                break

    if not all([result["alto_mm"], result["ancho_mm"], result["grueso_mm"]]):
        for col in df.columns:
            norm = _norm_colname(col)
            if norm in {"medidas", "dimension", "dimensiones", "medida", "tamano", "size"}:
                result["medidas"] = col
                break
    return result


def detect_color_columns(df: pd.DataFrame) -> dict:
    color_syn = ["color", "acabado", "finish", "decor", "nombre", "descripcion", "descripción"]
    model_syn = ["modelo", "gama", "collection", "coleccion", "colección", "serie"]
    norm_map = {_norm_colname(col): col for col in df.columns}

    out = {"color": None, "modelo": None}
    for word in color_syn:
        key = _norm_colname(word)
        if key in norm_map:
            out["color"] = norm_map[key]
            break
    for word in model_syn:
        key = _norm_colname(word)
        if key in norm_map:
            out["modelo"] = norm_map[key]
            break
    return out


def load_alvic_db(db_path: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(db_path, sep=None, engine="python")
    except Exception:
        try:
            df = pd.read_csv(db_path, sep=";")
        except Exception:
            df = pd.read_csv(db_path, sep=",")

    df.columns = [str(col).strip().lower() for col in df.columns]
    return df


def _extract_dims_from_text(value: str) -> tuple[str | None, str | None, str | None]:
    if value is None:
        return None, None, None
    text = str(value)
    match = re.search(r"(\d+(?:[\.,]\d+)?)\s*[xX×]\s*(\d+(?:[\.,]\d+)?)\s*[xX×]\s*(\d+(?:[\.,]\d+)?)", text)
    if not match:
        return None, None, None
    return match.group(1).replace(",", "."), match.group(2).replace(",", "."), match.group(3).replace(",", ".")


def _as_clean_text(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text if text else None


def find_code(df: pd.DataFrame, code: str) -> dict | None:
    if df.empty:
        return None

    code_col = detect_code_column(df)
    work = df.copy()
    work["__code_norm"] = work[code_col].map(normalize_code)
    rows = work[work["__code_norm"] == normalize_code(code)]
    if rows.empty:
        return None

    row = rows.iloc[0]
    dim_cols = detect_dim_columns(df)
    color_cols = detect_color_columns(df)

    alto = _as_clean_text(row[dim_cols["alto_mm"]]) if dim_cols["alto_mm"] else None
    ancho = _as_clean_text(row[dim_cols["ancho_mm"]]) if dim_cols["ancho_mm"] else None
    grueso = _as_clean_text(row[dim_cols["grueso_mm"]]) if dim_cols["grueso_mm"] else None

    if (not alto or not ancho or not grueso) and dim_cols["medidas"]:
        ex_alto, ex_ancho, ex_grueso = _extract_dims_from_text(row[dim_cols["medidas"]])
        alto = alto or ex_alto
        ancho = ancho or ex_ancho
        grueso = grueso or ex_grueso

    color = _as_clean_text(row[color_cols["color"]]) if color_cols["color"] else None
    modelo = _as_clean_text(row[color_cols["modelo"]]) if color_cols["modelo"] else None

    return {
        "code": normalize_code(code),
        "alto_mm": alto or "—",
        "ancho_mm": ancho or "—",
        "grueso_mm": grueso or "—",
        "color": color or "—",
        "modelo": modelo,
    }


def format_result(item: dict | None, code: str) -> str:
    code = normalize_code(code)
    if item is None:
        return (
            "### ✅ Código ALVIC\n"
            f"**{code}**\n\n"
            "❌ No encontrado en base_datos_alvic_2026.csv\n"
        )

    lines = [
        "### ✅ Código ALVIC",
        f"**{item.get('code', code)}**",
        "",
        "### 📐 Dimensiones estándar ALVIC",
        f"- **Alto:** {item.get('alto_mm', '—')} mm",
        f"- **Ancho:** {item.get('ancho_mm', '—')} mm",
        f"- **Grueso:** {item.get('grueso_mm', '—')} mm",
        "",
        "### 🎨 Color / Acabado",
        f"- **{item.get('color', '—') or '—'}**",
    ]
    modelo = item.get("modelo")
    if modelo:
        lines.append(f"- **Modelo:** {modelo}")
    return "\n".join(lines) + "\n"
