import os
import pandas as pd
from typing import Dict, Tuple, Optional, List

# =========================================================
# CONFIGURACIÓN INPUT (CSV CUBRO)
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

# =========================================================
# COLORES (orden exacto CUBRO → ALVIC)
# =========================================================

CUBRO_COLORS_ORDER = [
    "Blanco", "Negro", "Tinta", "Seda", "Tipo", "Crema", "Humo", "Zafiro",
    "Celeste", "Pino", "Noche", "Marga", "Argil", "Curry", "Roto", "Ave"
]

ALVIC_COLOR_CODES_ORDER = [
    "L3806", "L4596", "L4706", "L5266", "L5276", "L5556", "L5866", "L5906",
    "L6766", "L9146", "L9166", "L9556", "LA056", "LA066", "LA076", "LA086"
]

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

COLOR_CODE_MAP: Dict[str, str] = {
    c.casefold(): code
    for c, code in zip(CUBRO_COLORS_ORDER, ALVIC_COLOR_CODES_ORDER)
}

# =========================================================
# HELPERS
# =========================================================

def _norm_str(x) -> str:
    return str(x).strip()

def _norm_key(x) -> str:
    return _norm_str(x).casefold()

def clamp_min_100(x: int) -> int:
    return 100 if x < 100 else x

# =========================================================
# NORMALIZACIÓN DE COLUMNAS
# =========================================================

def _canonicalize(col: str) -> str:
    s = str(col).strip()
    s = " ".join(s.split())
    return s.casefold()

def _rename_columns_with_synonyms(df: pd.DataFrame) -> pd.DataFrame:
    synonyms = {
        "ancho": ["ancho", "width", "w", "anchura"],
        "alto": ["alto", "height", "h", "altura"],
        "acabado": ["acabado", "color", "finish"],
        "material": ["material", "mat"],
        "gama": ["gama", "serie", "range"],
        "mecanizado o sin mecanizar (vacío)": [
            "mecanizado o sin mecanizar (vacío)",
            "mecanizado",
            "cnc",
            "mecanizada",
        ],
    }

    rename_dict = {}
    for col in df.columns:
        canon = _canonicalize(col)
        for target, keys in synonyms.items():
            if canon in map(_canonicalize, keys):
                if target == "ancho":
                    rename_dict[col] = "Ancho"
                elif target == "alto":
                    rename_dict[col] = "Alto"
                elif target == "acabado":
                    rename_dict[col] = "Acabado"
                elif target == "material":
                    rename_dict[col] = "Material"
                elif target == "gama":
                    rename_dict[col] = "Gama"
                elif target == "mecanizado o sin mecanizar (vacío)":
                    rename_dict[col] = "Mecanizado o sin mecanizar (vacío)"

    if rename_dict:
        df = df.rename(columns=rename_dict)

    df.columns = [str(c).strip() for c in df.columns]
    return df

def load_input_csv(path: str) -> pd.DataFrame:
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

    raise ValueError("El CSV no tiene el formato esperado.")

# =========================================================
# BASE DE DATOS ALVIC
# =========================================================

def load_alvic_db(db_csv_path: str) -> pd.DataFrame:
    if not os.path.exists(db_csv_path):
        raise FileNotFoundError(f"No existe la base ALVIC: {db_csv_path}")

    db = pd.read_csv(db_csv_path)
    db["Modelo"] = db["Modelo"].astype(str).str.upper().str.strip()
    db["Color_raw"] = db["Color"].astype(str).str.upper().str.strip()

    for c in ["Alto", "Ancho"]:
        db[c] = pd.to_numeric(db[c], errors="coerce")

    db = db.dropna(subset=["ARTICULO", "Color_raw", "Alto", "Ancho"])
    db = db[db["Modelo"].str.contains("ZENIT", na=False)]
    return db

# =========================================================
# DETECCIÓN LACA / MECANIZADO
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
    return str(row[col]).strip() != ""

# =========================================================
# MATCHING
# =========================================================

def find_best_match(db: pd.DataFrame, w: int, h: int):
    exact = db[(db["Ancho"] == w) & (db["Alto"] == h)]
    if not exact.empty:
        return exact.iloc[0], "EXACT"

    rotated = db[(db["Ancho"] == h) & (db["Alto"] == w)]
    if not rotated.empty:
        return rotated.iloc[0], "ROTATED_EXACT"

    fit = db[(db["Ancho"] >= w) & (db["Alto"] >= h)]
    if not fit.empty:
        fit = fit.assign(area=fit["Ancho"] * fit["Alto"]).sort_values("area")
        return fit.iloc[0], "FIT"

    rfit = db[(db["Ancho"] >= h) & (db["Alto"] >= w)]
    if not rfit.empty:
        rfit = rfit.assign(area=rfit["Ancho"] * rfit["Alto"]).sort_values("area")
        return rfit.iloc[0], "ROTATED_FIT"

    return None, "NO_MATCH"

# =========================================================
# MOTOR PRINCIPAL
# =========================================================

def translate_and_split(
    input_csv_path: str,
    db_csv_path: str,
    output_machined_csv_path: str,
    output_non_machined_csv_path: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:

    db = load_alvic_db(db_csv_path)
    inp = load_input_csv(input_csv_path)

    out_rows: List[dict] = []

    for _, row in inp.iterrows():
        base = row.to_dict()
        is_lac = detect_is_lac(row)
        is_machined = detect_is_machined(row)

        if not is_lac:
            out_rows.append({**base, "Codigo_ALVIC": "", "Es_Mecanizada": is_machined})
            continue

        w = clamp_min_100(int(float(row["Ancho"])))
        h = clamp_min_100(int(float(row["Alto"])))

        color_key = _norm_key(row["Acabado"])
        color_code = COLOR_CODE_MAP.get(color_key)
        color_text = COLOR_TEXT_MAP.get(color_key)

        if color_code:
            dcol = db[db["Color_raw"] == color_code]
        elif color_text:
            dcol = db[db["Color_raw"] == color_text]
        else:
            dcol = db

        match, match_type = find_best_match(dcol, w, h)

        out_rows.append({
            **base,
            "Codigo_ALVIC": match["ARTICULO"] if match is not None else "",
            "Match_type": match_type,
            "Es_Mecanizada": is_machined,
        })

    out = pd.DataFrame(out_rows)
    machined = out[out["Es_Mecanizada"] == True]
    non_machined = out[out["Es_Mecanizada"] == False]

    machined.to_csv(output_machined_csv_path, index=False)
    non_machined.to_csv(output_non_machined_csv_path, index=False)

    return machined, non_machined
