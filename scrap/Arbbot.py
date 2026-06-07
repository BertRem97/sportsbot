from dataclasses import dataclass


@dataclass
class Odds:
    A: float
    X: float
    B: float


def implied_sum(odds: Odds):
    return (1/odds.A) + (1/odds.X) + (1/odds.B)


def is_arbitrage(odds: Odds):
    return implied_sum(odds) < 1


def ev_implied(prob, odds):
    return prob * odds - 1


def normalize_probs(odds: Odds):
    raw = {
        "A": 1/odds.A,
        "X": 1/odds.X,
        "B": 1/odds.B
    }
    s = sum(raw.values())
    return {k: v/s for k, v in raw.items()}


def optimal_arb_stakes(bankroll, odds: Odds):
    inv_sum = implied_sum(odds)

    return {
        "A": (1/odds.A)/inv_sum * bankroll,
        "X": (1/odds.X)/inv_sum * bankroll,
        "B": (1/odds.B)/inv_sum * bankroll,
        "profit_pct": (1/inv_sum - 1) * 100
    }


def evaluate(bankroll, odds: Odds):
    probs = normalize_probs(odds)

    return {
        "market_probs": probs,
        "ev_check": True,   # EV moet je hier apart per bookmaker berekenen
        "arb_possible": is_arbitrage(odds),
        "implied_sum": implied_sum(odds),
        "strategy": "ARBITRAGE" if is_arbitrage(odds) else "VALUE_ONLY"
    }


# usage
odds = Odds(A=3.2, X=2.8, B=4)

result = evaluate(1000, odds)

if result["arb_possible"]:
    print(optimal_arb_stakes(1000, odds))
else:
    print("No hedge possible → only value betting allowed")
