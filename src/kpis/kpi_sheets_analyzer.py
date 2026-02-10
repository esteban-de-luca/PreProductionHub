from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, List, Any
import re

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials


# =========================
# Config
# =========================

@dataclass(frozen=True)
class KPIConfig:
    spreadsheet_id: str
    gid_2024: int
    gid_2025: int
    gid_2026: int


DEFAULT_MODEL_MAP = {
    # Ajusta según tu convención real
    "--": "INC",
    "INC": "INC",
    "-": "DIY",  # si en tu sheet "-" significa FS, cámbialo aquí o en la UI
    "DIY": "DIY",
    "FS": "FS",
    "F/S": "FS",
}


# =========================
# Google Sheets client
# =========================

def build_gspread_client(*, service_account_info: dict) -> gspread.Client:
    """
    Crea cliente gspread usando credenciales en st.secrets (Service Account).
    """
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    return gspread.authorize(creds)


def worksheet_by_gid(gc: gspread.Client, spreadsheet_id: str, gid: int) -> gspread.Worksheet:
    sh = gc.open_by_key(spreadsheet_id)
    for ws in sh.worksheets():
        if ws.id == gid:
            return ws
    raise ValueError(f"No encontré worksheet con gid={gid}. Revisa el config o el link.")


def fetch_year_dataframe(
    gc: gspread.Client,
    spreadsheet_id: str,
    gid: int,
    year: int,
    *,
    header_row: int = 4,      # 1-based
    data_start_row: int = 5,  # 1-based
) -> pd.DataFrame:
    """
    Lee una worksheet por GID, usando headers en fila 4 y datos desde fila 5.
    Devuelve DataFrame con columnas por nombre y una columna '__year__'.
    """
    ws = worksheet_by_gid(gc, spreadsheet_id, gid)

    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()

    header_idx = header_row - 1
    data_idx = data_start_row - 1

    if len(values) <= header_idx:
        raise ValueError(f"La hoja no llega a la fila {header_row} (headers).")

    headers = values[header_idx]
    data = values[data_idx:] if len(values) > data_idx else []

    df = pd.DataFrame(data, columns=headers)
    df["__year__"] = year

    # Eliminar filas totalmente vacías (tolerante)
    if not df.empty:
        df = df.dropna(how="all")
        df = df.loc[~(df.astype(str).apply(lambda r: "".join(r).strip() == "", axis=1))]

    return df


# =========================
# Parsers / Cleaners
# =========================

def parse_int_safe(x: Any) -> Optional[int]:
    if x is None:
        return None
    s = str(x).strip()
    if s == "":
        return None
    s = s.replace("'", "")
    s = s.replace(",", ".")
    m = re.search(r"-?\d+(\.\d+)?", s)
    if not m:
        return None
    try:
        return int(float(m.group(0)))
    except ValueError:
        return None


def parse_float_minutes(x: Any) -> Optional[float]:
    """
    Convierte valores de tiempo a minutos.
    Soporta:
    - "48,6" (min)
    - "48.6"
    - "01:12" (hh:mm) o "01:12:30"
    - "72" (min)
    - strings con texto (extrae el primer número)
    """
    if x is None:
        return None
    s = str(x).strip()
    if s == "":
        return None

    s = s.replace("'", "").strip()

    # hh:mm(:ss)
    if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", s):
        parts = s.split(":")
        if len(parts) == 2:
            h, m = parts
            return int(h) * 60 + int(m)
        if len(parts) == 3:
            h, m, sec = parts
            return int(h) * 60 + int(m) + (int(sec) / 60.0)

    s2 = s.replace(",", ".")
    m = re.search(r"-?\d+(\.\d+)?", s2)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def normalize_model(x: Any, model_map: Dict[str, str]) -> str:
    s = ("" if x is None else str(x)).strip().upper()
    if s == "":
        return "UNKNOWN"
    return model_map.get(s, s)


def is_complex(comment: Any) -> bool:
    if comment is None:
        return False
    return str(comment).strip() != ""


