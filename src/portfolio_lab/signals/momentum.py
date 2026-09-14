"""Momentum signals."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Signal, zscore_cross_section


class TimeSeriesMomentum(Signal):
    """Classic 12-1: trailing 12-month return, skipping the most recent month.

    The one-month skip exists because short-horizon returns tend to reverse, so
    including the latest month contaminates a trend signal with reversal.

    Score is the raw trailing return, so the sign is meaningful on its own: this
    signal says "own what has been going up", independent of the other assets.
    """

    name = "ts_momentum"

    def __init__(self, lookback: int = 252, skip: int = 21) -> None:
        self.lookback = lookback
        self.skip = skip

    def compute(self, prices: pd.DataFrame) -> pd.DataFrame:
        log_px = np.log(prices)
        # Return from t-lookback to t-skip, known at t.
        score = log_px.shift(self.skip) - log_px.shift(self.lookback)
        return score


class CrossSectionalMomentum(Signal):
    """Rank assets against each other on trailing return.

    Unlike the time-series version this is zero-sum by construction: the scores
    are demeaned across the universe, so it expresses only relative views and
    leaves the overall market exposure to the allocator.
    """

    name = "xs_momentum"

    def __init__(self, lookback: int = 252, skip: int = 21) -> None:
        self.lookback = lookback
        self.skip = skip

    def compute(self, prices: pd.DataFrame) -> pd.DataFrame:
        log_px = np.log(prices)
        trailing = log_px.shift(self.skip) - log_px.shift(self.lookback)
        # Rank within each date, map to [-1, 1], then standardise.
        ranks = trailing.rank(axis=1, pct=True)
        centred = 2.0 * (ranks - 0.5)
        return zscore_cross_section(centred)
