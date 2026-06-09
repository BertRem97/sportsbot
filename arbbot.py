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
    inv = [1 / o for o in odds_list]
    print(inv)
    total = sum(inv)
    true_probs = [i / total for i in inv]

    return true_probs

def hedge_1x2(stake_val, odds, index):
    payout = stake_val * odds[index]
    other_odds = odds[~index]

    return payout / other_odds[0], payout / other_odds[1]

def calculate_stakes_wkelly(bankroll, odds,
                             index, p, fraction=0.5):
    
    implied_odds = odds[index]
   
    p = 1 / p
    b = implied_odds - 1
    q = 1 - p
    f = (b*p - q) / b
   
    if b <= 0:
        return 0
    
    stake_value = bankroll * f * fraction
    stake_x, stake_y = hedge_1x2(stake_value, odds, index)
    
    print(f"overige stakes: ", stake_x, stake_y)
    return stake_value, stake_x, stake_y


def ev_calc(implied_odds_true_probs, idx, stakes[0]):
    implied_odd_val = implied_odds_true_probs

    return (p * (odds - 1)) - (1 - p)


# ---------------- USER INPUT ----------------

def get_market():
    print("\n=== MARKET INPUT ===")

    n = int(input("Aantal outcomes (2 of 3): "))

    teams = []
    odds = []
  
    for i in range(n):
        name = input(f"Naam outcome {i+1}: ")
        odd = float(input(f"Odds {name}: "))
        teams.append(name)
        odds.append(odd)

    league = input("Voer de league in bv WK: ")
    land = input("In welk land vind de wedstrijd plaats?: ")
    value_team = input("\nOp welke outcome heb je VALUE bet? ")
    true_prob = input("Wat is de ware kans dat het team wint?: ")

    return teams, odds, value_team, league, land, true_prob


# ---------------- STRATEGY ----------------

def build_bet(bankroll, teams, odds, value_team, true_prob_val):
    probs = implied_probs(odds)
    idx = teams.index(value_team)
    bet_placed = teams[idx]
    implied_odd_val = odds[idx]

    print(bet_placed)

    stakes = []

    stakes.append(calculate_stakes_wkelly(bankroll, odds, 
                                          idx, true_prob_val))
                              
    
    ev = ev_calc(implied_odd_val, idx, stakes[0])


    return {
        "teams": teams,
        "odds": odds,
        "probs": probs,
        "ev": ev,
        "bet_placed":bet_placed,
        "stakes": stakes,
        "worst_case": min(stakes) * -1  # simplified risk view
    }


# ---------------- GOOGLE SHEETS LOG ----------------

def log_to_sheet(sheet, bet):

    row = [
         datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "-".join(bet["teams"]),
        ", ".join(map(str, bet["odds"])),
        ", ".join([str(round(p, 4)) for p in bet["probs"]]),
        bet["ev"],
        bet["stakes"][bet["value_idx"]],
        ", ".join([str(round(s, 2)) for s in bet["stakes"]])
    ]

    sheet.append_row(row, value_input_option="USER_ENTERED")


# ---------------- MAIN ----------------

def main():

    sheet = connect_sheet()

    bankroll = float(sheet.acell("R2").value.replace(",",""))
    teams, odds, value_team, league, land, true_prob = get_market()

    bet = build_bet(bankroll, teams, odds, value_team, true_prob)

    print("\n=== RESULT ===")
    print("EV:", round(bet["ev"], 4))
    print("Stakes:", bet["stakes"])

    if bet["ev"] > 0:
        print("✔ Value bet gevonden!")

        confirm = input("Log naar Google Sheets? (Y/N): ")

        if confirm.lower() == "y":
            log_to_sheet(sheet, bet)
            print("✔ Opgeslagen in Google Sheets")

    else:
        print("✖ Geen value bet")


if __name__ == "__main__":
    main()