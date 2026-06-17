import requests
import time
from pprint import pprint
from collections import defaultdict
import statistics
from config import ODDSPAPI_KEYS


BASE_URL = "https://api.oddspapi.io"

LAST_REQUEST = 0



# -----------------------------
# CONFIG
# -----------------------------

BOOKMAKERS = [
    "bwin.be",
    "unibet.be",
    "betano",
    "pinnacle",
    "stake"
]


USED_BOOKMAKERS = [
    "bwin.be",
    "unibet.be",
    "betano"
]


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
        for t in tournaments
    ]


    # API rate limit vermijden
    # batches van 5

    for i in range(0, len(tournament_ids), 5):

        batch = tournament_ids[i:i+5]

        try:

            fixtures = get_odds_by_tournaments(
                batch,
                bookmaker,
            
            )

            found_ids = {

                fixture["tournamentId"]

                for fixture in fixtures

            }

            for tournament in tournaments:


                if tournament["tournamentId"] in found_ids:

                    available.append(
                        tournament
                    )



        except requests.exceptions.HTTPError:


            print(
                f"Batch {batch} overgeslagen"
            )


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

            print(
                bookmaker,
                e
            )


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





# -----------------------------
# MAIN
# -----------------------------


if __name__ == "__main__":

    percentage_ov = 10
    CURRENT_KEY = 0
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
                pprint(outcomes)
                implied_odd = float(1 / outcomes["max_odds"])
                avg_chance_win = outcomes["avg_chance_win"]
                bookmaker = outcomes["bookmaker"]
                betslip = outcomes["betslip"]
                max_odd = outcomes["max_odds"]

                print(implied_odd, percentage_ov, (avg_chance_win / (1 + percentage_ov / 100)))
                if (avg_chance_win / (1 / max_odd) - 1) * 100 >= percentage_ov:
                    print(f"VALUE BET")
                    print(f"Bookmaker: {bookmaker}")
                    print(f"Odds: {max_odd}")
                    print(f"Win chance %: {avg_chance_win * 100}")
                    print(f"Betslip: {betslip}")



