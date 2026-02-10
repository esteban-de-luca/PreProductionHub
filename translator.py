import os
import pandas as pd
from typing import Dict, Tuple, Optional, List


# =========================================================
# INPUT CUBRO (CSV)
# =========================================================

EXPECTED_COLS = [
    "ID de Proyecto",
    "SKU",
    "ID de pieza",
    "Tipología de pieza",
    "Ancho",
    "Alto",
    "Material",
    "Gama",
    "Acabado",
    "Mecanizado o sin mecanizar (vacío)",
    "Modelo de tirador",
    "Posición de tirador",
    "Dirección de apertura de puerta",
    "Acabado de tirador",
]

CUBRO_COLORS_ORDER = [
    "Blanco", "Negro", "Tinta", "Seda", "Tipo", "Crema", "Humo", "Zafiro",
    "Celeste", "Pino", "Noche", "Marga", "Argil", "Curry", "Roto", "Ave"
]

ALVIC_COLOR_CODES_ORDER = [
    "L3806", "L4596", "L4706", "L5266", "L5276", "L5556", "L5866", "L5906",
    "L6766", "L9146", "L9166", "L9556", "LA056", "LA066", "LA076", "LA086"
]

# Texto (lo que aparece en la DB ALVIC)
COLOR_TEXT_MAP: Dict[str, str] = {
    "blanco": "BLANCO SM",
    "negro": "NEGRO SM",
    "tinta": "GRIS PLOMO SM",
    "seda": "CASHMERE SM",
    "tipo": "BASALTO SM",
    "crema": "MAGNOLIA SM",
    "humo": "GRIS NUBE SM",
    "zafiro": "AZUL ÍNDIGO SM",
    "celeste": "AGUA MARINA SM",
    "pino": "VERDE SALVIA SM",
    "noche": "AZUL MARINO SM",
    "marga": "COTTO SM",
    "argil": "ALMAGRA SM",
    "curry": "CAMEL SM",
    "roto": "ARENA SM",
    "ave": "TORTORA SM",
}

# Código interno (puede servir si la DB algún día lo incluye)
COLOR_CODE_MAP: Dict[str, str] = {
    c.casefold(): code
    for c, code in zip(CUBRO_COLORS_ORDER, ALVIC_COLOR_CODES_ORDER)
}


# =========================================================
# Helpers
# =========================================================

def _norm_str(x) -> str:
    return str(x).strip()

def _norm_key(x) -> str:
    return _norm_str(x).casefold()

def clamp_min_100(x: int) -> int:
    return 100 if x < 100 else x

def _is_empty_value(v) -> bool:
    """True si el valor debe considerarse vacío (incluye NaN)."""
    if v is None:
        return True
    try:
        # NaN real
        if pd.isna(v):
            return True
    except Exception:
        pass

    s = str(v).strip().casefold()
    return s in {"", "nan", "none", "null"}


def parse_mm(value) -> Optional[float]:
    """Parsea mm robusto (soporta coma decimal y texto como 'mm')."""
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in {"", "nan", "none"}:
        return None
    s = s.replace("mm", "").replace(",", ".").replace(" ", "")
    try:
        return float(s)
    except Exception:
        return None


# =========================================================
# Normalización de columnas
# =========================================================

def _canonicalize(col: str) -> str:
    s = str(col).strip()
    s = " ".join(s.split())
    return s.casefold()

def _rename_columns_with_synonyms(df: pd.DataFrame) -> pd.DataFrame:
    synonyms = {
        "Ancho": ["ancho", "width", "w", "anchura"],
        "Alto": ["alto", "height", "h", "altura"],
        "Acabado": ["acabado", "color", "finish"],
        "Material": ["material", "mat"],
        "Gama": ["gama", "serie", "range"],
        "Mecanizado o sin mecanizar (vacío)": [
            "mecanizado o sin mecanizar (vacío)",
            "mecanizado o sin mecanizar (vacio)",
            "mecanizado o sin mecanizar",
            "mecanizado",
            "cnc",
            "mecanizada",
            "mecanizado/sin mecanizar",
        ],
    }

    canon_cols = {c: _canonicalize(c) for c in df.columns}
    rename_dict = {}

    for col in df.columns:
        ccanon = canon_cols[col]
        for target, keys in synonyms.items():
            keys_canon = set(_canonicalize(k) for k in keys)
            if ccanon in keys_canon:
                rename_dict[col] = target

    if rename_dict:
        df = df.rename(columns=rename_dict)

    df.columns = [str(c).strip() for c in df.columns]
    return df


