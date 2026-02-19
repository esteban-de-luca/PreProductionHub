from __future__ import annotations

import hashlib
import io
import re
from datetime import datetime
from typing import Any

import gspread
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

COLUMN_SYNONYMS = {
    "piece_id": ["id", "id pieza", "id_pieza", "pieza", "id pieza cubro", "piece_id"],
    "tipologia": ["tipología", "tipologia", "tipo", "d", "tipologia pieza"],
    "alto_mm": ["alto", "alto mm", "h", "altura", "altura mm"],
    "ancho_mm": ["ancho", "ancho mm", "w", "anchura"],
    "handle_pos": ["posición tir.", "posicion tirador", "tirador", "pos tir", "posicion tir.", "posicion"],
    "observaciones": ["observaciones", "obs", "notas", "j"],
}


def _norm_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _find_column(df: pd.DataFrame, logical_name: str) -> str | None:
    normalized = {str(col).strip().lower(): col for col in df.columns}
    for candidate in COLUMN_SYNONYMS[logical_name]:
        col = normalized.get(candidate.lower())
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


def load_and_normalize_csv(file) -> pd.DataFrame:
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

    piece_col = _find_column(df, "piece_id")
    tip_col = _find_column(df, "tipologia")
    alto_col = _find_column(df, "alto_mm")
    if piece_col is None or tip_col is None or alto_col is None:
        raise ValueError(
            "Faltan columnas mínimas requeridas: piece_id, tipologia y alto_mm."
        )

    ancho_col = _find_column(df, "ancho_mm")
    handle_col = _find_column(df, "handle_pos")
    obs_col = _find_column(df, "observaciones")

    normalized = pd.DataFrame()
    normalized["piece_id"] = df[piece_col].map(_norm_text)
    normalized["tipologia"] = df[tip_col].map(_norm_text)
    normalized["alto_mm"] = df[alto_col].map(_parse_number) if alto_col else None
    normalized["ancho_mm"] = df[ancho_col].map(_parse_number) if ancho_col else None
    normalized["handle_pos_raw"] = df[handle_col].map(_norm_text) if handle_col else ""
    normalized["observaciones"] = df[obs_col].map(_norm_text) if obs_col else ""
    normalized["row_number_in_source"] = df.index + 2

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
    return normalized


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
    out = df_features.copy()
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

    for col in MUEBLES_HEADERS:
        if col not in out.columns:
            out[col] = ""
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
save_cache = st.sidebar.checkbox("Guardar en caché (Google Sheets)", value=True)
process = st.sidebar.button("Procesar", type="primary")

if process:
    if not uploaded:
        st.warning("Sube un archivo CSV antes de procesar.")
    else:
        source_filename = uploaded.name
        project_id = project_id_input.strip() or _derive_project_id(source_filename)
        project_name = source_filename.rsplit(".", 1)[0]
        rules_version = st.secrets.get("app", {}).get("rules_version", "v2.1")
        timezone_name = st.secrets.get("app", {}).get("timezone", "Europe/Madrid")
        import_timestamp = datetime.now(ZoneInfo(timezone_name)).isoformat()

        with st.spinner("Procesando despiece..."):
            try:
                df_normalized = load_and_normalize_csv(uploaded)
            except Exception as exc:
                st.error(f"Error al leer/normalizar CSV: {exc}")
                st.stop()

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

        st.subheader("KPIs por categoría")
        categories = ["MB", "MB-H", "MB-FE", "MA", "MA-H", "MA-N", "MP", "MP-R", "UNK"]
        total = len(df_muebles_cache)
        cols = st.columns(len(categories))
        for idx, cat in enumerate(categories):
            count = int((df_muebles_cache["categoria"] == cat).sum())
            pct = (count / total * 100.0) if total else 0
            cols[idx].metric(cat, f"{count}", f"{pct:.1f}%")

        st.subheader("Detalle por mueble")
        st.dataframe(
            df_muebles_cache[
                [
                    "mueble_id",
                    "n_frentes",
                    "n_puertas",
                    "n_cajones",
                    "alto_total_mm",
                    "has_handle_data",
                    "has_any_door_without_handle",
                    "door_heights_mm",
                    "drawer_heights_mm",
                    "categoria",
                    "confidence",
                    "rule_id",
                    "razon",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Casos ambiguos (UNK)")
        st.dataframe(
            df_muebles_cache[df_muebles_cache["categoria"].eq("UNK")][
                [
                    "mueble_id",
                    "n_puertas",
                    "n_cajones",
                    "alto_total_mm",
                    "door_heights_mm",
                    "drawer_heights_mm",
                    "confidence",
                    "rule_id",
                    "razon",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Detalle por pieza (P/C/PQ)")
        st.dataframe(
            df_piezas_cache[
                [
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
            ],
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
