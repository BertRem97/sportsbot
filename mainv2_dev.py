
from pprint import pprint
from collections import defaultdict
import statistics
from config import BOOKMAKERS, USED_BOOKMAKERS
from config import TELEGRAM_TOKEN, CHAT_ID
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
    tekst = query.message.tekst

    if tekst == "Voer het aantal outcomes in (2 of 3): ":
        pass


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


async def handle_tekst_message(update, context):
    pass




# ---------------- STRATEGY ----------------

async def build_bet(manual=False):
    error_msg = "Bet reeds gelogd, log een ander bet"
    succes_msg = "✔ Opgeslagen in Google Sheets"
    print('ok')
    if manual:
        print('yes')

        keyboard = [
            [
                InlineKeyboardButton(text="2", callback_data="outcomes_3"),
                InlineKeyboardButton(text="3", callback_data="outcomes_2")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        
        await bot.send_message(chat_id=CHAT_ID, text="Voer het aantal outcomes in (2 of 3): ", 
                     reply_markup=reply_markup)
    

    
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
    
async def run():

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
            filters.TEXT & filters.COMMAND,
            handle_tekst_message
        )
    )

    application.add_handler(
        CommandHandler("manuallog", await build_bet(manual=True))
    )

    application.add_handler(
        CommandHandler("autosearch", await build_bet(manual=False))
    )

    await application.run_polling()



if __name__ == "__main__":
    asyncio.run(run())
    

    
    

                      
                        
       
                        


                       



