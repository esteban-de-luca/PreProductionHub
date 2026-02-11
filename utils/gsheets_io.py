from __future__ import annotations

from typing import Dict, List

import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SHEETS_READONLY_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"

GOOGLE_SHEETS_SOURCES = {
    "Fuente 1": "1WUgFlI1ea4OcWTyFGfJCcEKWBhaHIDj89GiXN02Fr2w",
    "Fuente 2": "1wa2WrV-iujiwxhiL-Q8rKYoPDcPU-eKR3k0Qc9jqxM0",
    "Fuente 3": "1GW8j6Cg__6qX0Tyh9390_XqGKZBBEk5Bvki7SF4PN7k",
    "Fuente 4": "14U-IJz4V787pLAKmKAtBq7T69GVS86GofwaFamAXN5A",
}


def get_sheets_service():
    try:
        service_account_info = st.secrets["gcp_service_account"]
    except Exception as exc:
        raise RuntimeError("Falta gcp_service_account en secrets.") from exc

    try:
        creds = Credentials.from_service_account_info(
            service_account_info,
            scopes=[SHEETS_READONLY_SCOPE],
        )
        return build("sheets", "v4", credentials=creds)
    except Exception as exc:
        raise RuntimeError("No se pudo autenticar con Google Sheets (service account).") from exc


@st.cache_data(ttl=3600)
def build_sheet_index(sources: Dict[str, str]) -> pd.DataFrame:
    service = get_sheets_service()

    rows = []
    for source_name, spreadsheet_id in sources.items():
        try:
            resp = (
                service.spreadsheets()
                .get(
                    spreadsheetId=spreadsheet_id,
                    fields="properties.title,sheets.properties.sheetId,sheets.properties.title",
                )
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(
                f"No se pudo indexar la fuente '{source_name}' ({spreadsheet_id})."
            ) from exc

        spreadsheet_title = resp.get("properties", {}).get("title", "")
        for sheet in resp.get("sheets", []):
            props = sheet.get("properties", {})
            rows.append(
                {
                    "source_name": source_name,
                    "spreadsheet_id": spreadsheet_id,
                    "spreadsheet_title": spreadsheet_title,
                    "sheet_id": props.get("sheetId"),
                    "sheet_title": str(props.get("title", "")).strip(),
                }
            )

    return pd.DataFrame(
        rows,
        columns=[
            "source_name",
            "spreadsheet_id",
            "spreadsheet_title",
            "sheet_id",
            "sheet_title",
        ],
    )


def read_sheet_values(spreadsheet_id: str, sheet_title: str, range_a1: str = "A:Q") -> List[List[str]]:
    service = get_sheets_service()
    sheet_range = f"{sheet_title}!{range_a1}"

    try:
        resp = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=spreadsheet_id,
                range=sheet_range,
                valueRenderOption="UNFORMATTED_VALUE",
            )
            .execute()
        )
    except HttpError as exc:
        raise RuntimeError(
            f"No se pudo leer la pestaña '{sheet_title}' en el spreadsheet '{spreadsheet_id}'."
        ) from exc

    return resp.get("values", []) or []
