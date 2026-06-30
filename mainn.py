from pprint import pprint
from collections import defaultdict
import statistics
from config import BOOKMAKERS, USED_BOOKMAKERS
from config import TELEGRAM_TOKEN, CHAT_ID, KELLY_FRACTION
from config import min_win_chance, min_percentage_ov
import logger_dev as logger
from telegram import InlineKeyboardButton, Bot
from telegram import InlineKeyboardMarkup, ForceReply, Update
from telegram.ext import CallbackQueryHandler, MessageHandler, \
    CommandHandler, filters
from telegram.ext import (
    Application,
    CallbackQueryHandler
)
import asyncio
import apiwrapper_dev as api
import uuid


BASE_URL = "https://api.oddspapi.io"
LAST_REQUEST = 0

# -----------------------------
# CONFIG
# -----------------------------

def calculate_hinge_1X2_after(odd_val, stake_val):
    total_implied_odds = 0.99
    chance_val = 1 / odd_val

    min_odd_other_p = 1 / (total_implied_odds - chance_val)
    payout = stake_val * odd_val

    stake_other_p = payout / min_odd_other_p
    return round(min_odd_other_p, 2), round(stake_other_p, 2)
    

def implied_probs(odds_list):
    """Convert odds → normalized true probabilities"""
    hinge = False
    inv = [1 / o for o in odds_list]
    total = sum(inv)
    true_probs = [i / total for i in inv]

    if total < 1:
        hinge = True

    return hinge

def hedge_stakes(stake_val, odd, other_odds):
    payout = stake_val * odd

    return payout / float(list(map(float, other_odds))[0])