# =========================
# Tidy + KPIs
# =========================

def prepare_tidy_df(raw_df: pd.DataFrame, model_map: Dict[str, str]) -> pd.DataFrame:
    """
    Convierte el DF crudo en un DF 'tidy' estandarizado:
    week, project_id, owner, comment, is_complex, time_min, boards, model, __year__
    """
    if raw_df.empty:
        return raw_df

    df = raw_df.copy()

    def pick_col(possible_names: List[str]) -> str:
        cols = {str(c).strip().lower(): c for c in df.columns}
        for name in possible_names:
            key = name.strip().lower()
            if key in cols:
                return cols[key]
        raise ValueError(
            f"No encuentro ninguna de estas columnas: {possible_names}. "
            f"Columnas disponibles: {list(df.columns)}"
        )

    # ✅ Ajusta estos nombres si tus headers son distintos (fila 4)
    col_week = pick_col(["Semana", "Week", "SEMANA"])
    col_project = pick_col(["ID de proyecto", "Proyecto", "ID Proyecto", "Project ID"])
    col_owner = pick_col(["Responsable", "Owner", "Responsable / Owner"])
    col_comment = pick_col(["Comentario", "Comentarios", "Comment", "Observaciones"])
    col_time = pick_col(["Tiempo", "Tiempo (min)", "Time", "Duración", "Duracion"])
    col_boards = pick_col(["Tableros", "Nº tableros", "N° tableros", "Boards", "Cantidad tableros"])
    col_model = pick_col(["Modelo", "DIY/FS", "Tipo", "Model"])

    df["week"] = df[col_week].apply(parse_int_safe)
    df["project_id"] = df[col_project].astype(str).str.strip()
    df["owner"] = df[col_owner].astype(str).str.strip().replace({"": "UNKNOWN"})
    df["comment"] = df[col_comment].astype(str).fillna("").astype(str)
    df["is_complex"] = df[col_comment].apply(is_complex)

    df["time_min"] = df[col_time].apply(parse_float_minutes)
    df["boards"] = df[col_boards].apply(parse_int_safe)
    df["model"] = df[col_model].apply(lambda v: normalize_model(v, model_map))

    df.loc[df["project_id"].isin(["", "None", "nan"]), "project_id"] = "UNKNOWN"
    df.loc[df["week"].isna(), "week"] = -1

    keep = ["__year__", "week", "project_id", "owner", "comment", "is_complex", "time_min", "boards", "model"]
    return df[keep]


