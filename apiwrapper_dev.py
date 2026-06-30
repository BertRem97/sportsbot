
import requests
import time
from pprint import pprint
from collections import defaultdict
from config import ODDSPAPI_KEYS
from config import BOOKMAKERS, USED_BOOKMAKERS
from config import TELEGRAM_TOKEN, CHAT_ID
from logger import * 
from mainv2_dev import *
import subprocess
import asyncio
import subprocess
import requests
import time


BASE_URL = "https://api.oddspapi.io"
LAST_REQUEST = 0
CURRENT_KEY = 0
# -----------------------------
# CONFIG
# -----------------------------


def rotate_ip():
    subprocess.run(
        ["bash", "/home/pi/services/sportsscanner/rotate_vpn_on_call.sh"],
        check=True
    )

    while True:
        try:
            response = requests.get(
                BASE_URL,
                timeout=5
            )
            if response.status_code < 500:  
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

            print(f"Batch {batch} overgeslagen")
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
            response = requests.get(
                BASE_URL + endpoint,
                params=params
            )
            data = response.json()
            print(type(data))
            return data


    while response.status_code == 429:
        for _ in range(10):
            params["apiKey"] = get_next_key()

            response = requests.get(
                BASE_URL + endpoint,
                params=params
            )

    data = response.json()
    response.raise_for_status()

    print(type(data))
    return data

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
