import requests
import time
from pprint import pprint
from collections import defaultdict
import statistics
from config import ODDSPAPI_KEYS
from config import BOOKMAKERS, USED_BOOKMAKERS
from config import TELEGRAM_TOKEN, CHAT_ID
from config import min_win_chance, min_percentage_ov
from logger import * 
from telegram import InlineKeyboardButton, Bot
from telegram import InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from telegram.ext import (
    Application,
    CallbackQueryHandler
)
import asyncio
import re
import subprocess

decision = None
decision_event = asyncio.Event()

BASE_URL = "https://api.oddspapi.io"
LAST_REQUEST = 0

# -----------------------------
# CONFIG
# -----------------------------

def rotate_ip():

    print("VPN IP roteren...")
    subprocess.run(
        ["bash", "/home/pi/services/sportsbot/rotate_vpn_on_call.sh"],
        check=True
    )

    print("Wachten op verbinding...")

    while True:

        try:

            response = requests.get(
                BASE_URL,
                timeout=5
            )

            # server antwoordt = internet terug
            if response.status_code < 500:

                print("Verbinding hersteld!")
                return True

        except requests.exceptions.RequestException:

            pass

        time.sleep(2)

    
def get_next_key():

    global CURRENT_KEY

    key = ODDSPAPI_KEYS[CURRENT_KEY]

    CURRENT_KEY = (
        CURRENT_KEY + 1
    ) % len(ODDSPAPI_KEYS)

    return key

def get_settlements(fixtureid):
    params = {
        "fixtureId": fixtureid,
    }
    
    return api_get(
        "/v4/settlements",
        params
    )


def get_available_tournaments(
        tournaments,
        bookmaker="unibet.be"
):

    AVAILABLE_TOURNAMENTS = defaultdict(list)

    tournament_ids = [
        t["tournamentId"]
        for t in tournaments]


    for i in range(0, len(tournament_ids), 5):

        batch = tournament_ids[i:i+5]

        try:
            fixtures = get_odds_by_tournaments(
                batch,
                bookmaker,
            
            )

            for fixture in fixtures:
                found_ids = {
                    fixture["tournamentId"]
                    }
                
                for tournament in tournaments:

                    if tournament["tournamentId"] in found_ids:
                        AVAILABLE_TOURNAMENTS[fixture["tournamentId"]].append(fixture)
          

        except requests.exceptions.HTTPError as e:

            print(f"Batch {batch} overgeslagen: {e}")
            continue


    return AVAILABLE_TOURNAMENTS

# -----------------------------
# API
# -----------------------------

def api_get(endpoint, params):

    global LAST_REQUEST
    elapsed = time.time() - LAST_REQUEST

    if elapsed < 1:
        time.sleep(1 - elapsed)

    params["apiKey"] = get_next_key()

    response = requests.get(
        BASE_URL + endpoint,
        params=params
    )


    LAST_REQUEST = time.time()

    if response.status_code == 403:

        print("403 ontvangen -> IP rotatie")

        if rotate_ip():
            # opnieuw proberen met nieuwe IP
            response = requests.get(
                BASE_URL + endpoint,
                params=params
            )
            print(response)
            return response

    response.raise_for_status()

    return response.json()

# -----------------------------
# TOURNAMENTS
# -----------------------------

def get_tournaments(sport_id=10):

    params = {
        "sportId": sport_id,
    }

    return api_get(
        "/v4/tournaments",
        params
    )


def get_odds_by_tournaments(
        tournament_ids,
        bookmaker,
):
    
    # maakt van enkelvoudige ID een lijst
    if isinstance(tournament_ids, int):
        tournament_ids = [tournament_ids]

    params = {

        "bookmaker": bookmaker,

        "tournamentIds": ",".join(
            map(str, tournament_ids)
        ),

        "language": "en",

        "verbosity": 3,

    }

    return api_get(
        "/v4/odds-by-tournaments",
        params
    )


# -----------------------------
# FIXTURE ODDS
# -----------------------------

