import requests
from config import ODDSPAPI_KEY
import time
from pprint import pprint
from collections import defaultdict


BASE_URL = "https://api.oddspapi.io"
LAST_REQUEST = 0

def compare_bookmakers_for_fixture(fixture):

    fixture_id = fixture["fixtureId"]

    market_map = defaultdict(dict)

    for bookie in BOOKMAKERS:

        params = {
            "fixtureId": fixture_id,
            "bookmaker": bookie,
            "language": "en",
            "verbosity": 3,
            "apiKey": ODDSPAPI_KEY
        }

        try:
            event = api_get("/v4/odds", params)

            markets = event["bookmakerOdds"][bookie]["markets"]

            for market_id, market in markets.items():

                market_map[market_id][bookie] = market

        except Exception as e:
            print(f"{bookie}: {e}")

    return market_map



def extract_market_odds(fixture):

    tournament_id = fixture["fixtureId"]
    dict = defaultdict(list)
    for bookie in BOOKMAKERS:
        params = {
            "fixtureId": tournament_id,
            "bookmaker": bookie,
            "language": "en",
            "verbosity": 3,
            "apiKey": ODDSPAPI_KEY
        }

        event = api_get('/v4/odds', params)
        
        dict[bookie].append(event) 
     
    return dict

def api_get(endpoint, params):

    global LAST_REQUEST

    elapsed = time.time() - LAST_REQUEST

    if elapsed < 1:
        time.sleep(1 - elapsed)


    response = requests.get(
        f"{BASE_URL}{endpoint}",
        params=params
    )

    LAST_REQUEST = time.time()

    if response.status_code != 200:
        print(response.text)

    response.raise_for_status()
    return response.json()


def get_tournaments(sport_id=10):

    params = {
        "sportId": sport_id,
        "apiKey": ODDSPAPI_KEY
    }

    return api_get(
        "/v4/tournaments",
        params
    )


def get_odds_by_tournaments(
        tournament_ids,
        bookmaker="unibet.be"
):

    params = {
        "bookmaker": bookmaker,
        "tournamentIds": ",".join(
            map(str, tournament_ids)
        ),
        "language": "en",
        "verbosity": 3,
        "apiKey": ODDSPAPI_KEY
    }

    return api_get(
        "/v4/odds-by-tournaments",
        params
    )


def get_available_tournaments(
        tournaments,
        bookmaker="unibet.be"
):

    available = []

    ids = [
        t["tournamentId"]
        for t in tournaments
    ]

    for i in range(0, len(ids), 5):

        batch = ids[i:i+5]
        try:
            fixtures = get_odds_by_tournaments(
                batch,
                bookmaker
            )

            for fixture in fixtures:
                tournament_id = fixture["tournamentId"]

                match = next(
                    (
                        t for t in tournaments
                        if t["tournamentId"] == tournament_id
                    ),
                    None)


                if match and match not in available:
                    available.append(match)

        except requests.exceptions.HTTPError as e:

            print(
                f"Batch {batch} overgeslagen")

            continue
    return available

BOOKMAKERS =  ["bwin.be", "unibet.be", "betano", "pinnacle", "bc.game"]
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

league_id = int(
    input("\nGeef tournament ID: ")
    )

fixtures = get_odds_by_tournaments(
    [league_id],
    BOOKMAKERS[0])

print(f"\n{len(fixtures)} wedstrijden gevonden")


for fixture in fixtures[:5]:
    print(
        f"\n{fixture['participant1Name']} - {fixture['participant2Name']}")

    market_map = compare_bookmakers_for_fixture(fixture)
    for market_id, bookmakers in market_map.items():
        if len(list(bookmakers)) == len(BOOKMAKERS):
            print(f"\nMARKET {market_id}")
            for bookie, market in bookmakers.items():
                print(f"  {bookie}")

                for outcome_id, outcome in market["outcomes"].items():
                    player = outcome["players"]["0"]

                    print(
                        f"    outcome={outcome_id}"
                        f" odds={player['price']}"
                        f" betslip={player['betslip']}")
