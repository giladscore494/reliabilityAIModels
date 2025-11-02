# -*- coding: utf-8 -*-
"""
Google Sheets integration layer
"""
import pandas as pd
from typing import Optional
import gspread
from google.oauth2.service_account import Credentials

from settings import (
    GOOGLE_SHEET_ID,
    REQUIRED_HEADERS,
    get_service_account_dict
)


_worksheet = None


def connect_sheet():
    """Connect to Google Sheet and ensure headers are correct"""
    global _worksheet
    
    if _worksheet is not None:
        return _worksheet
    
    if not GOOGLE_SHEET_ID:
        raise RuntimeError("GOOGLE_SHEET_ID not configured")
    
    svc_dict = get_service_account_dict()
    if not svc_dict:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON not configured or invalid")
    
    try:
        credentials = Credentials.from_service_account_info(
            svc_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        gc = gspread.authorize(credentials)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        ws = sh.sheet1
        
        # Ensure headers are correct
        current = [c.lower() for c in ws.row_values(1)]
        if current != REQUIRED_HEADERS:
            ws.update("A1", [REQUIRED_HEADERS], value_input_option="USER_ENTERED")
        
        _worksheet = ws
        return ws
    except Exception as e:
        raise RuntimeError(f"Failed to connect to Google Sheets: {repr(e)}")


def sheet_to_df() -> pd.DataFrame:
    """Read Google Sheet into DataFrame"""
    ws = connect_sheet()
    
    try:
        recs = ws.get_all_records()
        df = pd.DataFrame(recs) if recs else pd.DataFrame(columns=REQUIRED_HEADERS)
    except Exception as e:
        # Return empty dataframe on error
        return pd.DataFrame(columns=REQUIRED_HEADERS)
    
    # Ensure all required columns exist
    for h in REQUIRED_HEADERS:
        if h not in df.columns:
            df[h] = ""
    
    return df


def append_row_to_sheet(row_dict: dict):
    """Append a row to the sheet"""
    ws = connect_sheet()
    
    row = [row_dict.get(k, "") for k in REQUIRED_HEADERS]
    
    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        raise RuntimeError(f"Failed to append row to sheet: {repr(e)}")
