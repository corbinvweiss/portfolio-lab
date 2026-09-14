"""Regime overlay: a risk filter, not a return forecast.

This does not predict direction. It scales exposure down when realised
volatility is elevated relative to its own history, or when price is below its
long-run trend. Volatility is far more forecastable than returns, which is why
this kind of overlay is one of the few things that survives out of sample.

Output is a multiplier in [floor, 1.0], applied to gross exposure after the
allocator has set relative weights.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class VolTrendRegime:
    name = "vol_trend_regime"

    def __init__(
        self,
        vol_window: int = 21,
        vol_ref_window: int = 252,
        trend_window: int = 200,
        floor: float = 0.25,
        use_trend: bool = True,
    ) -> None:
        self.vol_window = vol_window
        self.vol_ref_window = vol_ref_window
        self.trend_window = trend_window
        self.floor = floor
        self.use_trend = use_trend

    def compute(self, prices: pd.DataFrame) -> pd.Series:
        """Return a per-date scalar multiplier on gross exposure."""
        rets = np.log(prices).diff()
        eq_curve = rets.mean(axis=1)  # equal-weight proxy for the universe

        realised = eq_curve.rolling(self.vol_window).std()
        reference = eq_curve.rolling(self.vol_ref_window).std()
        vol_ratio = (reference / realised).clip(upper=1.0)

        multiplier = vol_ratio
        if self.use_trend:
            level = (1.0 + eq_curve.fillna(0.0)).cumprod()
            above_trend = (level > level.rolling(self.trend_window).mean()).astype(float)
            # Soften the binary switch so it does not whipsaw on a single crossing.
            above_trend = above_trend.rolling(5).mean()
            multiplier = multiplier * (self.floor + (1 - self.floor) * above_trend)

        return multiplier.clip(lower=self.floor, upper=1.0).fillna(self.floor)
