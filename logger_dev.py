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
    spreadsheet = client.open_by_key(SHEET_ID)
    worksheet = spreadsheet.get_worksheet(1)
    return worksheet


# ---------------- GOOGLE SHEETS LOG ----------------

def log_to_sheet(bet):
    try:
        fixture_id, market_id = sheet.find(bet['event']["fixture_id"]), sheet.find(bet['event']["market_id"]) 

    except KeyError:
        fixture_id, market_id = 0, 0
    
    next_row = len(sheet.get_all_values()) + 1
     
    event = bet['bet']['event']
    outcomes = bet['bet']['outcomes']
    hedge = bet['bet']['hedge']
    stake = bet['bet']['stake']
    selection = bet['bet']['selection']

    outcomes_iter = iter(outcomes.items())
    outcome, data = next(outcomes_iter)
    outcome_data_1 = f"{outcome if outcome else ""} >> {data['odd']} @ {data['bookmaker']}"
    outcome, data = next(outcomes_iter, (None, None))
    outcome_data_2 = f"{outcome if outcome else ""} >> {data['odd']} @ {data['bookmaker']}" if outcome else ""
    

    try:
        outcome, data = next(outcomes_iter, (None, None))
        outcome_data_3 = f"{outcome if outcome else ""} >> {data['odd']} @ {data['bookmaker']}" if outcome else ""
    except:
        outcome_data_3 = ""

    try:
       event_fixture = event['event_fixture'] 
       market_fixture = event['market_fixture']
       betslip = selection['betslip'] 
    
    except:
        event_fixture = ""
        market_fixture = ""
        betslip = ""

    try:
        secured_profit = "{:.2f}".format(hedge['secured_profit']).replace(".", ",")
    
    except:
        secured_profit = ""

    try:
        possible_profit = "{:.2f}".format(stake['possible_profit']).replace(".", ",")
    except:
        possible_profit = ""
    
    try: 
        hinge_later = f"{str(hedge['bookmaker'])} >> Minimal stake @ {str(hedge['outcome'])}: {str(hedge['min_stake_other_p'])} @ {str(hedge['min_odd_other_p'])}" 
    except:
        hinge_later = ""


    row = [
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            event['start_event'],
            event_fixture,
            market_fixture,
            event['teamnames'],
            event['tournament'],
            event['league'],
            outcome_data_1,
            outcome_data_2,
            outcome_data_3,
            hedge['wanting_hedge'],
            secured_profit,
            possible_profit if bet['bet']['type'] == 'valuebet' else "",
            "{:.2f}".format(stake['stake_val']).replace(".", ","),
            hinge_later if bet['bet']['type'] == 'valuebet' else "",
            "{:.2f}".format(stake['total_stakes']).replace(".", ","),
            selection['outcome'],
            "{:.2f}".format(stake['ev']).replace(".", ","),
            betslip

            ]

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
                    value = "WIN"

                elif result == "LOSE":
                    value = "LOSE"

                elif result == "UNDECIDED":
                    value = "UNDECIDED"

                sheet.update_cell(row_idx, settlement_col, value)
                
            except Exception as e:
                print(f"Result van marketid {market_fixture} met eventid {event_fixture} niet kunnen ophalen: {e}")
                sheet.update_cell(row_idx, settlement_col, "Onbekend")


sheet = connect_sheet()
bankroll = float(sheet.acell("U2").value.replace(",","."))

