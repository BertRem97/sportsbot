import gspread
from google.oauth2.service_account import Credentials
import datetime
from config import SHEET_ID, CREDS_FILE
from config import EDGE_THRESHOLD, KELLY_FRACTION

# ---------------- GOOGLE SHEETS ----------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


def connect_sheet():
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1

# ---------------- MATH ----------------

def calculate_hinge_1X2_after(odd_val, stake_val):
    total_implied_odds = 0.99
    chance_val = 1 / odd_val

    min_odd_other_p = 1 / (total_implied_odds - chance_val)
    payout = stake_val * odd_val

    stake_other_p = payout / min_odd_other_p
    return round(min_odd_other_p, 2), round(stake_other_p, 2)

def implied_probs(odds_list):
    """Convert odds → normalized true probabilities"""
    hinge = False
    inv = [1 / o for o in odds_list]
    total = sum(inv)
    true_probs = [i / total for i in inv]

    if total < 1:
        hinge = True

    return hinge

def hedge(stake_val, odds, index):
    payout = stake_val * odds[index]
    other_odds = [odd for i, odd in enumerate(odds) if i != index]

    if len(other_odds) > 1:
        return payout / other_odds[0], payout / other_odds[1], payout
    
    else:
        return payout / other_odds[0], None, payout


def calculate_ev_stakes_wkelly(odds=None,
                             index=None, p=None, hinge=False, odd= None,
                             fraction=KELLY_FRACTION):
    
    implied_odds = None
    if odds:
        implied_odds = odds[index]

    else:
        if odd:
            implied_odds = odd

    p = p / 100
    b = implied_odds - 1
    q = 1 - p
    f = (b*p - q) / b

    ev = (p * b) - (q * 1)
    print(f"EV {ev}")
    

    if b <= 0:
        return 0
    
    stake_value = bankroll * f * fraction
    payout = stake_value * implied_odds if implied_odds is not None else None

    stakes = {"stake_val": stake_value,
            "stake_x": None,
            "stake_y": None}
           
    if hinge:
        stake_x, stake_y, payout = hedge(stake_value, odds, index)
    
        stakes["stake_x"] = stake_x
        stakes["stake_y"] = stake_y

    return stakes, ev, payout

# ---------------- USER INPUT ----------------

def get_market():
    print("\n=== MARKET INPUT ===")

    n = int(input("Aantal outcomes (2 of 3): "))

    outcomes = []
    odds = []
    teams = input("Voer teamnames in met '-' bv Belgie - Afrika: ")
    league = input("Voer de league in bv WK: ")
    land = input("In welk land vind de wedstrijd plaats?: ")
    value_team = input("\nOp welke outcome heb je VALUE bet? ")
    true_prob = float(input("Wat is de ware kans dat het team wint bv'%30 ?: "))

    for i in range(n):
        name = input(f"Naam outcome {i+1}: ")
        odd = float(input(f"Odds {name}: "))
        outcomes.append(name)
        odds.append(odd)
    
    return outcomes, odds, value_team, league, land, true_prob, teams


# ---------------- STRATEGY ----------------

def build_bet(outcomes, odds, value_team, true_prob_val):
    hinge = implied_probs(odds)
    idx = outcomes.index(value_team)
    bet_placed = outcomes[idx]
    other_p = [i for i in outcomes if i != value_team]


    stakes, ev, payout = calculate_ev_stakes_wkelly(odds, 
                                          idx, true_prob_val, hinge)
    

    total_stakes = (lambda x: sum(x))([i for i in stakes.values() if i is not None])
    net_profit = payout - total_stakes
 
    data = {
        "outcomes": outcomes,
        "odds": odds,
        "ev": ev,
        "bet_placed": bet_placed,
        "stakes": stakes,
        "hinge": False,
        "net_profit": net_profit,
        "stake_val_bet": stakes["stake_val"],
        "total_stake": total_stakes,
        "outcome_bet": value_team,
        "min_odd_other_p": None,
        "min_stake_other_p": None,
        "other_p": None
        }  

    if hinge:
        data["hinge"] = True
    
    else:
        if len(outcomes) != 3:
            min_odds, min_stake = calculate_hinge_1X2_after(odds[idx], stakes['stake_val'])
            data["min_odd_other_p"] = min_odds
            data["min_stake_other_p"] = min_stake
            data["other_p"] = other_p
            
            payout_other_p = data["min_stake_other_p"]
    return data

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


sheet = connect_sheet()
bankroll = float(sheet.acell("T2").value.replace(".", "").replace(',', "."))
# ---------------- MAIN ----------------

def main():
    outcomes, odds, value_team, league, land, true_prob, teams = get_market()
    bet = build_bet(outcomes, odds, value_team, true_prob)

    print("\n=== RESULT ===")
    print("EV:", f"{round(bet['ev'], 2)}%")
    print("Stakes:", bet["stakes"])
    print(f"Hinge?: {bet['hinge']}")
    print(f"Possible profit: {bet['net_profit']}")

    if bet["ev"] > 0:
        print("✔ Value bet gevonden!")
        if bet["hinge"]:
            print("Hinge mogelijk ✔")

        confirm = input("Log naar Google Sheets? (Y/N): ")

        if confirm.lower() == "y":
            log_to_sheet(bet, league, land, teams, True)
            print("✔ Opgeslagen in Google Sheets")

    else:
        print("✖ Geen value bet")


if __name__ == "__main__":
    main()
