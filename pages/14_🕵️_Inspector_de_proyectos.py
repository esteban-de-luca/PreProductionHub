from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from datetime import datetime
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
    "alto_mm": ["alto", "altura", "h", "alto mm", "altura mm"],
    "ancho_mm": ["ancho", "w", "width", "ancho mm", "anchura"],
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
    for logical_name in ["piece_id", "tipologia", "alto_mm", "ancho_mm", "handle_pos", "observaciones", "project_id"]:
        mapped = find_column_by_synonyms(df, logical_name)
        if mapped is not None:
            found_mapping[logical_name] = mapped

    rename_map = {source_col: target_col for target_col, source_col in found_mapping.items()}
    df = df.rename(columns=rename_map).copy()

    required_cols = ["piece_id", "tipologia", "alto_mm"]
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
    normalized["alto_mm"] = pd.to_numeric(df["alto_mm"], errors="coerce")
    normalized["ancho_mm"] = pd.to_numeric(df["ancho_mm"], errors="coerce") if "ancho_mm" in df.columns else None
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

    normalized = normalized[normalized["normalized_tipologia"].isin(["P", "C"])].copy()
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
    rows = rows[rows["mueble_id"].notna()].copy()

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

    rows = rows.rename(columns={"tipologia": "tipologia", "piece_id": "piece_id"})

    for col in PIEZAS_HEADERS:
        if col not in rows.columns:
            rows[col] = ""

    return rows[PIEZAS_HEADERS].copy()


def aggregate_by_mueble(df_piezas_cache: pd.DataFrame) -> pd.DataFrame:
    def _drawer_heights(group: pd.DataFrame) -> str:
        vals = group.loc[group["is_drawer"], "alto_mm"].dropna().astype(float)
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
    door_heights_set = set(door_heights)

    if n_puertas == 2 and n_cajones == 0 and door_heights_set in ({798, 1198}, {798, 1398}):
        return (
            "MA-N",
            0.95,
            "RULE_MAN_FRIDGE_798_1198_1398",
            "2 puertas 798 + (1198/1398) sin cajones",
        )

    if n_puertas == 2 and bool(row_features.get("has_mixed_handle_doors", False)):
        return (
            "MB-FE",
            0.90,
            "RULE_MBFE_TWO_DOORS_ONE_HANDLE",
            "2 puertas: una con tirador y otra sin tirador",
        )

    if n_puertas == 0 and n_cajones >= 1 and ({148, 298} & drawer_heights):
        return ("MB-H", 0.95, "RULE_MBH_DRAWER_148_298", "Sin puertas y cajón 148/298")

    allowed_mpr_heights = {419, 429, 439, 449, 619, 629, 639, 649, 819, 829, 839, 849}
    if n_puertas in {1, 2} and bool(row_features.get("has_any_door_without_handle", False)):
        if door_no_handle_heights and all(h in allowed_mpr_heights for h in door_no_handle_heights):
            return (
                "MP-R",
                0.95,
                "RULE_MPR_NO_HANDLE_ALLOWED_HEIGHTS",
                "Puerta(s) sin tirador con altura válida recrecida",
            )

    alto_total = float(row_features.get("alto_total_mm", 0) or 0)
    if n_puertas >= 1 and n_cajones >= 1 and alto_total > 800:
        return (
            "MA-H",
            0.90,
            "RULE_MAH_DOORS_DRAWERS_TOTAL_GT_800",
            "Puertas + cajones y suma frentes > 800",
        )

    if bool(row_features.get("has_handle_data", False)):
        if n_puertas >= 2 and bool(row_features.get("has_handle_pos4", False)):
            return ("MA", 0.90, "RULE_HANDLE_POS4_MULTI_DOOR", "2+ puertas con tirador posición 4")
        if n_puertas == 1 and bool(row_features.get("has_handle_pos4", False)):
            return ("MP", 0.90, "RULE_HANDLE_POS4_SINGLE_DOOR", "1 puerta con tirador posición 4")
        if n_puertas in {1, 2} and bool(row_features.get("has_handle_pos1_2", False)):
            return ("MB", 0.90, "RULE_HANDLE_POS1_2", "Tirador en posición superior")
        if n_puertas == 1 and bool(row_features.get("has_handle_pos3", False)):
            return ("MA", 0.90, "RULE_HANDLE_POS3", "1 puerta con tirador lateral centro")
        if n_puertas == 1 and bool(row_features.get("has_handle_pos5", False)):
            return ("MP", 0.90, "RULE_HANDLE_POS5", "1 puerta con tirador inferior centro")

    if alto_total > 800:
        return ("MA", 0.75, "RULE_FALLBACK_HEIGHT_GT_800", "Alto total de frentes > 800 mm")
    if alto_total <= 800 and n_cajones > 0:
        return ("MB", 0.75, "RULE_FALLBACK_HEIGHT_LE_800_WITH_DRAWER", "Alto <= 800 mm y con cajones")
    if alto_total <= 800 and n_cajones == 0:
        if n_puertas in {1, 2} and bool(row_features.get("has_any_door_without_handle", False)):
            return (
                "UNK",
                0.40,
                "RULE_UNK_NO_HANDLE_HEIGHT_OUTSIDE_MPR_SET",
                "Puerta sin tirador con altura fuera del set recrecido",
            )
        return (
            "UNK",
            0.40,
            "RULE_UNK_HEIGHT_LE_800_NO_DRAWER",
            "Alto <= 800 mm, sin cajones y sin señales suficientes",
        )

    return ("UNK", 0.40, "RULE_UNK", "No se pudo inferir categoría")


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
    if first_row != headers:
        ws.update("A1", [headers])
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
    existing_data_hashes = set(ws_m.col_values(24)[1:])

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

            df_muebles_cache = normalize_required_columns(df_muebles_cache)
            df_muebles_view, cols_present, cols_missing = safe_select_columns(
                df_muebles_cache,
                CANONICAL_COLUMNS_MUEBLES,
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
        categories = ["MB", "MB-H", "MB-FE", "MA", "MA-H", "MA-N", "MP", "MP-R", "UNK"]
        total = len(df_muebles_cache)
        category_counts = categoria_series.value_counts(dropna=False)
        cols = st.columns(len(categories))
        for idx, cat in enumerate(categories):
            count = int(category_counts.get(cat, 0))
            pct = (count / total * 100.0) if total else 0
            cols[idx].metric(cat, f"{count}", f"{pct:.1f}%")

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

        st.subheader("Detalle por pieza (P/C/PQ)")
        df_piezas_view, _, cols_missing_piezas = safe_select_columns(df_piezas_cache, CANONICAL_COLUMNS_PIEZAS_DETAIL)
        if debug_mode and cols_missing_piezas:
            with st.expander("Debug de columnas de detalle por pieza"):
                st.write("Columnas canónicas faltantes en piezas:")
                st.json(cols_missing_piezas)
                st.write("Columnas actuales en df_piezas_cache:")
                st.json(df_piezas_cache.columns.tolist())
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
