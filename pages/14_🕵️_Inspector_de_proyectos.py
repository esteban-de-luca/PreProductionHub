from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from datetime import datetime
from collections import Counter
from typing import Any

import gspread
import numpy as np
import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

from ui_theme import apply_shared_sidebar

st.set_page_config(page_title="Inspector de proyectos", layout="wide")
apply_shared_sidebar("pages/14_🕵️_Inspector_de_proyectos.py")

MUEBLES_HEADERS = [
    "cache_id",
    "project_id",
    "project_name",
    "source_filename",
    "import_timestamp",
    "mueble_id",
    "n_frentes",
    "n_puertas",
    "n_cajones",
    "alto_total_mm",
    "alto_max_mm",
    "has_handle_data",
    "has_handle_pos1_2",
    "has_handle_pos3",
    "has_handle_pos4",
    "has_handle_pos5",
    "has_any_door_without_handle",
    "drawer_heights_mm",
    "categoria",
    "confidence",
    "rule_id",
    "razon",
    "rules_version",
    "data_hash",
    "notes",
    "ancho_mueble_mm",
    "ancho_mueble_cm",
    "alto_mueble_mm",
    "alto_mueble_cm",
    "alto_total_cm",
    "extraible_altura_mm",
    "extraible_codigo",
    "tipologia_split",
    "split_status",
    "split_notes",
    "inference_source",
]

PIEZAS_HEADERS = [
    "cache_row_id",
    "project_id",
    "source_filename",
    "import_timestamp",
    "mueble_id",
    "piece_id",
    "tipologia",
    "alto_mm",
    "ancho_mm",
    "handle_pos",
    "handle_present",
    "observaciones",
    "is_door",
    "is_drawer",
    "normalized_tipologia",
    "row_number_in_source",
    "rules_version",
    "pieza_role",
    "is_structural",
    "is_drawer_part",
    "inferred_width_mm",
    "inferred_height_mm",
    "detected_drawer_height_mm",
    "inference_source",
]



CANONICAL_COLUMNS_MUEBLES = [
    "cache_id",
    "project_id",
    "project_name",
    "source_filename",
    "import_timestamp",
    "mueble_id",
    "n_frentes",
    "n_puertas",
    "n_cajones",
    "alto_total_mm",
    "alto_max_mm",
    "drawer_heights_mm",
    "has_handle_data",
    "has_handle_pos1_2",
    "has_handle_pos3",
    "has_handle_pos4",
    "has_handle_pos5",
    "has_any_door_without_handle",
    "categoria",
    "confidence",
    "rule_id",
    "razon",
    "rules_version",
    "data_hash",
    "notes",
]

CANONICAL_COLUMNS_UNK = [
    "project_id",
    "mueble_id",
    "n_frentes",
    "n_puertas",
    "n_cajones",
    "alto_total_mm",
    "alto_max_mm",
    "drawer_heights_mm",
    "has_any_door_without_handle",
    "has_handle_data",
    "has_handle_pos1_2",
    "has_handle_pos3",
    "has_handle_pos4",
    "has_handle_pos5",
    "categoria",
    "confidence",
    "rule_id",
    "razon",
    "rules_version",
    "data_hash",
]


DISPLAY_COLUMNS_MUEBLES = [
    "project_name",
    "mueble_id",
    "n_frentes",
    "n_puertas",
    "n_cajones",
    "alto_total_mm",
    "categoria",
    "rule_id",
    "razon",
]

CANONICAL_COLUMNS_PIEZAS_DETAIL = [
    "mueble_id",
    "piece_id",
    "tipologia",
    "normalized_tipologia",
    "alto_mm",
    "ancho_mm",
    "handle_present",
    "handle_pos",
    "observaciones",
    "row_number_in_source",
]

MUEBLES_BOOL_COLUMNS = {
    "has_handle_data",
    "has_handle_pos1_2",
    "has_handle_pos3",
    "has_handle_pos4",
    "has_handle_pos5",
    "has_any_door_without_handle",
}

MUEBLES_NUM_COLUMNS = {
    "n_frentes",
    "n_puertas",
    "n_cajones",
    "alto_total_mm",
    "alto_max_mm",
    "confidence",
}


def _default_for_mueble_column(col: str):
    if col in MUEBLES_BOOL_COLUMNS:
        return False
    if col in MUEBLES_NUM_COLUMNS:
        return pd.NA
    return ""


def ensure_muebles_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = _default_for_mueble_column(col)
    return out


def normalize_required_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "categoria" not in out.columns:
        out["categoria"] = ""
    out["categoria"] = out["categoria"].astype(str).fillna("")

    if "confidence" not in out.columns:
        out["confidence"] = np.nan
    if "rule_id" not in out.columns:
        out["rule_id"] = ""
    if "razon" not in out.columns:
        out["razon"] = ""

    return out


