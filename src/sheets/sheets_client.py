import json
import gspread
from google.oauth2.service_account import Credentials
from src.config import env

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

TIER_HEADERS = {
    "Tier1": ["Date Found", "Firm", "Role Title", "Function", "Location", "JD Link",
              "Referral Contact?", "Status", "Notes"],
    "Tier2": ["Date Found", "Company", "Role Title", "Overall Match %", "P1 Score",
              "P1 Sub-scores (note)", "P2 Score", "Location", "Salary (if disclosed)",
              "JD Link", "ATS Type", "Auto-Apply Status", "Tailored Resume Link", "Status"],
    "Tier3": ["Date Found", "Company", "Funding Round", "Funding Amount", "Funding Source",
              "Sector", "Careers Page Link", "Business-Side Role Listed?", "Founder Name",
              "Founder LinkedIn (unverified)", "Outreach Status", "Notes"],
}


def _client():
    creds_json = json.loads(env("GOOGLE_SERVICE_ACCOUNT_JSON"))
    creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_or_create_worksheet(sheet, tab_name: str):
    try:
        ws = sheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=tab_name, rows=1000, cols=len(TIER_HEADERS[tab_name]) + 2)
        ws.append_row(TIER_HEADERS[tab_name])
        return ws

    if ws.row_values(1) != TIER_HEADERS[tab_name]:
        ws.update("A1", [TIER_HEADERS[tab_name]])
    return ws


def append_row(tab_name: str, row_dict: dict) -> int:
    """row_dict keys should match TIER_HEADERS[tab_name] order-independently; missing keys -> blank.
    Returns the 1-indexed row number the data was written to, so callers (e.g. for attaching
    a cell note) don't need a separate lookup."""
    gc = _client()
    sheet = gc.open_by_key(env("SHEET_ID"))
    ws = _get_or_create_worksheet(sheet, tab_name)

    headers = TIER_HEADERS[tab_name]
    row = [row_dict.get(h, "") for h in headers]
    result = ws.append_row(row, value_input_option="USER_ENTERED")

    updated_range = result["updates"]["updatedRange"]  # e.g. "Tier2!A17:N17"
    row_number = int("".join(filter(str.isdigit, updated_range.split("!")[1].split(":")[0])))
    return row_number


def add_note_to_cell(tab_name: str, row_number: int, column_header: str, note_text: str):
    """Used for the P1 sub-score breakdown, attached as a cell note rather than a column."""
    gc = _client()
    sheet = gc.open_by_key(env("SHEET_ID"))
    ws = sheet.worksheet(tab_name)
    headers = TIER_HEADERS[tab_name]
    col_idx = headers.index(column_header) + 1
    cell = ws.cell(row_number, col_idx)
    ws.update_note(cell.address, note_text)
