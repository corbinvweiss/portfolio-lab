import pandas as pd
import pytest

from portfolio_lab.data.synthetic import make_synthetic_prices
from portfolio_lab.data.universe import TICKERS


@pytest.fixture(scope="session")
def synth():
    long, truth = make_synthetic_prices(TICKERS, n_days=1500, seed=11)
    wide = long.pivot(index="date", columns="ticker", values="close").sort_index()
    wide.index = pd.to_datetime(wide.index)
    wide.columns.name = None
    return wide, truth