def load_input_csv(path: str) -> pd.DataFrame:
    """
    - Si el CSV viene con cabecera válida, la usa.
    - Si viene sin cabecera (como tu ejemplo), re-lee con header=None y asigna EXPECTED_COLS.
    """
    df = pd.read_csv(path)
    df = _rename_columns_with_synonyms(df)

    if all(c in df.columns for c in ["Ancho", "Alto", "Acabado"]):
        return df

    df2 = pd.read_csv(path, header=None)
    if df2.shape[1] >= len(EXPECTED_COLS):
        df2 = df2.iloc[:, :len(EXPECTED_COLS)]
        df2.columns = EXPECTED_COLS
        df2 = _rename_columns_with_synonyms(df2)
        return df2

    raise ValueError(
        "El CSV input no tiene el formato esperado.\n"
        f"Columnas detectadas: {df.columns.tolist()} | (sin header): {df2.shape[1]} columnas"
    )


# =========================================================
# DB ALVIC
# =========================================================

def load_alvic_db(db_csv_path: str) -> pd.DataFrame:
    if not os.path.exists(db_csv_path):
        raise FileNotFoundError(f"No existe la base ALVIC: {db_csv_path}")

    db = pd.read_csv(db_csv_path)

    # Normaliza campos clave
    db["Modelo"] = db["Modelo"].astype(str).str.upper().str.strip()
    db["Color_raw"] = db["Color"].astype(str).str.upper().str.strip()

    for c in ["Alto", "Ancho"]:
        db[c] = pd.to_numeric(db[c], errors="coerce")

    db = db.dropna(subset=["ARTICULO", "Color_raw", "Alto", "Ancho"])

    # Filtra SOLO 06 ZENIT (según tu requisito)
    db = db[
        db["Modelo"].str.contains("ZENIT", na=False)
        & db["Modelo"].str.contains("06", na=False)
    ].copy()

    return db


# =========================================================
# Detección LAC / Mecanizado
# =========================================================

def detect_is_lac(row: pd.Series) -> bool:
    for col in ["Material", "Gama"]:
        if col in row.index and "LAC" in str(row[col]).upper():
            return True
    return False

def is_machined(row: pd.Series) -> Tuple[bool, str]:
    """Aplica reglas de mecanizado A1..A4 (soporta coma decimal)."""
    mech_col = "Mecanizado o sin mecanizar (vacío)"
    if mech_col in row.index and not _is_empty_value(row[mech_col]):
        return True, "A1_mecanizado_text"

    handle_model = str(row.get("Modelo de tirador", "")).casefold()
    if any(token in handle_model for token in ("round", "square", "pill")):
        return True, "A2_handle_model"

    w_raw = parse_mm(row.get("Ancho"))
    h_raw = parse_mm(row.get("Alto"))
    if w_raw is None or h_raw is None:
        return False, "NO"

    # Regla A3: si alguna dimensión < 100mm
    if w_raw < 100 or h_raw < 100:
        return True, "A3_lt_100"

    # Regla A4: si ambas dimensiones < 250mm
    if w_raw < 250 and h_raw < 250:
        return True, "A4_lt_250x250"

    return False, "NO"


# =========================================================
# Matching tamaño (EXACT / ROTATED_EXACT / FIT / ROTATED_FIT)
# =========================================================

