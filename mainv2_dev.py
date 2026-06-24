
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

decision = None
decision_event = asyncio.Event()

def calculate_hinge_1X2_after(odd_val, stake_val):
    total_implied_odds = 0.99
    chance_val = 1 / odd_val

    min_odd_other_p = 1 / (total_implied_odds - chance_val)
    payout = stake_val * odd_val

    stake_other_p = payout / min_odd_other_p
    return round(min_odd_other_p, 2), round(stake_other_p, 2)


async def calculate(update, context):
    data = context.user_data
    value_team = data["outcome_value_bet"]
    outcomes = [i for i in data["outcomes"].keys()]
    odds = [i for i in data["outcomes"].values()]
    true_prob = data["true_prob"]
    hinge = implied_probs(odds)
    odds_val_bet = data["outcomes"][value_team]
    other_odds = [v for k, v in data["outcomes"].items() if k != value_team]

    stakes, ev, payout = calculate_ev_stakes_wkelly(odds_val_bet, 
                                          true_prob, hinge, KELLY_FRACTION, context, update, other_odds)
    
    total_stakes = (lambda x: sum(x))([i for i in stakes.values() if i is not None])
    net_profit = payout - total_stakes

    writing_data = {
        "outcomes": outcomes,
        "odds": odds,
        "ev": ev,
        "bet_placed": value_team,
        "stakes": stakes,
        "hinge": False,
        "net_profit": net_profit,
        "stake_val_bet": stakes["stake_val"],
        "total_stake": total_stakes,
        "min_odd_other_p": None,
        "min_stake_other_p": None,
        "other_p": None
        }  

    if hinge:
        data["hinge"] = True

    
    else:
        if len(outcomes) != 3:
            min_odds, min_stake = calculate_hinge_1X2_after(odds_val_bet, stakes['stake_val'])
            data["min_odd_other_p"] = min_odds
            data["min_stake_other_p"] = min_stake
            data["other_p"] = other_p
            
            payout_other_p = data["min_stake_other_p"]
    return data
    

def implied_probs(odds_list):
    """Convert odds → normalized true probabilities"""
    hinge = False
    inv = [1 / o for o in odds_list]
    total = sum(inv)
    true_probs = [i / total for i in inv]

    if total < 1:
        hinge = True

    return hinge

def hedge(stake_val, odd, other_odds):
    payout = stake_val * odd

    if len(other_odds) > 1:
        return payout / other_odds[0], payout / other_odds[1], payout
    
    else:
        return payout / other_odds[0], None, payout