def safe_select_columns(
    df: pd.DataFrame,
    canonical_cols: list[str],
    defaults_by_type: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    out = df.copy()
    cols_present = [c for c in canonical_cols if c in out.columns]
    cols_missing = [c for c in canonical_cols if c not in out.columns]

    defaults = {"bool": False, "num": np.nan, "str": ""}
    if defaults_by_type:
        defaults.update(defaults_by_type)

    for col in cols_missing:
        if col.startswith(("has_", "is_")):
            out[col] = defaults["bool"]
        elif col.startswith("n_") or col.endswith("_mm") or col == "confidence":
            out[col] = defaults["num"]
        else:
            out[col] = defaults["str"]

    cols_present = [c for c in canonical_cols if c in out.columns]
    return out[cols_present].copy(), cols_present, cols_missing
COLUMN_SYNONYMS = {
    "piece_id": ["id pieza", "pieza", "piece id", "id_pieza", "id", "id pieza cubro", "piece_id"],
    "tipologia": ["tipologia", "tipología", "tipo", "d", "tipologia pieza"],
    "tipo_pieza": ["tipo pieza", "tipo_pieza", "rol pieza", "familia pieza"],
    "alto_mm": ["alto", "altura", "h", "alto mm", "altura mm", "dim_y_mm"],
    "ancho_mm": ["ancho", "w", "width", "ancho mm", "anchura", "dim_x_mm"],
    "handle_pos": ["posicion tir", "posicion tirador", "pos tir", "posicion", "posiciontir", "tirador"],
    "observaciones": ["observaciones", "obs", "notas", "j"],
    "project_id": ["id proyecto", "proyecto", "project id"],
}


def _norm_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def normalize_colname(col: str) -> str:
    text = _norm_text(col).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def find_column_by_synonyms(df: pd.DataFrame, logical_name: str) -> str | None:
    normalized_headers = {normalize_colname(str(col)): col for col in df.columns}
    for candidate in COLUMN_SYNONYMS[logical_name]:
        col = normalized_headers.get(normalize_colname(candidate))
        if col is not None:
            return col
    return None


def _parse_number(value: Any) -> float | None:
    if pd.isna(value):
        return None
    text = _norm_text(value).replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_nullable_int(series: pd.Series) -> pd.Series:
    clean = series.astype(str).str.replace(",", ".", regex=False).str.extract(r"(-?\d+(?:\.\d+)?)", expand=False)
    return pd.to_numeric(clean, errors="coerce").round().astype("Int64")


def _mode_int(values: list[int]) -> int | None:
    if not values:
        return None
    counter = Counter(values)
    max_count = max(counter.values())
    top = sorted(v for v, cnt in counter.items() if cnt == max_count)
    return top[0] if top else None


def _is_close_to(value: int, target: int, tolerance: int = 5) -> bool:
    return abs(value - target) <= tolerance


def _normalize_piece_role(row: pd.Series) -> str:
    raw = " ".join(
        [
            _norm_text(row.get("tipo_pieza", "")),
            _norm_text(row.get("tipologia", "")),
            _norm_text(row.get("piece_id", "")),
            _norm_text(row.get("observaciones", "")),
        ]
    ).upper().replace(" ", "")

    if "LAT" in raw:
        return "LAT"
    if "TAP" in raw:
        return "TAP"
    if "BAS" in raw:
        return "BAS"
    if "BLD" in raw or "BALD" in raw:
        return "BLD"
    if any(token in raw for token in ["CAJ", "DRAWER", "EXTR", "CUBO", "METAL"]):
        return "CAJON"
    return "UNKNOWN"


def _assign_missing_mueble_ids(df: pd.DataFrame, project_id: str) -> pd.DataFrame:
    out = df.copy()
    missing_mask = out["mueble_id"].isna() | out["mueble_id"].astype(str).str.strip().eq("")
    if not missing_mask.any():
        return out

    work = out.loc[missing_mask].copy()
    width = pd.concat([work["dim_x_mm"], work["dim_y_mm"]], axis=1).max(axis=1).fillna(0).astype(float)
    height = pd.concat([work["dim_x_mm"], work["dim_y_mm"]], axis=1).min(axis=1).fillna(0).astype(float)
    keys = list(zip((width / 5).round().astype(int), (height / 5).round().astype(int)))
    key_order = {k: i + 1 for i, k in enumerate(sorted(set(keys), key=lambda item: (-item[0], -item[1])))}
    out.loc[missing_mask, "mueble_id"] = [
        f"{project_id}__UNK__M{key_order[k]:02d}" for k in keys
    ]
    return out


def load_and_normalize_csv(file, debug_mode: bool = False) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    raw = file.getvalue()
    parsers = [
        lambda b: pd.read_csv(io.BytesIO(b), sep=None, engine="python"),
        lambda b: pd.read_csv(io.BytesIO(b), sep=";"),
        lambda b: pd.read_csv(io.BytesIO(b), sep=","),
    ]

    last_exc = None
    df = None
    for parser in parsers:
        try:
            df = parser(raw)
            if df is not None and not df.empty:
                break
        except Exception as exc:
            last_exc = exc

    if df is None or df.empty:
        raise ValueError("No se pudo leer el CSV o está vacío.") from last_exc

    normalized_headers = [normalize_colname(str(col)) for col in df.columns]
    found_mapping: dict[str, str] = {}
    for logical_name in ["piece_id", "tipologia", "tipo_pieza", "alto_mm", "ancho_mm", "handle_pos", "observaciones", "project_id"]:
        mapped = find_column_by_synonyms(df, logical_name)
        if mapped is not None:
            found_mapping[logical_name] = mapped

    rename_map = {source_col: target_col for target_col, source_col in found_mapping.items()}
    df = df.rename(columns=rename_map).copy()

    required_cols = ["piece_id", "tipologia"]
    missing_required = [col for col in required_cols if col not in df.columns]
    if missing_required:
        raise ValueError(
            "Faltan columnas mínimas requeridas tras mapear: "
            f"{', '.join(missing_required)}. "
            f"Headers encontrados: {', '.join(normalized_headers)}. "
            "Revisa que existan columnas equivalentes a ID Pieza / Tipología / Alto (mm)."
        )

    normalized = pd.DataFrame()
    normalized["piece_id"] = df["piece_id"].map(_norm_text)
    normalized["tipologia"] = df["tipologia"].map(_norm_text).str.upper().str.strip()
    normalized["alto_mm"] = _to_nullable_int(df["alto_mm"]) if "alto_mm" in df.columns else pd.Series(pd.array([pd.NA] * len(df), dtype="Int64"))
    normalized["ancho_mm"] = _to_nullable_int(df["ancho_mm"]) if "ancho_mm" in df.columns else pd.Series(pd.array([pd.NA] * len(df), dtype="Int64"))
    normalized["dim_x_mm"] = normalized["ancho_mm"]
    normalized["dim_y_mm"] = normalized["alto_mm"]
    normalized["tipo_pieza"] = df["tipo_pieza"].map(_norm_text).str.upper().str.strip() if "tipo_pieza" in df.columns else normalized["tipologia"]
    normalized["handle_pos_raw"] = df["handle_pos"].map(_norm_text) if "handle_pos" in df.columns else ""
    normalized["observaciones"] = df["observaciones"].map(_norm_text) if "observaciones" in df.columns else ""
    normalized["project_id"] = df["project_id"].map(_norm_text) if "project_id" in df.columns else ""
    normalized["row_number_in_source"] = pd.RangeIndex(start=2, stop=len(df) + 2, step=1)

    normalized = normalized[normalized["piece_id"] != ""].copy()
    normalized["mueble_id"] = normalized["piece_id"].str.extract(r"^(M\d+)", expand=False)

    tip = normalized["tipologia"].str.upper().str.strip()
    normalized["normalized_tipologia"] = tip.where(tip.isin(["P", "C", "PQ1", "PQ2"]), "IGNORED")
    normalized.loc[normalized["normalized_tipologia"].isin(["PQ1", "PQ2"]), "normalized_tipologia"] = "P"

    def parse_handle_pos(value: str) -> int | None:
        if value is None:
            return None
        text = _norm_text(value)
        if not text:
            return None
        match = re.search(r"(\d+)", text)
        if not match:
            return None
        pos = int(match.group(1))
        return pos if pos in {1, 2, 3, 4, 5} else None

    normalized["handle_pos"] = normalized["handle_pos_raw"].map(parse_handle_pos)
    normalized["handle_present"] = normalized["handle_pos"].notna()

    if debug_mode:
        debug_mapping = {key: f"{value} -> {key}" for key, value in found_mapping.items()}
    else:
        debug_mapping = found_mapping
    return normalized, debug_mapping, normalized_headers


def build_pieces_cache_rows(
    df: pd.DataFrame,
    project_id: str,
    source_filename: str,
    import_timestamp: str,
    rules_version: str,
) -> pd.DataFrame:
    rows = df.copy()
    rows = _assign_missing_mueble_ids(rows, project_id)

    rows["pieza_role"] = rows.apply(_normalize_piece_role, axis=1)
    rows["is_structural"] = rows["pieza_role"].isin({"LAT", "TAP", "BAS", "BLD"})
    rows["is_drawer_part"] = rows["pieza_role"].eq("CAJON")

    rows["inferred_width_mm"] = pd.Series(pd.array([pd.NA] * len(rows), dtype="Int64"))
    rows["inferred_height_mm"] = pd.Series(pd.array([pd.NA] * len(rows), dtype="Int64"))
    rows["detected_drawer_height_mm"] = pd.Series(pd.array([pd.NA] * len(rows), dtype="Int64"))
    rows["inference_source"] = ""

    rows["cache_row_id"] = rows.apply(
        lambda r: hashlib.sha1(
            "|".join(
                [
                    project_id,
                    source_filename,
                    str(r["mueble_id"]),
                    str(r["piece_id"]),
                    str(int(r["row_number_in_source"])),
                    rules_version,
                ]
            ).encode("utf-8")
        ).hexdigest(),
        axis=1,
    )
    rows["project_id"] = project_id
    rows["source_filename"] = source_filename
    rows["import_timestamp"] = import_timestamp
    rows["is_door"] = rows["normalized_tipologia"].eq("P")
    rows["is_drawer"] = rows["normalized_tipologia"].eq("C")
    rows["rules_version"] = rules_version

    for col in PIEZAS_HEADERS:
        if col not in rows.columns:
            rows[col] = ""

    return rows[PIEZAS_HEADERS].copy()


def aggregate_by_mueble(df_piezas_cache: pd.DataFrame) -> pd.DataFrame:
    def _drawer_heights(group: pd.DataFrame) -> str:
        vals = group.loc[group["is_drawer"], "alto_mm"].dropna().astype(float)
        ints = sorted({int(round(v)) for v in vals})
        return "|".join(str(v) for v in ints)

    def _drawer_widths(group: pd.DataFrame) -> str:
        vals = pd.to_numeric(group.loc[group["is_drawer"], "ancho_mm"], errors="coerce").dropna().astype(float)
        ints = sorted({int(round(v)) for v in vals})
        return "|".join(str(v) for v in ints)

    def _door_heights(group: pd.DataFrame) -> str:
        vals = group.loc[group["is_door"], "alto_mm"].dropna().astype(float)
        ints = sorted(int(round(v)) for v in vals)
        return "|".join(str(v) for v in ints)

    def _door_heights_without_handle(group: pd.DataFrame) -> str:
        vals = group.loc[(group["is_door"]) & (~group["handle_present"].fillna(False)), "alto_mm"].dropna().astype(float)
        ints = sorted(int(round(v)) for v in vals)
        return "|".join(str(v) for v in ints)

    agg = (
        df_piezas_cache.groupby("mueble_id", dropna=False)
        .apply(
            lambda g: pd.Series(
                {
                    "n_frentes": int(len(g)),
                    "n_puertas": int(g["is_door"].sum()),
                    "n_cajones": int(g["is_drawer"].sum()),
                    "alto_total_mm": float(pd.to_numeric(g["alto_mm"], errors="coerce").fillna(0).sum()),
                    "alto_max_mm": float(pd.to_numeric(g["alto_mm"], errors="coerce").fillna(0).max()),
                    "has_handle_data": bool(g["handle_present"].fillna(False).any()),
                    "has_handle_pos1_2": bool(g["handle_pos"].isin([1, 2]).any()),
                    "has_handle_pos3": bool(g["handle_pos"].eq(3).any()),
                    "has_handle_pos4": bool(g["handle_pos"].eq(4).any()),
                    "has_handle_pos5": bool(g["handle_pos"].eq(5).any()),
                    "has_any_door_without_handle": bool(((g["is_door"]) & (~g["handle_present"].fillna(False))).any()),
                    "n_doors_without_handle": int(((g["is_door"]) & (~g["handle_present"].fillna(False))).sum()),
                    "n_doors_with_handle": int(((g["is_door"]) & (g["handle_present"].fillna(False))).sum()),
                    "has_mixed_handle_doors": bool(
                        ((g["is_door"]) & (~g["handle_present"].fillna(False))).any()
                        and ((g["is_door"]) & (g["handle_present"].fillna(False))).any()
                    ),
                    "door_heights_mm": _door_heights(g),
                    "door_no_handle_heights_mm": _door_heights_without_handle(g),
                    "drawer_heights_mm": _drawer_heights(g),
                    "drawer_widths_mm": _drawer_widths(g),
                    "has_pq1": bool(g["tipologia"].astype(str).str.upper().eq("PQ1").any()),
                    "door_has_798_no_handle": bool(
                        (
                            g["is_door"]
                            & (~g["handle_present"].fillna(False))
                            & (pd.to_numeric(g["alto_mm"], errors="coerce").round().eq(798))
                        ).any()
                    ),
                }
            )
        )
        .reset_index()
    )
    return agg


def classify_mueble(row_features: pd.Series) -> tuple[str, float, str, str]:
    n_puertas = int(row_features["n_puertas"])
    n_cajones = int(row_features["n_cajones"])
    door_heights = [
        int(h.strip())
        for h in str(row_features.get("door_heights_mm", "")).split("|")
        if h.strip().isdigit()
    ]
    door_no_handle_heights = [
        int(h.strip())
        for h in str(row_features.get("door_no_handle_heights_mm", "")).split("|")
        if h.strip().isdigit()
    ]
    drawer_heights = {
        int(h.strip())
        for h in str(row_features.get("drawer_heights_mm", "")).split("|")
        if h.strip().isdigit()
    }
    drawer_widths = {
        int(h.strip())
        for h in str(row_features.get("drawer_widths_mm", "")).split("|")
        if h.strip().isdigit()
    }
    door_heights_set = set(door_heights)

    if n_puertas == 2 and n_cajones == 0 and door_heights_set in ({798, 1198}, {798, 1398}, {798, 1598}):
        base = (
            "MA-N",
            0.95,
            "RULE_MAN_FRIDGE_798_X",
            "2 puertas 798 + (1198/1398/1598) sin cajones",
        )
    elif n_cajones >= 1 and 596 in drawer_widths:
        base = ("LVV-60", 0.95, "RULE_LVV60_DRAWER_WIDTH_596", "Cajón ancho 596 => LVV-60")
    elif n_cajones >= 1 and 446 in drawer_widths:
        base = ("LVV-45", 0.95, "RULE_LVV45_DRAWER_WIDTH_446", "Cajón ancho 446 => LVV-45")
    elif bool(row_features.get("has_pq1", False)):
        base = ("MB-Q", 0.95, "RULE_MBQ_HAS_PQ1", "Contiene PQ1 => MB-Q")
    elif n_puertas == 2 and bool(row_features.get("has_mixed_handle_doors", False)):
        base = (
            "MB-FE",
            0.90,
            "RULE_MBFE_TWO_DOORS_ONE_HANDLE",
            "2 puertas: una con tirador y otra sin tirador",
        )
    elif n_puertas == 0 and n_cajones >= 1 and ({148, 298} & drawer_heights):
        base = ("MB-H", 0.95, "RULE_MBH_DRAWER_148_298", "Sin puertas y cajón 148/298")
    elif n_cajones >= 1 and ({298, 198} & drawer_widths):
        base = ("MB-E", 0.90, "RULE_MBE_DRAWER_WIDTH_298_198", "Cajón ancho 298/198 => MB-E")
    elif n_puertas >= 1 and bool(row_features.get("door_has_798_no_handle", False)):
        base = ("MB", 0.90, "RULE_MB_DOOR_798_NO_HANDLE", "Puerta 798 sin tirador => MB")
    else:
        allowed_mpr_heights = {419, 429, 439, 449, 619, 629, 639, 649, 819, 829, 839, 849}
        if n_puertas in {1, 2} and bool(row_features.get("has_any_door_without_handle", False)):
            if door_no_handle_heights and all(h in allowed_mpr_heights for h in door_no_handle_heights):
                base = (
                    "MP-R",
                    0.95,
                    "RULE_MPR_NO_HANDLE_ALLOWED_HEIGHTS",
                    "Puerta(s) sin tirador con altura válida recrecida",
                )
            else:
                base = None
        else:
            base = None

        if base is None:
            alto_total = float(row_features.get("alto_total_mm", 0) or 0)
            if n_puertas >= 1 and n_cajones >= 1 and alto_total > 800:
                base = (
                    "MA-H",
                    0.90,
                    "RULE_MAH_DOORS_DRAWERS_TOTAL_GT_800",
                    "Puertas + cajones y suma frentes > 800",
                )
            elif bool(row_features.get("has_handle_data", False)):
                if n_puertas >= 2 and bool(row_features.get("has_handle_pos4", False)):
                    base = ("MA", 0.90, "RULE_HANDLE_POS4_MULTI_DOOR", "2+ puertas con tirador posición 4")
                elif n_puertas == 1 and bool(row_features.get("has_handle_pos4", False)):
                    base = ("MP", 0.90, "RULE_HANDLE_POS4_SINGLE_DOOR", "1 puerta con tirador posición 4")
                elif n_puertas in {1, 2} and bool(row_features.get("has_handle_pos1_2", False)):
                    base = ("MB", 0.90, "RULE_HANDLE_POS1_2", "Tirador en posición superior")
                elif n_puertas == 1 and bool(row_features.get("has_handle_pos3", False)):
                    base = ("MA", 0.90, "RULE_HANDLE_POS3", "1 puerta con tirador lateral centro")
                elif n_puertas == 1 and bool(row_features.get("has_handle_pos5", False)):
                    base = ("MP", 0.90, "RULE_HANDLE_POS5", "1 puerta con tirador inferior centro")
                else:
                    base = None
            else:
                base = None

            if base is None:
                if alto_total > 800:
                    base = ("MA", 0.75, "RULE_FALLBACK_HEIGHT_GT_800", "Alto total de frentes > 800 mm")
                elif alto_total <= 800 and n_cajones > 0:
                    base = ("MB", 0.75, "RULE_FALLBACK_HEIGHT_LE_800_WITH_DRAWER", "Alto <= 800 mm y con cajones")
                elif alto_total <= 800 and n_cajones == 0:
                    if n_puertas in {1, 2} and bool(row_features.get("has_any_door_without_handle", False)):
                        base = (
                            "UNK",
                            0.40,
                            "RULE_UNK_NO_HANDLE_HEIGHT_OUTSIDE_MPR_SET",
                            "Puerta sin tirador con altura fuera del set recrecido",
                        )
                    else:
                        base = (
                            "UNK",
                            0.40,
                            "RULE_UNK_HEIGHT_LE_800_NO_DRAWER",
                            "Alto <= 800 mm, sin cajones y sin señales suficientes",
                        )
                else:
                    base = ("UNK", 0.40, "RULE_UNK", "No se pudo inferir categoría")

    categoria, confidence, rule_id, razon = base

    if categoria == "MP" and 398 in door_heights_set:
        return ("MP-A", 0.95, "RULE_MPA_MP_DOOR_HEIGHT_398", "MP con puerta 398 => MP-A")

    if categoria == "MB" and n_puertas == 0 and n_cajones > 0:
        return ("MB-C", 0.85, "RULE_MBC_MB_ONLY_DRAWERS", "MB con solo cajones => MB-C")

    if categoria == "MB" and n_cajones == 0 and n_puertas > 0:
        return ("MB-B", 0.85, "RULE_MBB_MB_ONLY_DOORS", "MB con solo puertas => MB-B")

    return categoria, confidence, rule_id, razon


def build_muebles_cache_rows(
    df_features: pd.DataFrame,
    project_id: str,
    project_name: str,
    source_filename: str,
    import_timestamp: str,
    rules_version: str,
) -> pd.DataFrame:
    out = ensure_muebles_columns(df_features, MUEBLES_HEADERS)
    out[["categoria", "confidence", "rule_id", "razon"]] = out.apply(
        lambda r: pd.Series(classify_mueble(r)), axis=1
    )
    out["project_id"] = project_id
    out["project_name"] = project_name
    out["source_filename"] = source_filename
    out["import_timestamp"] = import_timestamp
    out["rules_version"] = rules_version
    out["notes"] = ""

    out["cache_id"] = out.apply(
        lambda r: hashlib.sha1(
            "|".join([project_id, source_filename, str(r["mueble_id"]), rules_version]).encode("utf-8")
        ).hexdigest(),
        axis=1,
    )

    out["data_hash"] = out.apply(
        lambda r: hashlib.sha1(
            "|".join(
                [
                    project_id,
                    str(r["mueble_id"]),
                    str(r["n_frentes"]),
                    str(r["n_puertas"]),
                    str(r["n_cajones"]),
                    str(r["alto_total_mm"]),
                    str(r["categoria"]),
                    str(r["rule_id"]),
                    rules_version,
                ]
            ).encode("utf-8")
        ).hexdigest(),
        axis=1,
    )

    out = ensure_muebles_columns(out, MUEBLES_HEADERS)
    return out[MUEBLES_HEADERS].copy()




def enrich_caches_for_splits(df_muebles: pd.DataFrame, df_piezas: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    muebles = df_muebles.copy()
    piezas = df_piezas.copy()

    piezas["dim_x_mm"] = _to_nullable_int(piezas.get("ancho_mm", pd.Series(dtype=object)))
    piezas["dim_y_mm"] = _to_nullable_int(piezas.get("alto_mm", pd.Series(dtype=object)))
    piezas["tipologia"] = piezas["tipologia"].astype(str).str.upper().str.strip()

    for mueble_id, group in piezas.groupby("mueble_id", dropna=False):
        idx = group.index
        structural = group[group["is_structural"].fillna(False)]

        width_candidates = []
        preferred = structural[structural["pieza_role"].isin(["TAP", "BAS", "BLD"])]
        for _, row in preferred.iterrows():
            dims = [v for v in [row.get("dim_x_mm"), row.get("dim_y_mm")] if pd.notna(v)]
            if dims:
                width_candidates.append(int(max(dims)))
        if not width_candidates:
            for _, row in structural.iterrows():
                dims = [v for v in [row.get("dim_x_mm"), row.get("dim_y_mm")] if pd.notna(v)]
                if not dims:
                    continue
                cand = int(max(dims))
                if cand not in {720, 800, 880, 2000, 2200}:
                    width_candidates.append(cand)
        width_mm = _mode_int(width_candidates)

        height_candidates = []
        lat = structural[structural["pieza_role"].eq("LAT")]
        source_for_height = lat if not lat.empty else structural
        for _, row in source_for_height.iterrows():
            dims = [v for v in [row.get("dim_x_mm"), row.get("dim_y_mm")] if pd.notna(v)]
            if dims:
                height_candidates.append(int(max(dims)))
        height_mm = _mode_int(height_candidates) or (max(height_candidates) if height_candidates else None)

        muebles_idx = muebles.index[muebles["mueble_id"].astype(str) == str(mueble_id)]
        if len(muebles_idx):
            muebles.loc[muebles_idx, "ancho_mueble_mm"] = width_mm
            muebles.loc[muebles_idx, "ancho_mueble_cm"] = int(round(width_mm / 10.0)) if width_mm else pd.NA
            muebles.loc[muebles_idx, "alto_mueble_mm"] = height_mm
            muebles.loc[muebles_idx, "alto_mueble_cm"] = int(round(height_mm / 10.0)) if height_mm else pd.NA

        piezas.loc[idx, "inferred_width_mm"] = width_mm if width_mm else pd.NA
        piezas.loc[idx, "inferred_height_mm"] = height_mm if height_mm else pd.NA
        piezas.loc[idx, "inference_source"] = np.where(
            piezas.loc[idx, "is_structural"].fillna(False),
            "geometry",
            piezas.loc[idx, "inference_source"],
        )

    muebles["alto_total_cm"] = pd.to_numeric(muebles.get("alto_total_mm"), errors="coerce").apply(
        lambda v: int(round(v / 10.0)) if pd.notna(v) else pd.NA
    )

    piezas = piezas.merge(
        muebles[["mueble_id", "categoria", "rule_id"]],
        on="mueble_id",
        how="left",
        suffixes=("", "_mueble"),
    )

    # MB-E detector priority: A) geometry from despiece dimensions, B) text/code patterns, C) rule_id fallback.
    for mueble_id, group in piezas[piezas["categoria"].eq("MB-E")].groupby("mueble_id"):
        gidx = group.index
        notes = None
        source = None
        detected = None

        drawer_rows = group[group["is_drawer_part"].fillna(False)]
        candidates = []
        for ridx, row in drawer_rows.iterrows():
            for dim in [row.get("dim_x_mm"), row.get("dim_y_mm")]:
                if pd.isna(dim):
                    continue
                d = int(dim)
                if 190 <= d <= 205:
                    candidates.append((ridx, 198))
                elif 290 <= d <= 305:
                    candidates.append((ridx, 298))
        vals = [c[1] for c in candidates]
        if vals:
            if set(vals) == {198}:
                detected, source = 198, "geometry"
            elif set(vals) == {298}:
                detected, source = 298, "geometry"
            else:
                counts = Counter(vals)
                major_h, major_n = counts.most_common(1)[0]
                if major_n / len(vals) >= 0.7:
                    detected, source = major_h, "geometry_majority"
                    notes = "Conflicto 198/298 resuelto por mayoría"
                else:
                    source = "geometry_conflict"
                    notes = "Conflicto 198 y 298 detectados"

        if detected is None and source != "geometry_conflict":
            txt = " ".join(
                group[["piece_id", "tipologia", "observaciones"]].fillna("").astype(str).agg(" ".join, axis=1).tolist()
            ).upper()
            has_198 = any(t in txt for t in ["198", "E20", "H198", "EX198"])
            has_298 = any(t in txt for t in ["298", "E30", "H298", "EX298"])
            if has_198 ^ has_298:
                detected = 198 if has_198 else 298
                source = "text_code"
            elif has_198 and has_298:
                notes = "Conflicto por códigos 198 y 298"
                source = "text_code_conflict"

        if detected is None and source not in {"geometry_conflict", "text_code_conflict"}:
            rid = str(group["rule_id"].dropna().astype(str).head(1).squeeze()).upper()
            if any(t in rid for t in ["E20", "198"]):
                detected, source = 198, "rule_id"
            elif any(t in rid for t in ["E30", "298"]):
                detected, source = 298, "rule_id"

        m_idx = muebles.index[muebles["mueble_id"].astype(str) == str(mueble_id)]
        if len(m_idx) and detected in {198, 298}:
            muebles.loc[m_idx, "extraible_altura_mm"] = detected
            muebles.loc[m_idx, "extraible_codigo"] = "E20" if detected == 198 else "E30"
            muebles.loc[m_idx, "inference_source"] = source
            hit_indexes = [r for r, _ in candidates if _ == detected]
            piezas.loc[hit_indexes, "detected_drawer_height_mm"] = detected
            piezas.loc[hit_indexes, "inference_source"] = source
        elif len(m_idx):
            muebles.loc[m_idx, "split_notes"] = notes or "No se pudo detectar 198/298 desde despiece"
            muebles.loc[m_idx, "inference_source"] = source or "missing"

    def build_tipologia_split(row: pd.Series) -> pd.Series:
        categoria = _norm_text(row.get("categoria"))
        split = categoria
        status = "NOT_APPLICABLE"
        notes = ""
        source = _norm_text(row.get("inference_source"))

        if categoria == "MB-C":
            n_caj = pd.to_numeric(row.get("n_cajones"), errors="coerce")
            ancho_cm = pd.to_numeric(row.get("ancho_mueble_cm"), errors="coerce")
            if pd.notna(n_caj) and pd.notna(ancho_cm):
                split = f"MB-{int(n_caj)}C-{int(ancho_cm)}"
                status = "OK"
                source = source or "geometry"
            else:
                split = "MB-C-UNK"
                status = "MISSING_DATA"
                missing = []
                if pd.isna(n_caj):
                    missing.append("n_cajones")
                if pd.isna(ancho_cm):
                    missing.append("ancho")
                notes = "Falta: " + ", ".join(missing)
        elif categoria == "MB-E":
            code = _norm_text(row.get("extraible_codigo"))
            if code in {"E20", "E30"}:
                split = f"MB-{code}"
                status = "OK"
            else:
                split = "MB-E-UNK"
                status = "MISSING_DATA"
                notes = _norm_text(row.get("split_notes")) or "No se pudo detectar 198/298 desde despiece"
        elif categoria == "MP-R":
            alto_cm = pd.to_numeric(row.get("alto_mueble_cm"), errors="coerce")
            if pd.notna(alto_cm):
                split = f"MP-R{int(alto_cm)}"
                status = "OK"
                source = source or "geometry"
            else:
                split = "MP-R-UNK"
                status = "MISSING_DATA"
                notes = "Falta alto_mueble_cm"
        elif categoria == "MA-N":
            total_cm = pd.to_numeric(row.get("alto_total_cm"), errors="coerce")
            if pd.notna(total_cm):
                split = f"MA-N{int(total_cm)}"
                status = "OK"
            else:
                split = "MA-N-UNK"
                status = "MISSING_DATA"
                notes = "Falta alto_total_cm"

        return pd.Series({"tipologia_split": split, "split_status": status, "split_notes": notes, "inference_source": source})

    muebles[["tipologia_split", "split_status", "split_notes", "inference_source"]] = muebles.apply(
        build_tipologia_split, axis=1
    )

    for col in MUEBLES_HEADERS:
        if col not in muebles.columns:
            muebles[col] = ""
    for col in PIEZAS_HEADERS:
        if col not in piezas.columns:
            piezas[col] = ""

    return muebles[MUEBLES_HEADERS].copy(), piezas[PIEZAS_HEADERS].copy()

def _to_values(df: pd.DataFrame) -> list[list[Any]]:
    values = []
    for _, row in df.iterrows():
        vals = []
        for v in row.tolist():
            if isinstance(v, bool):
                vals.append("TRUE" if v else "FALSE")
            elif pd.isna(v):
                vals.append("")
            elif isinstance(v, float):
                vals.append(round(v, 2))
            else:
                vals.append(v)
        values.append(vals)
    return values


def _get_worksheet(client: gspread.Client, spreadsheet_id: str, worksheet_name: str, headers: list[str]):
    spreadsheet = client.open_by_key(spreadsheet_id)
    try:
        ws = spreadsheet.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=max(26, len(headers) + 2))

    first_row = ws.row_values(1)
    if not first_row:
        ws.update("A1", [headers])
        return ws

    merged_headers = first_row + [h for h in headers if h not in first_row]
    if first_row != merged_headers:
        ws.update("A1", [merged_headers])
    return ws


def append_to_cache(df_muebles: pd.DataFrame, df_piezas: pd.DataFrame) -> tuple[int, int]:
    creds = st.secrets["gcp_service_account"]
    spreadsheet_id = st.secrets["google_sheets"]["cache_spreadsheet_id"]
    worksheet_muebles = st.secrets["google_sheets"].get("worksheet_muebles", "muebles_cache")
    worksheet_piezas = st.secrets["google_sheets"].get("worksheet_piezas", "piezas_cache")

    client = gspread.service_account_from_dict(creds)

    ws_m = _get_worksheet(client, spreadsheet_id, worksheet_muebles, MUEBLES_HEADERS)
    ws_p = _get_worksheet(client, spreadsheet_id, worksheet_piezas, PIEZAS_HEADERS)

    existing_cache_ids = set(ws_m.col_values(1)[1:])
    hash_col_idx = MUEBLES_HEADERS.index("data_hash") + 1
    existing_data_hashes = set(ws_m.col_values(hash_col_idx)[1:])

    m_new = df_muebles[
        (~df_muebles["cache_id"].astype(str).isin(existing_cache_ids))
        & (~df_muebles["data_hash"].astype(str).isin(existing_data_hashes))
    ].copy()

    existing_piece_ids = set(ws_p.col_values(1)[1:])
    p_new = df_piezas[~df_piezas["cache_row_id"].astype(str).isin(existing_piece_ids)].copy()

    if not m_new.empty:
        ws_m.append_rows(_to_values(m_new), value_input_option="USER_ENTERED")
    if not p_new.empty:
        ws_p.append_rows(_to_values(p_new), value_input_option="USER_ENTERED")

    return len(m_new), len(p_new)


def _derive_project_id(filename: str) -> str:
    name = filename.rsplit(".", 1)[0]
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_")
    return safe or "projecto_sin_id"


st.title("🕵️ Inspector de proyectos")
st.caption("Clasifica tipologías MB/MB-H/MB-FE/MA/MA-H/MA-N/MP/MP-R a partir de despieces CUBRO y guarda caché.")

col_back, _ = st.columns([1, 5])
with col_back:
    if st.button("⬅️ Volver al Pre Production Hub"):
        st.switch_page("Home.py")

uploaded = st.sidebar.file_uploader("Upload CSV", type=["csv"])
project_id_input = st.sidebar.text_input("project_id (opcional)")
debug_mode = st.sidebar.checkbox("Modo debug", value=False)
save_cache = st.sidebar.checkbox("Guardar en caché (Google Sheets)", value=True)
process = st.sidebar.button("Procesar", type="primary")

if process:
    if not uploaded:
        st.warning("Sube un archivo CSV antes de procesar.")
    else:
        source_filename = uploaded.name
        project_id = project_id_input.strip()
        project_name = source_filename.rsplit(".", 1)[0]
        rules_version = st.secrets.get("app", {}).get("rules_version", "v2.1")
        timezone_name = st.secrets.get("app", {}).get("timezone", "Europe/Madrid")
        import_timestamp = datetime.now(ZoneInfo(timezone_name)).isoformat()

        with st.spinner("Procesando despiece..."):
            try:
                df_normalized, debug_mapping, normalized_headers = load_and_normalize_csv(
                    uploaded,
                    debug_mode=debug_mode,
                )
            except Exception as exc:
                st.error(f"Error al leer/normalizar CSV: {exc}")
                st.stop()

            if debug_mode:
                with st.expander("Debug de mapeo de columnas"):
                    st.write("Headers normalizados detectados:")
                    st.code("\n".join(normalized_headers) if normalized_headers else "(sin headers)")
                    st.write("Mapeo aplicado (origen -> interno):")
                    st.json(debug_mapping)

            project_id_from_csv = ""
            if "project_id" in df_normalized.columns:
                project_id_from_csv = (
                    df_normalized["project_id"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().head(1).squeeze()
                    if not df_normalized.empty
                    else ""
                )
                project_id_from_csv = _norm_text(project_id_from_csv)

            project_id = project_id or project_id_from_csv or _derive_project_id(source_filename)

            missing_mueble = int(df_normalized["mueble_id"].isna().sum())
            if missing_mueble > 0:
                st.warning(
                    f"Se ignoraron {missing_mueble} piezas sin prefijo de mueble válido (regex ^(M\\d+))."
                )

            df_piezas_cache = build_pieces_cache_rows(
                df_normalized,
                project_id=project_id,
                source_filename=source_filename,
                import_timestamp=import_timestamp,
                rules_version=rules_version,
            )

            if df_piezas_cache.empty:
                st.error("No hay piezas válidas (P/C/PQ con mueble_id) para clasificar.")
                st.stop()

            df_features = aggregate_by_mueble(df_piezas_cache)
            df_muebles_cache = build_muebles_cache_rows(
                df_features,
                project_id=project_id,
                project_name=project_name,
                source_filename=source_filename,
                import_timestamp=import_timestamp,
                rules_version=rules_version,
            )

            df_muebles_cache, df_piezas_cache = enrich_caches_for_splits(df_muebles_cache, df_piezas_cache)
            df_muebles_cache = normalize_required_columns(df_muebles_cache)
            df_muebles_view, cols_present, cols_missing = safe_select_columns(
                df_muebles_cache,
                DISPLAY_COLUMNS_MUEBLES,
            )

            if debug_mode:
                with st.expander("Debug de columnas de detalle por mueble"):
                    st.write("Columnas canónicas faltantes:")
                    st.json(cols_missing)
                    st.write("Columnas actuales en df_muebles_cache:")
                    st.json(df_muebles_cache.columns.tolist())
                    st.write("Vista previa (head 3):")
                    st.dataframe(df_muebles_view.head(3), use_container_width=True, hide_index=True)

        st.subheader("KPIs por categoría")
        categoria_series = df_muebles_cache.get("categoria", pd.Series([], dtype=str)).astype(str).fillna("")
        CATEGORIES_ALL = [
            "MB",
            "MB-B",
            "MB-C",
            "MB-E",
            "MB-FE",
            "MB-H",
            "MB-Q",
            "MA",
            "MA-H",
            "MA-N",
            "MP",
            "MP-A",
            "MP-R",
            "LVV-60",
            "LVV-45",
            "UNK",
        ]
        total = len(df_muebles_cache)
        counts = categoria_series.value_counts(dropna=False).to_dict()
        counts.pop("LVV", None)
        cols = st.columns(len(CATEGORIES_ALL))
        for idx, cat in enumerate(CATEGORIES_ALL):
            count = int(counts.get(cat, 0))
            pct = (count / total * 100.0) if total else 0
            cols[idx].metric(cat, f"{count}", f"{pct:.1f}%")

        with st.expander("Validación de split tipológico", expanded=debug_mode):
            split_counts = (
                df_muebles_cache.groupby(["categoria", "split_status"], dropna=False)
                .size()
                .reset_index(name="count")
                .sort_values(["categoria", "split_status"])
            )
            st.write("Conteo por categoría y split_status")
            st.dataframe(split_counts, use_container_width=True, hide_index=True)

            missing_pct = (
                df_muebles_cache.assign(is_missing=df_muebles_cache["split_status"].eq("MISSING_DATA"))
                .groupby("categoria", dropna=False)["is_missing"]
                .mean()
                .mul(100)
                .round(1)
                .reset_index(name="missing_pct")
                .sort_values("missing_pct", ascending=False)
            )
            st.write("% MISSING_DATA por categoría")
            st.dataframe(missing_pct, use_container_width=True, hide_index=True)

            unk_examples = (
                df_muebles_cache[df_muebles_cache["tipologia_split"].astype(str).str.endswith("-UNK")]
                [["project_id", "mueble_id", "categoria", "split_notes"]]
                .groupby("categoria", dropna=False)
                .head(5)
            )
            st.write("Ejemplos de filas UNK (máximo 5 por categoría)")
            st.dataframe(unk_examples, use_container_width=True, hide_index=True)

        st.subheader("Detalle por mueble")
        st.dataframe(
            df_muebles_view,
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Casos ambiguos (UNK)")
        df_unk = df_muebles_cache[categoria_series.eq("UNK")].copy()
        df_unk_view, cols_present_unk, cols_missing_unk = safe_select_columns(df_unk, CANONICAL_COLUMNS_UNK)

        if df_unk.empty:
            st.info("No hay casos UNK para este archivo.")

        if debug_mode:
            with st.expander("Debug de columnas de casos UNK"):
                st.write("Columnas canónicas faltantes en UNK:")
                st.json(cols_missing_unk)
                st.write("Columnas actuales en df_muebles_cache:")
                st.json(df_muebles_cache.columns.tolist())
                st.write("Vista previa de UNK (head 3):")
                st.dataframe(df_unk_view.head(3), use_container_width=True, hide_index=True)

        st.dataframe(
            df_unk_view,
            use_container_width=True,
            hide_index=True,
        )

        df_piezas_view, _, cols_missing_piezas = safe_select_columns(df_piezas_cache, CANONICAL_COLUMNS_PIEZAS_DETAIL)
        if debug_mode and cols_missing_piezas:
            with st.expander("Debug de columnas de detalle por pieza"):
                st.write("Columnas canónicas faltantes en piezas:")
                st.json(cols_missing_piezas)
                st.write("Columnas actuales en df_piezas_cache:")
                st.json(df_piezas_cache.columns.tolist())

        with st.expander("Detalle por pieza (P/C/PQ)"):
            st.dataframe(
                df_piezas_view,
                use_container_width=True,
                hide_index=True,
            )

        st.download_button(
            "Descargar CSV resumen",
            data=df_muebles_cache.to_csv(index=False).encode("utf-8"),
            file_name=f"{project_id}_muebles_resumen.csv",
            mime="text/csv",
        )
        st.download_button(
            "Descargar CSV piezas",
            data=df_piezas_cache.to_csv(index=False).encode("utf-8"),
            file_name=f"{project_id}_piezas.csv",
            mime="text/csv",
        )

        if save_cache:
            with st.spinner("Guardando en Google Sheets..."):
                try:
                    added_m, added_p = append_to_cache(df_muebles_cache, df_piezas_cache)
                    st.success(
                        f"Cache actualizado. Muebles añadidos: {added_m}. Piezas añadidas: {added_p}."
                    )
                except Exception as exc:
                    st.error(f"No se pudo guardar en caché: {exc}")
        else:
            st.info("Procesado completado sin guardar en Google Sheets.")
