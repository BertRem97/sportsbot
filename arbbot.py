import gspread
from google.oauth2.service_account import Credentials
import datetime


# ---------------- GOOGLE SHEETS ----------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SHEET_ID = "1Q2ALPTkGx8SICor1c4cDjZWI5Ewg_OKugvr0yUNY_WQ"
CREDS_FILE = "credentials.json"


def connect_sheet():
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1


# ---------------- MATH ----------------

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


def calculate_ev_stakes_wkelly(bankroll, odds,
                             index, p, hinge, fraction=0.5):
    
    implied_odds = odds[index]
    p = p / 100
    b = implied_odds - 1
    q = 1 - p
    f = (b*p - q) / b

    ev = (p * b) - (q * 1)

    if b <= 0:
        return 0
    
    stake_value = bankroll * f * fraction
    payout = stake_value * odds[index]

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

def build_bet(bankroll, outcomes, odds, value_team, true_prob_val):
    hinge = implied_probs(odds)
    idx = outcomes.index(value_team)
    bet_placed = outcomes[idx]

    stakes, ev, payout = calculate_ev_stakes_wkelly(bankroll, odds, 
                                          idx, true_prob_val, hinge)
    

    total_stakes = (lambda x: sum(x))([i for i in stakes.values() if i is not None])
    net_profit = payout - total_stakes
 
    data = {
        "outcomes": outcomes,
        "odds": odds,
        "ev": ev,
        "bet_placed":bet_placed,
        "stakes": stakes,
        "hinge": False,
        "net_profit": net_profit,
        "stake_val_bet": stakes["stake_val"],
        "total_stake": total_stakes,
        "outcome_bet": value_team
        }  

    if hinge:
        data["hinge"] = True


    return data

# ---------------- GOOGLE SHEETS LOG ----------------

def log_to_sheet(sheet, bet, league, land, teams):
    row = [
         datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        teams,
        land,
        league,
        f"{bet['outcomes'][0]} @ {bet['odds'][0]}",
        f"{bet['outcomes'][1]} @ {bet['odds'][1]}", 
        f"{bet['outcomes'][2]} @ {bet['odds'][2]}" if len(bet['outcomes']) == 3 else 0,
        bet["hinge"],
        bet['net_profit'],
        bet["stake_val_bet"],
        bet['total_stake'],
        bet["outcome_bet"],
        bet["ev"]
    ]
       
    next_row = len(sheet.get_all_values()) + 1
    sheet.update(
        f"A{next_row}:P{next_row}",
        [row])


# ---------------- MAIN ----------------

def main():

    sheet = connect_sheet()

    bankroll = float(sheet.acell("O2").value.replace(",","."))
    outcomes, odds, value_team, league, land, true_prob, teams = get_market()

    bet = build_bet(bankroll, outcomes, odds, value_team, true_prob)

    print("\n=== RESULT ===")
    print("EV:", f"{round(bet['ev'], 4)}%")
    print("Stakes:", bet["stakes"])
    print(f"Hinge?: {bet['hinge']}")
    print(f"Possible profit: {bet['net_profit']}")

    if bet["ev"] > 0:
        print("✔ Value bet gevonden!")
        if bet["hinge"]:
            print("Hinge mogelijk ✔")

        confirm = input("Log naar Google Sheets? (Y/N): ")

        if confirm.lower() == "y":
            log_to_sheet(sheet, bet, league, land, teams)
            print("✔ Opgeslagen in Google Sheets")

    else:
        print("✖ Geen value bet")


if __name__ == "__main__":
    main()