ODDS_CACHE = {}
def get_fixture_odds(fixture_id,bookmaker):
    
    key = (fixture_id, bookmaker)

    if key in ODDS_CACHE:
        return ODDS_CACHE[key]
        
    params = {

        "fixtureId": fixture_id,

        "bookmaker": bookmaker,

        "language": "en",

        "verbosity": 3,
    }
    
    data = api_get(
        "/v4/odds",
        params)
    
    ODDS_CACHE[key] = data
  
    return data

# -----------------------------
# MARKET VERGELIJKING
# -----------------------------

def compare_bookmakers_for_fixture(fixture):

    fixture_id = fixture["fixtureId"]


    market_map = defaultdict(dict)

    for bookmaker in BOOKMAKERS:
        try:
            
            data = get_fixture_odds(
                fixture_id,
                bookmaker,
            )

            markets = (
                data["bookmakerOdds"]
                [bookmaker]
                ["markets"]
            )


            for market_id, market in markets.items():
                market_map[market_id][bookmaker] = market
            
        except Exception as e:
            print(bookmaker, e)

    return market_map


# -----------------------------
# ANALYSE ODDS
# -----------------------------

def analyse_market_data(market_map):

    results = defaultdict(list)
    for market_id, bookmakers in market_map.items():

        # market moet bij alle bookmakers bestaan
        if set(bookmakers.keys()) != set(BOOKMAKERS):

            continue

        outcome_prices = defaultdict(list)

        # odds verzamelen per outcome
        for bookmaker, market in bookmakers.items():
            for outcome_id, outcome in market["outcomes"].items():
                player = outcome["players"]["0"]

                outcome_prices[outcome_id].append({

                    "bookmaker": bookmaker,

                    "price": player["price"],

                    "betslip": player["betslip"],
                    
                    "market_outcome": player["bookmakerOutcomeId"]

                })


        # elke outcome controleren
        for outcome_id, prices in outcome_prices.items():
            available_books = {

                x["bookmaker"]
                for x in prices

            }

            # -------------------------
            # TRUE KANS
            # -------------------------

            if available_books != set(BOOKMAKERS):

                continue

            probs = [1 / x["price"] for x in prices]
            median_prob = statistics.median(probs)

            avg_chance_win = median_prob

            # -------------------------
            # BESTE SPEELBARE ODD
            # -------------------------


            playable = [

                x for x in prices

                if x["bookmaker"]
                in USED_BOOKMAKERS

            ]

            playable_books = {

                x["bookmaker"]
                for x in playable

            }

            # enkel als alle speelbookies bestaan
            if playable_books != set(USED_BOOKMAKERS):
                continue


            best = max(
                playable,
                key=lambda x:x["price"]
            )


            results[market_id].append({

                "outcome_id": outcome_id,

                "bookmaker": best["bookmaker"],

                "betslip": best["betslip"],

                "price": best["price"],

                "max_odds": best["price"],

                "avg_chance_win": avg_chance_win,

                "all_prices": prices

            })


    return results


async def handle_button(update, context):

    global decision

    query = update.callback_query

    await query.answer()

    if query.data == "bet_yes":

        decision = True

        await query.message.reply_text(
            "✅ Bet bevestigd"
        )

    elif query.data == "bet_no":

        decision = False

        await query.message.reply_text(
            "❌ Bet geweigerd"
        )

    decision_event.set()

# -----------------------------
# MAIN
# -----------------------------
bot = Bot(token=TELEGRAM_TOKEN)
application = (Application.builder().token(TELEGRAM_TOKEN).build())