def find_best_match(db: pd.DataFrame, w: int, h: int) -> Tuple[Optional[pd.Series], str]:
    exact = db[(db["Ancho"] == w) & (db["Alto"] == h)]
    if not exact.empty:
        return exact.iloc[0], "EXACT"

    rotated = db[(db["Ancho"] == h) & (db["Alto"] == w)]
    if not rotated.empty:
        return rotated.iloc[0], "ROTATED_EXACT"

    tol_ancho = (db["Ancho"] != 1197).astype(int) * 3
    tol_alto = (db["Alto"] != 2498).astype(int) * 3

    fit = db[(db["Ancho"] + tol_ancho >= w) & (db["Alto"] + tol_alto >= h)].copy()
    if not fit.empty:
        fit["area"] = fit["Ancho"] * fit["Alto"]
        fit = fit.sort_values(["area", "Alto", "Ancho"])
        return fit.iloc[0], "FIT"

    rfit = db[(db["Ancho"] + tol_ancho >= h) & (db["Alto"] + tol_alto >= w)].copy()
    if not rfit.empty:
        rfit["area"] = rfit["Ancho"] * rfit["Alto"]
        rfit = rfit.sort_values(["area", "Alto", "Ancho"])
        return rfit.iloc[0], "ROTATED_FIT"

    return None, "NO_MATCH"


def _filter_db_by_color(db: pd.DataFrame, color_text: Optional[str], color_code: Optional[str]) -> Tuple[pd.DataFrame, str]:
    """
    Prioriza código interno (si estuviera en DB), pero si no hay resultados,
    hace fallback a texto (que es lo que tu DB 2026 contiene).
    """
    if color_code:
        d_code = db[db["Color_raw"] == str(color_code).upper()]
        if not d_code.empty:
            return d_code, "CODE"

    if color_text:
        d_text = db[db["Color_raw"] == str(color_text).upper()]
        if not d_text.empty:
            return d_text, "TEXT"

    return db, "FALLBACK_NO_COLOR_FILTER"


# =========================================================
# Motor principal
# =========================================================

OUTPUT_COLUMNS = [
    "referencia",
    "csub",
    "cordir",
    "almacen",
    "lin",
    "acod",
    "cant",
    "alargo",
    "aancho",
    "agrueso",
    "nplano",
]


def _format_meters(mm_value) -> str:
    if _is_empty_value(mm_value):
        return ""
    try:
        meters = float(mm_value) / 1000
    except Exception:
        return ""
    return f"{meters:.3f}".replace(".", ",")


def _choose_project_id_column(df: pd.DataFrame) -> str:
    # Preferencia explícita para proyecto.
    candidates = ["ID de Proyecto", "ProjectID", "ID_Cliente", "ID de pieza", "SKU"]
    for col in candidates:
        if col in df.columns:
            return col
    # Fallback: usa la primera columna disponible para evitar fallo en Streamlit.
    if len(df.columns) > 0:
        return df.columns[0]
    raise ValueError("El input no tiene columnas para definir referencia.")


def _choose_client_column(df: pd.DataFrame) -> Optional[str]:
    # Busca por sinónimos (case-insensitive) para "Cliente".
    candidates = [
        "Cliente",
        "Nombre cliente",
        "Nombre Cliente",
        "Client",
        "Customer",
        "ID_Cliente",
        "ID Cliente",
    ]
    canon = {_canonicalize(c): c for c in df.columns}
    for candidate in candidates:
        candidate_key = _canonicalize(candidate)
        if candidate_key in canon:
            return canon[candidate_key]
    return None


def build_reference(project_id: str, suffix: str, is_mec: bool) -> str:
    """Construye referencia final con límite total de 20 caracteres."""
    project_id = "" if _is_empty_value(project_id) else str(project_id).strip()
    suffix = "" if _is_empty_value(suffix) else str(suffix)
    ref_base = f"{project_id}_{suffix}" if suffix else project_id
    if is_mec:
        return "MEC_" + ref_base[:16]
    return ref_base[:20]


def extract_filename_suffix(input_filename: Optional[str]) -> str:
    if _is_empty_value(input_filename):
        return ""
    base_name = str(input_filename)
    if base_name.lower().endswith('.csv'):
        base_name = base_name[:-4]
    if '_' in base_name:
        _, suffix = base_name.split('_', 1)
        return suffix
    return ""


