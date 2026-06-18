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

decision = None
decision_event = asyncio.Event()

BASE_URL = "https://api.oddspapi.io"
LAST_REQUEST = 0

# -----------------------------
# CONFIG
# -----------------------------

def get_next_key():

    global CURRENT_KEY

    key = ODDSPAPI_KEYS[CURRENT_KEY]

    CURRENT_KEY = (
        CURRENT_KEY + 1
    ) % len(ODDSPAPI_KEYS)

    return key


def get_available_tournaments(
        tournaments,
        bookmaker="unibet.be"
):

    available = []


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

            found_ids = {

                fixture["tournamentId"]
                
                for fixture in fixtures}

            for tournament in tournaments:

                if tournament["tournamentId"] in found_ids:
                    available.append(
                        tournament
                    )

        except requests.exceptions.HTTPError:

            print(f"Batch {batch} overgeslagen")
            continue


    return available

# -----------------------------
# API
# -----------------------------

def api_get(endpoint, params):

    global LAST_REQUEST

    elapsed = time.time() - LAST_REQUEST

    if elapsed < 1:
        time.sleep(1 - elapsed)

    response = requests.get(
        BASE_URL + endpoint,
        params=params
    )

    LAST_REQUEST = time.time()

    if response.status_code != 200:
        print(response.text)

    response.raise_for_status()

    return response.json()

# -----------------------------
# TOURNAMENTS
# -----------------------------

def get_tournaments(sport_id=10):

    params = {

        "sportId": sport_id,
        "apiKey": get_next_key()

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

        "apiKey": get_next_key()
    }

    return api_get(
        "/v4/odds-by-tournaments",
        params
    )


# -----------------------------
# FIXTURE ODDS
# -----------------------------

def get_fixture_odds(
        fixture_id,
        bookmaker,
):

    params = {

        "fixtureId": fixture_id,

        "bookmaker": bookmaker,

        "language": "en",

        "verbosity": 3,

        "apiKey": get_next_key()

    }


    return api_get(
        "/v4/odds",
        params
    )

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

                    "betslip": player["betslip"]

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


def handle_button(update, context):

    global decision

    query = update.callback_query

    query.answer()

    if query.data == "bet_yes":

        decision = True

        query.edit_message_text(
            "✅ Bet bevestigd"
        )

    elif query.data == "bet_no":

        decision = False

        query.edit_message_text(
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
    tournaments = get_tournaments()[:20]

    print(
        f"{len(tournaments)} competities gevonden"
    )

    available = get_available_tournaments(
        tournaments,
        BOOKMAKERS[0]
    )

    print("\nBeschikbare competities:\n")

    for t in available:

        print(t["tournamentId"],"-",t["categoryName"],
            "-",t["tournamentName"]
        )

    tournament_id = int(
        input("\nGeef tournament ID: ")
        )



    fixtures = get_odds_by_tournaments(
        tournament_id,
        BOOKMAKERS[0],
    )


    print(
        "Aantal wedstrijden:",
        len(fixtures)
    )


    for fixture in fixtures:
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
                betslip = outcomes["all_prices"][0]["betslip"]
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
Bookmaker: {bookmaker}
Quotering: {max_odd}
Waarschijnlijkheid: {win_chance:.2f}%
Overwaarde: {ov:.2f}%
Betslip: {betslip}

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
                            print(outcomes)
                            
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
                                log_to_sheet(bet=bet)
                                print("✔ Opgeslagen in Google Sheets")
                            
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
    

    
    

                      
                        
       
                        


                       