CURRENT_KEY = 0
async def main():
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
        
        settlements = get_settlements(fixtureid=event_fixture)
    
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

    tournaments = get_tournaments()[:100]

    print(
        f"{len(tournaments)} competities gevonden"
    )
   
    available = get_available_tournaments(
        tournaments,
        BOOKMAKERS[0]
    )

    print(f"{len(available)} Beschikbare competities bij {BOOKMAKERS[0]}\n")

    for k,v in available.items():
        for fixture in v:

            print(fixture["tournamentId"],"-",fixture["categoryName"],
                "-",fixture["tournamentName"]
            )
        
            print(
                "Aantal wedstrijden:",
                len(available)
            )

           
            teamnames = f"{fixture['participant1Name']} - {fixture['participant2Name']}"
            league = fixture["statusName"]
            tournament = fixture["tournamentSlug"]
            land = fixture["categoryName"]
            fixtureid = fixture["fixtureId"]

            print(
                "\n",
                fixture["participant1Name"],
                "-",
                fixture["participant2Name"]
            )


            market_map = compare_bookmakers_for_fixture(
                fixture
            )


            results = analyse_market_data(
                market_map
            )


            for markets, data in results.items():
                for outcomes in data:
                    implied_odd = float(1 / outcomes["max_odds"])
                    avg_chance_win = outcomes["avg_chance_win"]
                    bookmaker = outcomes["bookmaker"]

                    other_odds = {x["bookmaker"]: x["price"] for x in outcomes["all_prices"] if x['bookmaker'] != outcomes["bookmaker"]}
                    odds_text = "\n".join(
                        f"{bookmaker} @ {price}"
                        for bookmaker, price in other_odds.items()
)
                    betslip = next(
                        (
                            i["betslip"]
                            for i in outcomes["all_prices"]
                            if i["bookmaker"] == "bwin.be"
                        ),
                        None,
)
                    max_odd = outcomes["max_odds"]
                    win_chance = avg_chance_win * 100

                    if (avg_chance_win / (1 / max_odd) - 1) * 100 >= min_percentage_ov:
                        ov = float(max_odd / (1 / avg_chance_win) - 1) * 100
                        if win_chance >= min_win_chance:
                            stakes, ev, payout = calculate_ev_stakes_wkelly(odd=max_odd, p=win_chance)
                            stake_bet = round(stakes['stake_val'], 2)
                            payout = round(payout, 2)
                            net_profit = payout - stake_bet

                            ev = round(ev, 2)
                            if ev > 0:
                                msg = f"""========VALUE BET=========
    {teamnames}
    League: {league}
    Tournament: {tournament}
    EV: {ev}%
    Stake: €{stake_bet}
    Possible Profit: €{payout}
    Waarschijnlijkheid: {win_chance:.2f}%
    Overwaarde: {ov:.2f}%
    Betslip: {betslip}
    Bookmaker: {bookmaker} @ {max_odd}
    -----------------------------------
    {odds_text}
    
    Deze bet loggen?
    """
                                print(msg)

                                bet = {
                                    "odd": max_odd,
                                    "ev": ev,
                                    "market_id": markets,
                                    "stake_val": stake_bet,
                                    "hinge": False,
                                    "net_profit": net_profit,
                                    "stake_val_bet": stakes["stake_val"],
                                    "total_stake": stakes["stake_val"],
                                    "min_odd_other_p": None,
                                    "min_stake_other_p": None,
                                    "other_p": None,
                                    "teamnames": teamnames,
                                    "fixture_id": fixtureid,
                                    "land": land,
                                    "tournament": tournament,
                                    "league": league,
                                    "betslip": betslip
                                    } 
                                
                                print('-------------------------')
                                pprint(outcomes)
                                
                                keyboard = [
                                    [
                                        InlineKeyboardButton(
                                            "✅ Ja",
                                            callback_data=f"bet_yes"
                                        ),
                                        InlineKeyboardButton(
                                            "❌ Nee",
                                            callback_data=f"bet_no"
                                        )
                                    ]
                                ]

                                reply_markup = InlineKeyboardMarkup(keyboard)

                                global decision

                                decision = None
                                decision_event.clear()


                                await bot.send_message(
                                    chat_id=CHAT_ID,
                                    text=msg,
                                    reply_markup=reply_markup
                                )


                                await decision_event.wait()
                                if decision:
                                    if log_to_sheet(bet=bet):
                                        print("✔ Opgeslagen in Google Sheets")
                                    else:
                                        print("Fout tijdens het loggen")
                                
                                else:
                                    continue

async def run():

    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )


    application.add_handler(
        CallbackQueryHandler(
            handle_button
        )
    )


    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    await main()

    await application.updater.stop()
    await application.stop()
    await application.shutdown()


if __name__ == "__main__":
    asyncio.run(run())
    

    
    

                      
                        
       
                        


                       



