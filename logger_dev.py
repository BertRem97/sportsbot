import gspread
from google.oauth2.service_account import Credentials
import datetime
from config import SHEET_ID, CREDS_FILE
from config import EDGE_THRESHOLD, KELLY_FRACTION
from collections import defaultdict
import re
import apiwrapper_dev as api

# ---------------- GOOGLE SHEETS ----------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


def connect_sheet():
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1


# ---------------- GOOGLE SHEETS LOG ----------------

def log_to_sheet(bet=None, league=None, land=None, teams=None, manual_input=False):
    next_row = len(sheet.get_all_values()) + 1
    
    if manual_input:
        row = [
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            teams,
            land,
            league,
            f"{bet['outcomes'][0]} @ {bet['odds'][0]}",
            f"{bet['outcomes'][1]} @ {bet['odds'][1]}", 
            f"{bet['outcomes'][2]} @ {bet['odds'][2]}" if len(bet['outcomes']) == 3 else "",
            bet["hinge"],
            "{:.2f}".format(bet['net_profit']).replace(".", ",") if bet['hinge'] else "",
            "{:.2f}".format(bet['net_profit']).replace(".", ",") if not bet['hinge'] else "",
            "{:.2f}".format(bet['stake_val_bet']).replace(".", ","),
            f"{bet['other_p']} @ {bet['min_odd_other_p']} >> {bet['min_stake_other_p']}" 
            if bet['min_odd_other_p'] else "",
            "{:.2f}".format(bet['total_stake']).replace(".", ","),
            bet['bet_placed'],
            "{:.2f}".format(bet["ev"]).replace(".", ","),
        ]
        
        return True

    elif not manual_input:
        row = [
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            bet["teamnames"],
            bet["land"],
            bet["league"],
            bet["odd"],
            "",
            "",
            False,
            "",
            bet["net_profit"],
            bet["stake_val"],
            "",
            bet["stake_val"],
            "",
            bet["ev"],
            bet["fixture_id"],
            bet["market_id"],
            bet["betslip"]

        ]
   
        fixture_id, market_id = sheet.find(bet["fixture_id"]), sheet.find(bet["market_id"])
        print(fixture_id, market_id)
        
        if not (fixture_id and market_id):
            sheet.update(
                f"A{next_row}:S{next_row}",
                [row])
                
            return True
        

def get_settlements():
    rows = sheet.get_all_values()
    pairs = []
    settlement_col = 19

    fixture_pattern = r"^id\d+$"
    market_pattern = r"^\d+$"

    for row_index, row in enumerate(rows, start=1):

        if len(row) < 2:
            continue

        event_fixture = row[15].strip()
        market_fixture = row[16].strip()

        if (
            re.match(fixture_pattern, event_fixture)
            and
            re.match(market_pattern, market_fixture)
        ):  
            if not sheet.cell(row_index, settlement_col).value != "Ja" or "Nee":
                pairs.append(
                    (
                        event_fixture,
                        market_fixture,
                        row_index
                    )
                )

    grouped = defaultdict(list)

    for event_fixture, market_fixture, row_idx in pairs:
        grouped[event_fixture].append(
            (market_fixture, row_idx)
        )

    for event_fixture, markets in grouped.items():
        
        settlements = api.get_settlements(fixtureid=event_fixture)

        for market_fixture, row_idx in markets:
            market_fixture = str(market_fixture).strip().lstrip("'")
            
            try:
                result = settlements["markets"][market_fixture]["outcomes"][market_fixture]['players']["0"]["result"]
                
                
                if result == "WIN":
                    value = "Ja"

                elif result == "LOSE":
                    value = "Nee"

                elif result == "UNDECIDED":
                    value = "Onbepaald"

                sheet.update_cell(row_idx, settlement_col, value)
                
            except Exception as e:
                print(f"Result van marketid {market_fixture} met eventid {event_fixture} niet kunnen ophalen: {e}")
                sheet.update_cell(row_idx, settlement_col, "Onbekend")


sheet = connect_sheet()
bankroll = float(sheet.acell("T2").value.replace(",","."))

