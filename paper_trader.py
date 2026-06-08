import gspread
from google.oauth2.service_account import Credentials


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def connect_sheet(sheet_id, creds_file="credentials.json"):

    creds = Credentials.from_service_account_file(
        creds_file,
        scopes=SCOPES
    )

    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).sheet1

    return sheet

def log_trade_gsheet(sheet, bet):
    row = [
        bet.get("teamnames"),
        bet.get("land"),
        bet.get("league"),
        bet.get("time"),

        float(bet.get("stake value bet", 0)),
        float(bet.get("odds value bet", 0)),

        float(bet.get("stake tie bet", 0)),
        float(bet.get("odds tie bet", 0)),

        float(bet.get("stake other bet", 0)),
        float(bet.get("odds other bet", 0)),

        float(bet.get("profit if A, X or B wins") or 0),
        float(bet.get("profit if value bet won") or 0),
        float(bet.get("loss if value bet lost") or 0),

        bet.get("bet overvalue"),
        bet.get("hinge")
    ]

    next_row = len(sheet.get_all_values()) + 1

    sheet.update(
        f"A{next_row}:P{next_row}",
        [row]
    )
   

  


    