async def calculate(update=None, context=None, bet=None):
    
    data = bet['bet']
    pending = bet['pending']
    is_manual = data['manual']


    value_team = data['selection']["outcome"]
    data['type'] = None
    outcomes = data['outcomes']
    value_odd = float(data["selection"]['odd'])
    bookie_val = data['selection']['bookmaker']
    avg_chance_win = float(data['event']['win_chance'])

    other_odds = []
    odds = []
    hinge = implied_probs(odds) if is_manual else False

    for k, v in outcomes.items():
        outcome = k

        for outcome_data in v:
            bookmaker = outcome_data['bookmaker']
            odd = float(outcome_data['odd'])
            odds.append(odd)

            if outcome != value_team:
                other_odds.append(odd)

    win_chance = float(data['event']["win_chance"]) * 100
    
    p = win_chance / 100
    b = value_odd - 1
    q = 1 - p
    f = (b*p - q) / b

    ev = (p * b) - (q * 1)
    ev = ((p*value_odd)-1)*100

    if b <= 0:
        return 0
    
    if f <= 0:
        return 0
   
    stake_value = logger.bankroll * f * KELLY_FRACTION
    payout = float(stake_value * value_odd)
    net_profit = payout - stake_value

    data['stake']["payout"] = payout
    data['stake']["ev"] = ev
    data['stake']["ov"] = float(value_odd / (1 / win_chance) - 1) * 100
    data['stake']["possible_profit"] = net_profit
    data['stake']['total_stakes'] = stake_value
    data['stake']['stake_val'] = stake_value
    data['selection']['betslip'] = None
    ov = float(value_odd / (1 / win_chance) - 1) * 100 
 
    if is_manual:
        if context.user_data['pending']["awaiting_teams"][1] == 2:
            outcome_hedge = [i for i in data['outcomes'] if i != data['selection']['outcome']]
            for k, v in data['outcomes'].items():
                for i in v:
                    if k != value_team:
                        bookmaker = i['bookmaker']

            if hinge:
                keyboard = [
                    [
                        InlineKeyboardButton(text="Ja", callback_data="hinge_yes"),
                        InlineKeyboardButton(text="Nope", callback_data="hinge_no")
                    ]
                ]

                reply_markup = InlineKeyboardMarkup(keyboard)
        
                stake_x = hedge_stakes(stake_value, value_odd, other_odds)
                total_stakes = stake_value + stake_x
                secured_net_profit = payout - total_stakes
                data['hedge'] = {'odd': other_odds, 'stake': stake_x, 'outcome': str(outcome_hedge),
                                'bookmaker': bookmaker, "secured_profit": secured_net_profit}
                
                data['stake']['total_stakes'] = total_stakes

                pending['hinge_event'].clear()
                await context.bot.send_message(chat_id=CHAT_ID, text="Sure bet mogelijk, wil je hingen?", 
                                    reply_markup=reply_markup)
        
                await pending['hinge_event'].wait()
                decision = pending['decision']

                data['hedge']['wanting_hedge'] = False
                if decision:
                    data['hedge']['wanting_hedge'] = True
                    data['type'] = 'surebet'

                context.user_data['pending']["awaiting_teams"][1] = None

            else:
                min_odds, min_stake = calculate_hinge_1X2_after(value_odd, stake_value)
                data['hedge'] = {"min_odd_other_p": min_odds, "min_stake_other_p": min_stake,
                            'outcome': str(outcome_hedge), 'bookmaker': bookmaker}

    win_chance = avg_chance_win * 100
    ov = float(value_odd / (1 / avg_chance_win) - 1) * 100
    print(f"OVERVALUE: {ov}")
    print(f"EV: {ev}")

    if (avg_chance_win / (1 / value_odd) - 1) * 100 >= min_percentage_ov:
        if win_chance >= min_win_chance:
            if ev > 0:
                print("under_conditions!")
                if data['type'] != 'surebet':
                    data['type'] = "valuebet"

                outcome_lines = "\n".join(
                        f"{x['bookmaker']} @ {x['odd']}"
                        for x in data["outcomes"][None])
                
                prefix = (
                    "========VALUE BET========="
                    if data["type"] == "valuebet"
                    else "========SURE BET=========" if data['type'] == "surebet"
                    else ""
                
                    )
                
                profit = (
                    f"Possible profit: €{data['stake']['possible_profit']:.2f}"
                    if data['type'] == "valuebet" else 
                    f"Secured profit: €{data['hedge']['secured_profit']:.2f}"
                    if data['type'] == "surebet"
                    else "" 
                    )
                        

                msg = f"""

{prefix}

{data["event"]["teamnames"]}

League: {data["event"]["league"]}
Tournament: {data["event"]["tournament"]}

EV: {data["stake"]["ev"]:.2f}%
Probability: {win_chance:.2f}%
Over value: {ov:.2f}%
Stake value bet: €{data["stake"]["stake_val"]:.2f}
{f"Stake hedge bet: €{data['hedge']['stake']:.2f}" if data['type'] == "surebet" else ""} 

Bookmaker:
{bookie_val} @ {data["selection"]["odd"]}
{profit}
------------------------
{outcome_lines if outcome_lines else ""}

{f"Betslip: {data['selection']['betslip']}" 
if data['selection']['betslip'] else ""}

Wil je deze bet loggen?
"""
                print(msg)
                
                ACTIVE_BETS[data['id']] = bet
                if data['type'] != None:
                    keyboard = [
                        [
                            InlineKeyboardButton("✅ Ja",callback_data=f"bet_yes"),
                            InlineKeyboardButton("❌ Nee",callback_data=f"bet_no")
                        ]
                    ]

                    reply_markup = InlineKeyboardMarkup(keyboard)

                    pending['decision_event'].clear()

                    await context.bot.send_message(
                        chat_id=CHAT_ID,
                        text=msg,
                        reply_markup=reply_markup
                    )


                    await pending['decision_event'].wait()
                    decision = pending['decision']

                    if decision:
                        if logger.log_to_sheet(bet=bet):
                            print("✔ Opgeslagen in Google Sheets")
                            ACTIVE_BETS.pop('id')
                        else:
                            print("Fout tijdens het loggen")
                    
                        

async def handle_button(update, context):
    print("HANDLEING BUTTON")
    print(update)

    bet = next(iter(ACTIVE_BETS.values()))
    pending = bet["pending"]
    decision = pending['decision']
    decision_event = pending['decision_event']
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


