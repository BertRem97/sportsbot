import requests
from config import ODDSPAPI_KEY  
from paper_trader import PaperTrader
#from telegram_bot import send_message
from config import *


BASE_URL = "https://api.oddspapi.io"


def get_tournaments(
    language='en',
):

    headers = {
        "X-API-Key": ODDSPAPI_KEY
    }
    
    params = {
              "sportId": "10",
              "language": language,
              "apiKey": ODDSPAPI_KEY
    }

    response = requests.get(
        f"{BASE_URL}/v4/tournaments?",
        params=params,
        headers=headers
    )

    response.raise_for_status()
    data = response.json()

    return data[:20]
    
    
def get_tournament_odds(    
    tournament_ids,
    language='en',
    verbosity=3
):

    headers = {
        "X-API-Key": ODDSPAPI_KEY
    }
    
    params = {"tournamentIds": "15,16,17", #!
              "bookmaker": "unibet.be",
              "language": language,
              "verbosity": verbosity,
              "apiKey": ODDSPAPI_KEY
    }

    response = requests.get(
        f"{BASE_URL}/v4/odds-by-tournaments?",
        params=params,
        headers=headers
    )

    response.raise_for_status()
    data = response.json()
    
    return data
   

def market_consensus(bookmakers):

    odds = []

    for bookie in bookmakers:

        for outcome in bookie["outcomes"]:
            odds.append(outcome["price"])

    return sum(odds) / len(odds)


def is_value_bet(
    bookmaker_odd,
    consensus,
    threshold=0.03
):

    edge = (
        bookmaker_odd -
        consensus
    ) / consensus

    return edge > threshold
    

def kelly_fraction(
    odds,
    probability
):

    b = odds - 1

    return (
        odds * probability - 1
    ) / b
    

def kelly_stake(
    bankroll,
    odds,
    probability,
    fraction=0.25
):

    kelly = kelly_fraction(
        odds,
        probability
    )

    if kelly <= 0:
        return 0

    return bankroll * kelly * fraction










trader = PaperTrader(
    bankroll=STARTING_BANKROLL
)

events = get_tournaments()
tournament_ids = []

for event in events:
    tournament_id = event["tournamentId"]
    tournament_ids.append(tournament_id)

tournament_odds = get_tournament_odds(tournament_ids=tournament_ids)

for tournament in tournament_odds:
	bookmakerOdds = tournament['bookmakerOdds']
	is_active = bookmakerOdds['unibet.be']['bookmakerIsActive']
	markets = bookmakerOdds['unibet.be']['markets']
	
	for market in markets:
		
	
	
	print(list(markets.keys()))

