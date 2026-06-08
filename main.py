import requests
from pprint import pprint
from config import ODDSPAPI_KEY, STARTING_BANKROLL
from paper_trader import PaperTrader

BASE_URL = "https://api.oddspapi.io"


# ----------------------------
# TOURNAMENTS
# ----------------------------
def get_tournaments(language="en", limit=18):

    params = {
        "sportId": "10",
        "language": language,
        "apiKey": ODDSPAPI_KEY
    }

    r = requests.get(f"{BASE_URL}/v4/tournaments", params=params, timeout=10)
    r.raise_for_status()

    return r.json()[:limit]


# ----------------------------
# ODDS FETCH
# ----------------------------
def get_tournament_odds(tournament_ids, bookmaker="bwin.be", language="en", verbosity=3):

    if not tournament_ids:
        return []

    params = {
        "tournamentIds": ",".join(map(str, tournament_ids)),
        "bookmaker": bookmaker,
        "language": language,
        "verbosity": verbosity,
        "apiKey": ODDSPAPI_KEY
    }

    r = requests.get(
        f"{BASE_URL}/v4/odds-by-tournaments",
        params=params,
        timeout=15
    )

    if r.status_code in [404, 429]:
        return []

    r.raise_for_status()
    data = r.json()
    print(data)
    
    return data


# ----------------------------
# CHECK BOOKMAKER AVAILABILITY
# (fixture-level check)
# ----------------------------
def tournament_available(tournament_id, bookmaker="bwin.be"):

    params = {
        "tournamentIds": str(tournament_id),
        "bookmaker": bookmaker,
        "language": "en",
        "verbosity": 3,
        "apiKey": ODDSPAPI_KEY
    }

    try:
        r = requests.get(
            f"{BASE_URL}/v4/odds-by-tournaments",
            params=params,
            timeout=10
        )

        if r.status_code in [404, 429]:
            return False

        r.raise_for_status()

        data = r.json()

        if not data:
            return False

        # check per fixture
        for fixture in data:
            if (
                "bookmakerOdds" in fixture and
                bookmaker in fixture["bookmakerOdds"]
            ):
                return True

        return False

    except requests.exceptions.RequestException:
        return False


# ----------------------------
# PAPER TRADER
# ----------------------------
trader = PaperTrader(bankroll=STARTING_BANKROLL)


# ----------------------------
# MAIN PIPELINE
# ----------------------------
def main():

    events = get_tournaments()

    valid_tournament_ids = []

    print("Checking tournament availability...")

    for event in events:

        tournament_id = event["tournamentId"]

        if tournament_available(tournament_id):
            valid_tournament_ids.append(tournament_id)

    print(f"\nValid tournaments: {valid_tournament_ids}\n")

    if not valid_tournament_ids:
        print("Geen tournaments beschikbaar voor deze bookmaker.")
        return

    # fetch odds
    odds = get_tournament_odds(valid_tournament_ids)

    if not odds:
        print("Geen odds data ontvangen.")
        return

    pprint(odds)


if __name__ == "__main__":
    main()


