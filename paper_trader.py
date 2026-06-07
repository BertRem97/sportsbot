import pandas as pd
from pathlib import Path

FILE = "paper_trades.csv"


class PaperTrader:

    def __init__(
        self,
        bankroll=1000
    ):
        self.bankroll = bankroll

    def log_trade(
        self,
        row
    ):

        df = pd.DataFrame([row])

        if Path(FILE).exists():

            df.to_csv(
                FILE,
                mode="a",
                index=False,
                header=False
            )

        else:

            df.to_csv(
                FILE,
                index=False
            )