ACTIVE_BETS = {}
async def handle_tekst_message(update, context):

    text = update.message.text 
    pending = context.user_data['pending']
    if pending.get("awaiting_teams")[0]:
        teams = text
        context.user_data['bet']["event"]["teamnames"] = teams

        await context.bot.send_message(chat_id=CHAT_ID, text="Voer de league in", 
                     reply_markup=ForceReply(selective=True))
        
        pending["awaiting_teams"][0] = False
        pending["awaiting_league"] = True
        
    elif pending.get("awaiting_league"):
        league = text
        context.user_data['bet']["event"]["league"] = league

        await context.bot.send_message(chat_id=CHAT_ID, text="Voer het toernooi of het land in", 
                     reply_markup=ForceReply(selective=True))
        
        pending["awaiting_league"] = False
        pending["awaiting_tournament"] = True


    elif pending.get("awaiting_tournament"):
        land = text
        context.user_data['bet']['event']["tournament"] = land

        await context.bot.send_message(chat_id=CHAT_ID, text="Op welke outcome heb je een value bet?", 
                     reply_markup=ForceReply(selective=True))
        
        pending["awaiting_tournament"] = False
        pending["awaiting_outcome_v"] = True
    
    elif pending.get("awaiting_outcome_v"):
        value_team = text.lower()
        context.user_data['bet']['selection']["outcome"] = value_team

        await context.bot.send_message(chat_id=CHAT_ID, text="Voer de startdatum en tijdstip in volgens format: 07/10/2025 8:00", 
                     reply_markup=ForceReply(selective=True))
        
    
        pending["awaiting_outcome_v"] = False
        pending["awaiting_startdate"] = True


    elif pending.get("awaiting_startdate"):
        start_date = text
        context.user_data['bet']['event']['start_event'] = start_date

        await context.bot.send_message(chat_id=CHAT_ID, text="Wat is de ware kans dat het team wint bv'%30?", 
                     reply_markup=ForceReply(selective=True))


        pending["awaiting_startdate"] = False
        pending["awaiting_true_prob"] = True 

    elif pending.get("awaiting_true_prob"):
        true_prob = text
        context.user_data['bet']['event']["win_chance"] = true_prob

        await context.bot.send_message(chat_id=CHAT_ID, text="Naam en quotering + bookmaker outcome 1 volgens format: thuis @ 2.8 unibet", 
                     reply_markup=ForceReply(selective=True))
        
        pending["awaiting_true_prob"] = False
        pending["awaiting_outcome_1"] = True 


    elif pending.get("awaiting_outcome_1"):
        outcome_1 = text
    
        name, price = outcome_1.split(" @ ")
        price, bookmaker = price.split(" ")
        name = name.strip().lower()
        context.user_data['bet']['outcomes'][name].append({'bookmaker': bookmaker,
                                                      'odd': price})
        
        if name == context.user_data['bet']['selection']["outcome"]:
            context.user_data['bet']['selection']['odd'] = price
            context.user_data['bet']['selection']['bookmaker'] = bookmaker
        
        await context.bot.send_message(chat_id=CHAT_ID, text="Naam en quotering + bookmaker outcome 2 volgens format: tie @ 2.9 bwin.be", 
                    reply_markup=ForceReply(selective=True))
        
        pending["awaiting_outcome_1"] = False
        pending["awaiting_outcome_2"] = True
    
        
    elif pending.get("awaiting_outcome_2"):
        outcome_2 = text

        name, price = outcome_2.split(" @ ")
        price, bookmaker = price.split(' ')
        name = name.strip().lower()
        data = price, bookmaker
        value_team = context.user_data['bet']['selection']["outcome"]

        pending["awaiting_outcome_2"] = False
        context.user_data['bet']['outcomes'][name].append({'bookmaker': bookmaker,
                                                      'odd': price})
        
        list_outcomes = [outcome for outcome in context.user_data['bet']['outcomes'].keys()]
        if not value_team in list_outcomes:
            await context.bot.send_message(chat_id=CHAT_ID, text="Outcome value bet niet teruggevonden")
        
        if name == context.user_data['bet']['selection']["outcome"]:
            context.user_data['bet']['selection']['odd'] = price
            context.user_data['bet']['selection']['bookmaker'] = bookmaker
        
        if pending.get("awaiting_teams")[1] == 3:
            await context.bot.send_message(chat_id=CHAT_ID, text="Naam en quotering outcome 3 + bookmaker volgens format: uit @ 2.9 pinnacle", 
                    reply_markup=ForceReply(selective=True))
        
            pending["awaiting_outcome_3"] = True

        else:
            context.application.create_task(
                calculate(update=update, context=context, bet=context.user_data)
            )
        
    
    elif pending.get("awaiting_outcome_3"):
        outcome_3 = text
        name, price = outcome_3.split(" @ ")
        price, bookmaker = price.split(' ')
        name = name.strip().lower()
        value_team = context.user_data['bet']['selection']["outcome"]

        context.user_data['bet']['outcomes'][name].append({'bookmaker': bookmaker,
                                                      'odd': price})
        
        list_outcomes = [outcome for outcome in context.user_data['bet']['outcomes'].keys()]
        if not value_team in list_outcomes:
            await context.bot.send_message(chat_id=CHAT_ID, text="Outcome value bet niet teruggevonden")    
               
        if name == context.user_data['bet']['selection']["outcome"]:
            context.user_data['bet']['selection']['odd'] = price
            context.user_data['bet']['selection']['bookmaker'] = bookmaker

        pending["awaiting_outcome_3"] = False
        context.application.create_task(
                calculate(update=update, context=context, bet=context.user_data)
        )

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