def translate_and_split(
    input_csv_path: str,
    db_csv_path: str,
    output_machined_csv_path: str,
    output_non_machined_csv_path: str,
    input_filename: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, int], pd.DataFrame, pd.DataFrame]:

    db = load_alvic_db(db_csv_path)
    inp = load_input_csv(input_csv_path)

    required_cols = ["Ancho", "Alto", "Acabado"]
    missing = [c for c in required_cols if c not in inp.columns]
    if missing:
        raise ValueError(f"Faltan columnas obligatorias en input: {missing}. Disponibles: {inp.columns.tolist()}")

    project_id_col = _choose_project_id_column(inp)
    filename_suffix = extract_filename_suffix(input_filename)
    is_lac_mask = inp.apply(detect_is_lac, axis=1)
    lac_df = inp[is_lac_mask].copy()

    out_rows: List[dict] = []

    for _, row in lac_df.iterrows():
        base = row.to_dict()
        machined_flag, machined_reason = is_machined(row)
        ancho_raw = row.get("Ancho")
        alto_raw = row.get("Alto")
        w_f = parse_mm(ancho_raw)
        h_f = parse_mm(alto_raw)

        # Normaliza dimensiones y aplica mínimo 100mm
        if w_f is None or h_f is None:
            out_rows.append({
                **base,
                "Codigo_ALVIC": "",
                "Match_type": "BAD_DIMS",
                "Color_filter_mode": "",
                "Color_ALVIC_text": "",
                "Color_ALVIC_code": "",
                "Input_Ancho_norm": "",
                "Input_Alto_norm": "",
                "DB_Ancho": "",
                "DB_Alto": "",
                "Es_LAC": True,
                "Es_Mecanizada": machined_flag,
                "Mec_reason": machined_reason,
                "Ancho_raw": ancho_raw,
                "Alto_raw": alto_raw,
                "Ancho_parsed_mm": w_f,
                "Alto_parsed_mm": h_f,
                "Output_Ancho_mm": "",
                "Output_Largo_mm": "",
                "Output_Grueso_mm": "",
            })
            continue
        w_raw = int(round(w_f))
        h_raw = int(round(h_f))
        w = clamp_min_100(w_raw)
        h = clamp_min_100(h_raw)

        # Mapea color
        cubro_color = _norm_str(row["Acabado"])
        color_text = COLOR_TEXT_MAP.get(_norm_key(cubro_color))
        color_code = COLOR_CODE_MAP.get(_norm_key(cubro_color))

        if not (color_text or color_code):
            out_rows.append({
                **base,
                "Codigo_ALVIC": "",
                "Match_type": "UNKNOWN_COLOR",
                "Color_filter_mode": "",
                "Color_ALVIC_text": "",
                "Color_ALVIC_code": "",
                "Input_Ancho_norm": w,
                "Input_Alto_norm": h,
                "DB_Ancho": "",
                "DB_Alto": "",
                "Es_LAC": True,
                "Es_Mecanizada": machined_flag,
                "Mec_reason": machined_reason,
                "Ancho_raw": ancho_raw,
                "Alto_raw": alto_raw,
                "Ancho_parsed_mm": w_f,
                "Alto_parsed_mm": h_f,
                "Output_Ancho_mm": w_raw,
                "Output_Largo_mm": h_raw,
                "Output_Grueso_mm": "",
            })
            continue

        # Filtra DB por color (con fallback)
        d_color, color_filter_mode = _filter_db_by_color(db, color_text=color_text, color_code=color_code)

        # Matching tamaño
        match, match_type = find_best_match(d_color, w=w, h=h)

        if match is None:
            out_rows.append({
                **base,
                "Codigo_ALVIC": "",
                "Match_type": "NO_MATCH",
                "Color_filter_mode": color_filter_mode,
                "Color_ALVIC_text": color_text or "",
                "Color_ALVIC_code": color_code or "",
                "Input_Ancho_norm": w,
                "Input_Alto_norm": h,
                "DB_Ancho": "",
                "DB_Alto": "",
                "Es_LAC": True,
                "Es_Mecanizada": machined_flag,
                "Mec_reason": machined_reason,
                "Ancho_raw": ancho_raw,
                "Alto_raw": alto_raw,
                "Ancho_parsed_mm": w_f,
                "Alto_parsed_mm": h_f,
                "Output_Ancho_mm": w_raw,
                "Output_Largo_mm": h_raw,
                "Output_Grueso_mm": "",
            })
        else:
            if match_type.startswith("ROTATED"):
                output_largo = w_raw
                output_ancho = h_raw
            else:
                output_largo = h_raw
                output_ancho = w_raw

            out_rows.append({
                **base,
                "Codigo_ALVIC": match["ARTICULO"],
                "Match_type": match_type,
                "Color_filter_mode": color_filter_mode,
                "Color_ALVIC_text": color_text or "",
                "Color_ALVIC_code": color_code or "",
                "Input_Ancho_norm": w,
                "Input_Alto_norm": h,
                "DB_Ancho": int(match["Ancho"]) if pd.notna(match["Ancho"]) else "",
                "DB_Alto": int(match["Alto"]) if pd.notna(match["Alto"]) else "",
                "Es_LAC": True,
                "Es_Mecanizada": machined_flag,
                "Mec_reason": machined_reason,
                "Ancho_raw": ancho_raw,
                "Alto_raw": alto_raw,
                "Ancho_parsed_mm": w_f,
                "Alto_parsed_mm": h_f,
                "Output_Ancho_mm": output_ancho,
                "Output_Largo_mm": output_largo,
                "Output_Grueso_mm": match.get("Grueso", ""),
            })

    out = pd.DataFrame(out_rows)
    if out.empty:
        out = pd.DataFrame(columns=[
            *inp.columns.tolist(),
            "Codigo_ALVIC",
            "Match_type",
            "Color_filter_mode",
            "Color_ALVIC_text",
            "Color_ALVIC_code",
            "Input_Ancho_norm",
            "Input_Alto_norm",
            "DB_Ancho",
            "DB_Alto",
            "Es_LAC",
            "Es_Mecanizada",
            "Mec_reason",
            "Ancho_raw",
            "Alto_raw",
            "Ancho_parsed_mm",
            "Alto_parsed_mm",
            "Output_Ancho_mm",
            "Output_Largo_mm",
            "Output_Grueso_mm",
        ])
    out["Output_Ancho_m"] = out["Output_Ancho_mm"].apply(_format_meters)
    out["Output_Largo_m"] = out["Output_Largo_mm"].apply(_format_meters)
    out["Output_Grueso_m"] = out["Output_Grueso_mm"].apply(_format_meters)

    machined = out[out["Es_Mecanizada"] == True].copy().reset_index(drop=True)
    non_machined = out[out["Es_Mecanizada"] == False].copy().reset_index(drop=True)

    def _build_output(df: pd.DataFrame, is_mec: bool) -> pd.DataFrame:
        df = df.copy().reset_index(drop=True)
        out_df = pd.DataFrame()
        project_ids = df[project_id_col].astype(str)
        out_df["referencia"] = [
            build_reference(pid, filename_suffix, is_mec)
            for pid in project_ids
        ]
        out_df["csub"] = "430037779"
        out_df["cordir"] = "1"
        out_df["almacen"] = "7"
        out_df["lin"] = range(1, len(df) + 1)
        out_df["acod"] = df["Codigo_ALVIC"].astype(str)
        out_df["cant"] = "1"
        out_df["alargo"] = df["Output_Largo_m"]
        out_df["aancho"] = df["Output_Ancho_m"]
        out_df["agrueso"] = df["Output_Grueso_m"]
        out_df["nplano"] = ""
        return out_df[OUTPUT_COLUMNS]

    output_machined = _build_output(machined, True)
    output_non_machined = _build_output(non_machined, False)

    output_machined.to_csv(output_machined_csv_path, index=False)
    output_non_machined.to_csv(output_non_machined_csv_path, index=False)

    no_match = out[out["Codigo_ALVIC"] == ""].copy()
    bad_dims = out[out["Match_type"] == "BAD_DIMS"].copy()
    no_match_only = out[out["Match_type"] == "NO_MATCH"].copy()
    summary = {
        "total_lac": int(len(out)),
        "total_mec": int(len(machined)),
        "total_sin_mec": int(len(non_machined)),
        "total_no_match": int(len(no_match_only)),
        "total_bad_dims": int(len(bad_dims)),
    }

    return output_machined, output_non_machined, summary, no_match, out