async def calculate_ev_stakes_wkelly(odd_val_bet,
                             p, hinge,
                             fraction, context, update, other_odds):
    
    data = context.user_data
    implied_odds = None

    if odd_val_bet:
        implied_odds = odd_val_bet


    p = p / 100
    b = implied_odds - 1
    q = 1 - p
    f = (b*p - q) / b

    ev = (p * b) - (q * 1)

    if b <= 0:
        return 0
    
    stake_value = logger.bankroll * f * fraction
    payout = stake_value * implied_odds if implied_odds is not None else None

    stakes = {"stake_val": stake_value,
            "stake_x": None,
            "stake_y": None}
           
    if hinge and context.user_data["awaiting_teams"][1] == 2:
        keyboard = [
            [
                InlineKeyboardButton(text="Ja", callback_data="hinge_yes"),
                InlineKeyboardButton(text="Nope", callback_data="hinge_no")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await bot.send_message(chat_id=CHAT_ID, text="Sure bet mogelijk, wil je hingen?", 
                               reply_markup=reply_markup)
        

        context.user_data["awaiting_teams"][1] = None
        stake_x, stake_y, payout = hedge(stake_value, odd_val_bet, other_odds)
        data["stake_x"] = stake_x
        data["stake_y"] = stake_y

    return stakes, ev, payout
















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
    tekst = query.message.text

    await query.answer()
    
    if tekst == "Voer het aantal outcomes in (2 of 3)":
        await context.bot.send_message(chat_id=CHAT_ID, 
                                   text="Voer de teamnames in volgens volgend formaat: 'Belgie - Iran'",
                                   reply_markup=ForceReply(selective=True))
        
        if query.data == "outcomes_3":
            context.user_data["awaiting_teams"] = [True, 3]
            
        elif query.data == "outcomes_2":
            context.user_data["awaiting_teams"] = [True, 2]

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


async def handle_tekst_message(update, context):
    text = update.message.text 
    
    if context.user_data.get("awaiting_teams")[0]:
        teams = text
        context.user_data["teams"] = teams


        await bot.send_message(chat_id=CHAT_ID, text="Voer de league in", 
                     reply_markup=ForceReply(selective=True))
        
        context.user_data["awaiting_teams"][0] = False
        
        
        context.user_data["awaiting_league"] = True
        
    elif context.user_data.get("awaiting_league"):
        league = text
        context.user_data["league"] = league

        await bot.send_message(chat_id=CHAT_ID, text="In welk land wordt er gespeeld?", 
                     reply_markup=ForceReply(selective=True))
        
        context.user_data["awaiting_league"] = False
        context.user_data["awaiting_land"] = True


    elif context.user_data.get("awaiting_land"):
        land = text
        context.user_data["land"] = land

        await bot.send_message(chat_id=CHAT_ID, text="Op welke outcome heb je een value bet?", 
                     reply_markup=ForceReply(selective=True))
        
        context.user_data["awaiting_land"] = False
        context.user_data["awaiting_outcome_v"] = True
    
    elif context.user_data.get("awaiting_outcome_v"):
        value_team = text
        context.user_data["outcome_value_bet"] = value_team

        await bot.send_message(chat_id=CHAT_ID, text="Wat is de ware kans dat het team wint bv'%30?", 
                     reply_markup=ForceReply(selective=True))
        
    
        context.user_data["awaiting_outcome_v"] = False
        context.user_data["awaiting_true_prob"] = True

    elif context.user_data.get("awaiting_true_prob"):
        true_prob = text
        context.user_data["true_prob"] = true_prob

        await bot.send_message(chat_id=CHAT_ID, text="Naam en quotering outcome 1 volgens format: thuis 2.8", 
                     reply_markup=ForceReply(selective=True))

        context.user_data["awaiting_true_prob"] = False
        context.user_data["awaiting_outcome_1"] = True 


        
    elif context.user_data.get("awaiting_outcome_1"):
        outcome_1 = text

        try:
            name, price = outcome_1.split(" ")
            name = name.strip()
            context.user_data['outcomes'] = {}
            context.user_data['outcomes'][name] = price
            await bot.send_message(chat_id=CHAT_ID, text="Naam en quotering outcome 2 volgens format: tie 2.9", 
                        reply_markup=ForceReply(selective=True))
            
        except:
            await update.message.reply_text(text="Voer naam en quotering in gescheiden door één spatie")
                

                  
        context.user_data["awaiting_outcome_1"] = False
        context.user_data["awaiting_outcome_2"] = True

    elif context.user_data.get("awaiting_outcome_2"):
        outcome_2 = text

        try:
            name, price = outcome_2.split(" ")
            name = name.strip()

            if not context.user_data.get("outcome_value_bet") in context.user_data['outcomes']:
                await bot.send_message(chat_id=CHAT_ID, text="Outcome value bet niet teruggevonden")
            
            context.user_data["awaiting_outcome_2"] = False
            context.user_data['outcomes'][name] = price

            if context.user_data.get("awaiting_teams")[1] == 3:
                await bot.send_message(chat_id=CHAT_ID, text="Naam en quotering outcome 3 volgens format: tie 2.9", 
                        reply_markup=ForceReply(selective=True))
            
                context.user_data["awaiting_outcome_3"] = True
            
            calculate(update, context)
            
        except:
            await update.message.reply_text(text="Voer naam en quotering in gescheiden door één spatie")

    
    elif context.user_data.get("awaiting_outcome_3"):
        outcome_3 = text

        try:
            name, price = outcome_3.split(" ")
            name = name.strip()
            if not context.user_data.get("outcome_value_bet") in context.user_data['outcomes']:
                await bot.send_message(chat_id=CHAT_ID, text="Outcome value bet niet teruggevonden")

            context.user_data[name] = price
            await bot.send_message(chat_id=CHAT_ID, text="Naam en quotering outcome 3 volgens format: tie 2.9", 
                        reply_markup=ForceReply(selective=True))
            
            context.user_data["awaiting_outcome_3"] = False
            context.user_data["awaiting_outcomes"][1] = None

            calculate(update, context)

            
        except:
            await update.message.reply_text(text="Voer naam en quotering in gescheiden door één spatie")



# ---------------- STRATEGY ----------------

async def build_bet(update, context):
    cmmd = update.message.text

    error_msg = "Bet reeds gelogd, log een ander bet"
    succes_msg = "✔ Opgeslagen in Google Sheets"
    
    if cmmd == "/log":
        keyboard = [
            [
                InlineKeyboardButton(text="2", callback_data="outcomes_2"),
                InlineKeyboardButton(text="3", callback_data="outcomes_3")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await bot.send_message(chat_id=CHAT_ID, text="Voer het aantal outcomes in (2 of 3)", 
                     reply_markup=reply_markup)
        
    
        print(context.user_data)

    elif cmmd == "/run":
        pass
        
        
    

    
######################################################







# -----------------------------
# MAIN
# -----------------------------
bot = Bot(token=TELEGRAM_TOKEN)
application = (Application.builder().token(TELEGRAM_TOKEN).build())

CURRENT_KEY = 0
async def main():
    pass
    #logger.get_settlements()
    
def run():

    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    application.add_handler(
        CallbackQueryHandler(handle_button)
    )

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
    

    
    

                      
                        
       
                        


                       



