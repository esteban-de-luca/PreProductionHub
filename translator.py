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

def detect_is_machined(row: pd.Series) -> bool:
    col = "Mecanizado o sin mecanizar (vacío)"
    if col not in row.index:
        return False
    return not _is_empty_value(row[col])


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

    fit = db[(db["Ancho"] >= w) & (db["Alto"] >= h)].copy()
    if not fit.empty:
        fit["area"] = fit["Ancho"] * fit["Alto"]
        fit = fit.sort_values(["area", "Alto", "Ancho"])
        return fit.iloc[0], "FIT"

    rfit = db[(db["Ancho"] >= h) & (db["Alto"] >= w)].copy()
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

def translate_and_split(
    input_csv_path: str,
    db_csv_path: str,
    output_machined_csv_path: str,
    output_non_machined_csv_path: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:

    db = load_alvic_db(db_csv_path)
    inp = load_input_csv(input_csv_path)

    required_cols = ["Ancho", "Alto", "Acabado"]
    missing = [c for c in required_cols if c not in inp.columns]
    if missing:
        raise ValueError(f"Faltan columnas obligatorias en input: {missing}. Disponibles: {inp.columns.tolist()}")

    out_rows: List[dict] = []

    for _, row in inp.iterrows():
        base = row.to_dict()

        is_lac = detect_is_lac(row)
        is_machined = detect_is_machined(row)

        # No laca: no traducimos
        if not is_lac:
            out_rows.append({
                **base,
                "Codigo_ALVIC": "",
                "Match_type": "",
                "Color_filter_mode": "",
                "Color_ALVIC_text": "",
                "Color_ALVIC_code": "",
                "Input_Ancho_norm": "",
                "Input_Alto_norm": "",
                "DB_Ancho": "",
                "DB_Alto": "",
                "Es_LAC": False,
                "Es_Mecanizada": is_machined,
            })
            continue

        # Normaliza dimensiones y aplica mínimo 100mm
        try:
            w_raw = int(float(row["Ancho"]))
            h_raw = int(float(row["Alto"]))
            w = clamp_min_100(w_raw)
            h = clamp_min_100(h_raw)
        except Exception:
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
                "Es_Mecanizada": is_machined,
            })
            continue

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
                "Es_Mecanizada": is_machined,
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
                "Es_Mecanizada": is_machined,
            })
        else:
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
                "Es_Mecanizada": is_machined,
            })

    out = pd.DataFrame(out_rows)

    machined = out[out["Es_Mecanizada"] == True].copy()
    non_machined = out[out["Es_Mecanizada"] == False].copy()

    machined.to_csv(output_machined_csv_path, index=False)
    non_machined.to_csv(output_non_machined_csv_path, index=False)

    return machined, non_machined