async def build_bet(update, context):
    cmmd = update.message.text

    if cmmd == "/log":
        context.user_data["bet"] = {}
        data = context.user_data["bet"]
        data['event'] = {}
        data['outcomes'] = defaultdict(list)
        data['stake'] = {}
        data['hedge'] = {}
        data['id'] = uuid.uuid4().hex
        data['selection'] = {}
        context.user_data['pending'] = {
            "decision": None,
            "decision_event": asyncio.Event(),
            "hinge_event": asyncio.Event()
        },
        data['manual'] = True

        keyboard = [
            [
                InlineKeyboardButton(text="2", callback_data="outcomes_2"),
                InlineKeyboardButton(text="3", callback_data="outcomes_3")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=CHAT_ID, text="Voer het aantal outcomes in (2 of 3)", 
                     reply_markup=reply_markup)
        
    
    elif cmmd == "/run":
        await context.bot.send_message(chat_id=CHAT_ID, text="Aan het scannen voor opportuniteiten....")
        

        tournaments = (await asyncio.to_thread(api.get_tournaments))[:50]
        print(type(tournaments))

            
        available = await asyncio.to_thread(api.get_available_tournaments,
            tournaments,
            BOOKMAKERS[0]
        )

        availability_msg = (f"{len(available)} Beschikbare competities bij {BOOKMAKERS[0]}\n")
        await context.bot.send_message(chat_id=CHAT_ID, text=availability_msg)

        #available_matches_msg = f"Aantal wedstrijden: {len(available)}"

                #available_msg = f"Tournooi: {fixture['tournamentId']} - {fixture['categoryName']} \
                #{fixture['tournamentName']}\n{available_matches_msg}"
                
                #await context.bot.send_message(chat_id=CHAT_ID, text=available_msg)

        for k,v in available.items():
            for fixture in v:
                
                teamnames = f"{fixture['participant1Name']} - {fixture['participant2Name']}"
                league = fixture["statusName"]
                tournament = fixture["tournamentSlug"]
                land = fixture["categoryName"]
                fixtureid = fixture["fixtureId"]
                start_time = fixture['startTime']

                market_map = await asyncio.to_thread(api.compare_bookmakers_for_fixture, fixture)
                results = analyse_market_data(market_map)

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
                    
                        bet_data = {}
                        bet_data['bet'] = {}
                        bet = bet_data["bet"]
                        bet['event'] = {}
                        bet['outcomes'] = defaultdict(list)
                        bet['stake'] = {}
                        bet['hedge'] = {}
                        bet['id'] = uuid.uuid4().hex
                        bet['selection'] = {}
                        bet['manual'] = False

                        bet_data['pending'] = {
                            "decision": None,
                            "decision_event": asyncio.Event(),
                            "hinge_event": asyncio.Event()
                        }
                        

                        event = bet["event"]
                        event = bet['event']  
                        selection = bet['selection'] 
                        bet['type'] = 'valuebet'
                        event['league'] = league
                        event['start_event'] = start_time
                        event['teamnames'] = teamnames
                        event['tournament'] = tournament + land
                        event['win_chance'] = avg_chance_win

                        bet['outcomes'][None].extend({'bookmaker': i['bookmaker'], 'odd': i['price']} for i in outcomes['all_prices'])
                        selection['betslip'] = betslip
                        selection['bookmaker'] = outcomes['bookmaker']
                        selection['odd'] = outcomes['max_odds']
                        selection['market_id'] = markets
                        selection['fixture_id'] = fixtureid
                        selection['outcome'] = None

                        pprint(outcomes)
                        print('--------------------------------')
                        
                        await calculate(update=update, context=context, bet=bet_data)


CURRENT_KEY = 0

                
def run():

    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )
    print(application.handlers)


    application.add_handler(
        CallbackQueryHandler(
            handle_button
        )
    )
    print("CALLBACK HANDLER TOEGEVOEGD")


    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_tekst_message
        )
    )

    application.add_handler(
        CommandHandler(["log", "run"], build_bet)
    )
    

    application.run_polling()


if __name__ == "__main__":
    run()
    

    
    

                      
                        
       
                        


                       



