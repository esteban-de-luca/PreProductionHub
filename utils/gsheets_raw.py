from __future__ import annotations

from typing import Dict

import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SHEETS_READONLY_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"


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
            if getattr(exc.resp, "status", None) == 403:
                raise RuntimeError(
                    "Permiso denegado (403). Comparte los spreadsheets con el email del service account."
                ) from exc
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


def read_sheet_raw(spreadsheet_id: str, sheet_title: str, range_a1: str = "A:Q") -> pd.DataFrame:
    service = get_sheets_service()

    try:
        resp = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_title}!{range_a1}",
                valueRenderOption="UNFORMATTED_VALUE",
            )
            .execute()
        )
    except HttpError as exc:
        if getattr(exc.resp, "status", None) == 403:
            raise RuntimeError(
                "Permiso denegado (403). Comparte este spreadsheet con el email del service account."
            ) from exc
        raise RuntimeError(
            f"No se pudo leer la pestaña '{sheet_title}' en el spreadsheet '{spreadsheet_id}'."
        ) from exc

    values = resp.get("values", []) or []
    if not values:
        return pd.DataFrame()

    return pd.DataFrame(values)
