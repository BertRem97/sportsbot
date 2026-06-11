import requests
from config import ODDSPAPI_KEY
import time
from pprint import pprint


BASE_URL = "https://api.oddspapi.io"
LAST_REQUEST = 0

def extract_market_odds(fixture):

    bookmaker_odds = fixture["bookmakerOdds"]
    data_bookie = bookmaker_odds[BOOKMAKER]
    market = data_bookie["markets"]

    for market_id, market_data in market.items():
        outcomes = market_data["outcomes"]
        market_data = outcomes[market_id]["players"]["0"]

        pprint(market_data)

  
    

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
                    None
                )


                if match and match not in available:
                    available.append(match)

        except requests.exceptions.HTTPError as e:

            print(
                f"Batch {batch} overgeslagen"
            )

            continue


    return available


BOOKMAKER = "bwin.be"


# 1. Alle competities

tournaments = get_tournaments()[:20]

print(
    f"{len(tournaments)} competities gevonden"
)



# 2. Filter enkel competities met bookmaker odds

available = get_available_tournaments(
    tournaments,
    BOOKMAKER
)


print("\nBeschikbare competities:\n")


for t in available:

    print(
        t["tournamentId"],
        "-",
        t["categoryName"],
        "-",
        t["tournamentName"]
    )

# 3. Kies competitie

league_id = int(
    input(
        "\nGeef tournament ID: "
    )
)

# 4. Haal wedstrijden op

fixtures = get_odds_by_tournaments(
    [league_id],
    BOOKMAKER
)

print(
    f"\n{len(fixtures)} wedstrijden gevonden")


for fixture in fixtures[:10]:

    print("\n----------------")

    odds = extract_market_odds(fixture)
    for odd in odds:
        print(odd)