def kpi_summary_tables(tidy: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    if tidy.empty:
        return {
            "overview": pd.DataFrame(),
            "by_project": pd.DataFrame(),
            "by_owner": pd.DataFrame(),
            "by_week": pd.DataFrame(),
            "by_model": pd.DataFrame(),
            "complexity_overview": pd.DataFrame(),
        }

    year_val = int(tidy["__year__"].iloc[0])

    overview = pd.DataFrame([{
        "year": year_val,
        "files_count": int(len(tidy)),
        "unique_projects": int(tidy["project_id"].nunique()),
        "unique_owners": int(tidy["owner"].nunique()),
        "weeks_covered": int(tidy.loc[tidy["week"] >= 1, "week"].nunique()),
        "time_min_total": float(tidy["time_min"].fillna(0).sum()),
        "time_min_avg": float(tidy["time_min"].dropna().mean()) if tidy["time_min"].notna().any() else None,
        "boards_total": int(tidy["boards"].fillna(0).sum()),
        "boards_avg_per_file": float(tidy["boards"].dropna().mean()) if tidy["boards"].notna().any() else None,
        "complex_files": int(tidy["is_complex"].sum()),
        "complex_rate": float(tidy["is_complex"].mean()),
    }])

    by_project = (
        tidy.groupby("project_id", dropna=False)
        .agg(
            files=("project_id", "size"),
            owners=("owner", lambda s: ", ".join(sorted(set(s.dropna().astype(str))))),
            weeks=("week", lambda s: ", ".join(map(str, sorted(set(int(x) for x in s if x is not None))))),
            time_min_total=("time_min", "sum"),
            time_min_avg=("time_min", "mean"),
            boards_total=("boards", "sum"),
            boards_avg=("boards", "mean"),
            complex_files=("is_complex", "sum"),
            complex_rate=("is_complex", "mean"),
            model=("model", lambda s: ", ".join(sorted(set(s.dropna().astype(str))))),
        )
        .reset_index()
        .sort_values(["files", "time_min_total"], ascending=[False, False])
    )

    by_owner = (
        tidy.groupby("owner", dropna=False)
        .agg(
            files=("owner", "size"),
            unique_projects=("project_id", "nunique"),
            time_min_total=("time_min", "sum"),
            time_min_avg=("time_min", "mean"),
            boards_total=("boards", "sum"),
            boards_avg=("boards", "mean"),
            complex_files=("is_complex", "sum"),
            complex_rate=("is_complex", "mean"),
        )
        .reset_index()
        .sort_values(["files", "time_min_total"], ascending=[False, False])
    )

    by_week = (
        tidy.groupby("week", dropna=False)
        .agg(
            files=("week", "size"),
            unique_projects=("project_id", "nunique"),
            time_min_total=("time_min", "sum"),
            time_min_avg=("time_min", "mean"),
            boards_total=("boards", "sum"),
            boards_avg=("boards", "mean"),
            complex_files=("is_complex", "sum"),
            complex_rate=("is_complex", "mean"),
        )
        .reset_index()
        .sort_values("week", ascending=True)
    )

    by_model = (
        tidy.groupby("model", dropna=False)
        .agg(
            files=("model", "size"),
            unique_projects=("project_id", "nunique"),
            time_min_total=("time_min", "sum"),
            time_min_avg=("time_min", "mean"),
            boards_total=("boards", "sum"),
            boards_avg=("boards", "mean"),
            complex_files=("is_complex", "sum"),
            complex_rate=("is_complex", "mean"),
        )
        .reset_index()
        .sort_values(["files", "time_min_total"], ascending=[False, False])
    )

    complexity_overview = (
        tidy.assign(complexity=tidy["is_complex"].map({True: "COMPLEX", False: "NON_COMPLEX"}))
        .groupby("complexity")
        .agg(
            files=("complexity", "size"),
            time_min_total=("time_min", "sum"),
            time_min_avg=("time_min", "mean"),
            boards_total=("boards", "sum"),
            boards_avg=("boards", "mean"),
        )
        .reset_index()
        .sort_values("complexity")
    )

    return {
        "overview": overview,
        "by_project": by_project,
        "by_owner": by_owner,
        "by_week": by_week,
        "by_model": by_model,
        "complexity_overview": complexity_overview,
    }


def run_all_years_from_secrets(
    *,
    service_account_info: dict,
    spreadsheet_id: str,
    gid_2024: int,
    gid_2025: int,
    gid_2026: int,
    header_row: int = 4,
    data_start_row: int = 5,
    model_map: Optional[Dict[str, str]] = None,
) -> Dict[int, Dict[str, pd.DataFrame]]:
    """
    Runner principal para Streamlit (recibe todo desde st.secrets).
    """
    gc = build_gspread_client(service_account_info=service_account_info)

    cfg = KPIConfig(
        spreadsheet_id=spreadsheet_id,
        gid_2024=gid_2024,
        gid_2025=gid_2025,
        gid_2026=gid_2026,
    )

    mm = model_map or DEFAULT_MODEL_MAP

    def run_year(gid: int, year: int) -> Dict[str, pd.DataFrame]:
        raw = fetch_year_dataframe(
            gc,
            cfg.spreadsheet_id,
            gid,
            year,
            header_row=header_row,
            data_start_row=data_start_row,
        )
        tidy = prepare_tidy_df(raw, mm)
        return kpi_summary_tables(tidy)

    return {
        2024: run_year(cfg.gid_2024, 2024),
        2025: run_year(cfg.gid_2025, 2025),
        2026: run_year(cfg.gid_2026, 2026),
    }
