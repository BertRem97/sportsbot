import os
import requests
from dataclasses import dataclass
from dotenv import load_dotenv
import datetime
import json
import csv
import paper_trader

load_dotenv()


# ---------------- TELEGRAM ----------------

def send_telegram(msg: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    requests.post(url, json={
        "chat_id": chat_id,
        "text": msg
    })


# ---------------- KELLY ----------------

def kelly_fraction(odds, p):
    b = odds - 1
    q = 1 - p
    return (b * p - q) / b


def fractional_kelly(bankroll, kelly, fraction=0.25):
    return max(0, bankroll * kelly * fraction)


# ---------------- PROBABILITIES ----------------

def implied_prob(odds):
    return 1 / odds


# ---------------- INITIAL BET (VALUE) ----------------

def initial_bet(bankroll, odds, true_prob, kelly_factor=0.25):
    k = kelly_fraction(odds, true_prob)
    return fractional_kelly(bankroll, k, kelly_factor)


# ---------------- 1X2 HEDGE ----------------

def hedge_1x2(stake_a, odds_a, odds_x, odds_b):
    """
    Hedge A against X and B simultaneously
    """

    payout_a = stake_a * odds_a

    # hedge sizing: match payout
    stake_x = payout_a / odds_x
    stake_b = payout_a / odds_b

    return stake_x, stake_b


# ---------------- EVALUATION ----------------

def evaluate_1x2(stake_a, odds_a, stake_x, odds_x, stake_b, odds_b):

    payout_a = stake_a * odds_a
    payout_x = stake_x * odds_x
    payout_b = stake_b * odds_b

    profit_if_a = payout_a - stake_a - stake_x - stake_b
    profit_if_x = payout_x - stake_a - stake_x - stake_b
    profit_if_b = payout_b - stake_a - stake_x - stake_b

    return {
        "profit_if_a": profit_if_a,
        "profit_if_x": profit_if_x,
        "profit_if_b": profit_if_b,
        "worst_case": min(profit_if_a, profit_if_x, profit_if_b)
    }


# ---------------- STRATEGY ENGINE ----------------

def run_strategy(
    bankroll,
    odds_a,
    odds_x,
    odds_b,
    true_prob_a,
    kelly_factor=0.25,
    hinge=False
):
    stake_a = 0
    stake_x = 0
    stake_b = 0
    result = 0


    if hinge:
        # 1. value bet (A)
        stake_a = initial_bet(bankroll, odds_a, true_prob_a, kelly_factor)

        # 2. hedge positions
        stake_x, stake_b = hedge_1x2(stake_a, odds_a, odds_x, odds_b)

        # 3. evaluate
        result = evaluate_1x2(stake_a, odds_a, stake_x, odds_x, stake_b, odds_b)


    else:
        stake_a = initial_bet(bankroll, odds_a, true_prob_a, kelly_factor)
        result = evaluate_1x2(stake_a, odds_a, stake_x, odds_x, stake_b, odds_b)
        
        
    return {
        "stake_a": stake_a,
        "stake_x": stake_x,
        "stake_b": stake_b,
        "odds": {
            "A": odds_a,
            "X": odds_x,
            "B": odds_b
        },
        "result": result
    }


# ---------------- ALERT ----------------

def notify(data):

    team_names = input('Voer de beide namen in bv (Colombia - Jordanië): ')
    time = datetime.datetime.now()
    land = str(input("Voer het land/ werelddeel in van de match: "))
    league = str(input("Voer de subcategorie (league) in: "))  

    bet = {
            "teamnames": team_names,
            "land": land,
            "league": league,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stake value bet": data['stake_a'],
            "odds value bet": data['odds']['A'],
            "stake tie bet": data['stake_x'],
            "odds tie bet": data['odds']['X'],
            "stake other bet": data['stake_b'],
            "odds other bet": data["odds"]["B"],
            "profit if A, X or B wins": "",
            "profit if value bet won": "",
            "loss if value bet lost": "",
            "bet overvalue": "",
            "hinge": False
        }
    
   
    if ev < 1:
        print(ev)
        msg = f"""
    📊 1X2 HEDGE SYSTEM

    Stake A (value bet): €{data['stake_a']:.2f}
    Stake X (hedge): €{data['stake_x']:.2f}
    Stake B (hedge): €{data['stake_b']:.2f}

    Odds:
    A: {data['odds']['A']}
    X: {data['odds']['X']}
    B: {data['odds']['B']}

    Profit if A wins: €{data['result']['profit_if_a']:.2f}
    Profit if X wins: €{data['result']['profit_if_x']:.2f}
    Profit if B wins: €{data['result']['profit_if_b']:.2f}

    Worst case: €{data['result']['worst_case']:.2f}
    """
  
        if data['result']['worst_case'] > 0:
            #send_telegram(msg)
            print(msg)
            print("Hinge mogelijk!")
            betplaced = input("Wil je deze bet plaatsen (dry mode)? Y/N: ")

            if betplaced == 'Y':
                if dry_mode:
                    bet['hinge'] = True
                    bet["profit if A, X or B wins"] = data['result']['profit_if_a']
                    trader = paper_trader
                    sheet = trader.connect_sheet(sheet_id)
                    trader.log_trade_gsheet(sheet, bet)


    else:

        print("Geen hinge mogelijk, enkel value bet zonder bescherming van verlies")
        betplaced = input("Wil je deze bet alsnog plaatsen (dry mode)? Y/N: ")
        if betplaced == 'Y':
            ov = float(input("Wat is de overwaarde % volgens Oddspedia?: "))
            bet["profit if value bet won"] = data['result']['profit_if_a']
            bet["loss if value bet lost"] = data['stake_a']
            bet["bet overvalue"] = ov
           
            if dry_mode:
                trader = paper_trader
                sheet = trader.connect_sheet(sheet_id)
                trader.log_trade_gsheet(sheet, bet)
      
        

# ---------------- EXAMPLE ----------------

if __name__ == "__main__":
    dry_mode = True
    bankroll = float(input("Bankroll: "))
    sheet_id = "1Q2ALPTkGx8SICor1c4cDjZWI5Ewg_OKugvr0yUNY_WQ"
    kelly_factor = 0.15
    odds_a = float(input("Quotering Value bet: "))
    odds_x = float(input("Quotering Tie bet: "))
    odds_b = float(input("Quotering Other possibility: "))

    true_prob_a = float(input("Gemiddelde quotering (marktconsensus) value bet A: "))
    ev = 1 / odds_a + 1 / odds_x + 1 / odds_b

    data = run_strategy(
            bankroll,
            odds_a,
            odds_x,
            odds_b,
            true_prob_a,
            kelly_factor=0.15,
            hinge=False
        )
    
    if ev < 1:
        notify(data(hinge=True))
        
    else:
        notify(data)
        
