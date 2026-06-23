
from pprint import pprint
from collections import defaultdict
import statistics
from config import BOOKMAKERS, USED_BOOKMAKERS
from config import TELEGRAM_TOKEN, CHAT_ID
from config import min_win_chance, min_percentage_ov
import logger_dev as logger
from telegram import InlineKeyboardButton, Bot
from telegram import InlineKeyboardMarkup
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


async def handle_message(update, context):
    pass



# ---------------- STRATEGY ----------------

async def build_bet(manual):
    error_msg = "Bet reeds gelogd, log een ander bet"
    succes_msg = "✔ Opgeslagen in Google Sheets"

    if manual:
        hinge = implied_probs(odds)
        idx = outcomes.index(value_team)
        bet_placed = outcomes[idx]
        other_p = [i for i in outcomes if i != value_team]


        stakes, ev, payout = calculate_ev_stakes_wkelly(odds, 
                                            idx, true_prob_val, hinge)
        

        total_stakes = (lambda x: sum(x))([i for i in stakes.values() if i is not None])
        net_profit = payout - total_stakes
    
        data = {
            "outcomes": outcomes,
            "odds": odds,
            "ev": ev,
            "bet_placed": bet_placed,
            "stakes": stakes,
            "hinge": False,
            "net_profit": net_profit,
            "stake_val_bet": stakes["stake_val"],
            "total_stake": total_stakes,
            "outcome_bet": value_team,
            "min_odd_other_p": None,
            "min_stake_other_p": None,
            "other_p": None
            }  

        if hinge:
            data["hinge"] = True
        
        else:
            if len(outcomes) != 3:
                min_odds, min_stake = calculate_hinge_1X2_after(odds[idx], stakes['stake_val'])
                data["min_odd_other_p"] = min_odds
                data["min_stake_other_p"] = min_stake
                data["other_p"] = other_p
                
                payout_other_p = data["min_stake_other_p"]


        if logger.log_to_sheet(bet=bet):
            bot.send_message(chat_id=CHAT_ID, text=succes_msg)
        else:
            bot.send_message(chat_id=CHAT_ID, text=error_msg)
    


    elif manual == False:
        tournaments = api.get_tournaments()[:100]

        print(
            f"{len(tournaments)} competities gevonden"
        )
    
        available = api.get_available_tournaments(
            tournaments,
            BOOKMAKERS[0]
        )

        print(f"{len(available)} Beschikbare competities bij {BOOKMAKERS[0]}\n")

        for k,v in available.items():
            for fixture in v:

                print(fixture["tournamentId"],"-",fixture["categoryName"],
                    "-",fixture["tournamentName"]
                )
            
                print(
                    "Aantal wedstrijden:",
                    len(available)
                )

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


                market_map = api.compare_bookmakers_for_fixture(
                    fixture
                )
                

                results = api.analyse_market_data(
                    market_map
                )


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
        Waarschijnlijkheid: {win_chance:.2f}%
        Overwaarde: {ov:.2f}%
        Betslip: {betslip}
        Bookmaker: {bookmaker} @ {max_odd}
        -----------------------------------
        {odds_text}
        
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
                                    pprint(outcomes)
                                    
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
                                        if logger.log_to_sheet(bet=bet):
                                            bot.send_message(chat_id=CHAT_ID, text=succes_msg)
                                        else:
                                            bot.send_message(chat_id=CHAT_ID, text=error_msg)
                                    
                                    else:
                                        continue

    

######################################################







# -----------------------------
# MAIN
# -----------------------------
bot = Bot(token=TELEGRAM_TOKEN)
application = (Application.builder().token(TELEGRAM_TOKEN).build())

CURRENT_KEY = 0
async def main():
    logger.get_settlements()
    
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

    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.COMMAND, 
            handle_message))
    
    application.add_handler(CommandHandler("manuallog", await build_bet(manual=True)))
    application.add_handler(CommandHandler("autosearch", await build_bet(manual=False)))
    


    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    await main()

    await application.updater.stop()
    await application.stop()
    await application.shutdown()


if __name__ == "__main__":
    asyncio.run(run())
    

    
    

                      
                        
       
                        


                       



