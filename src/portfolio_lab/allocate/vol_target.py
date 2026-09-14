"""Volatility targeting: the simplest honest answer to "what is a risk budget".

Relative weights come straight from the views (optionally scaled by inverse
volatility so a view on a 30-vol asset does not dominate a view on a 5-vol one).
Then the whole book is scaled so that *predicted* portfolio volatility equals the
target. The risk budget here is a single number for the portfolio as a whole.

Worth noticing in the backtest: the scaling is done on predicted vol, and
realised vol will miss the target, sometimes badly. That gap is the whole
difficulty of risk management in one observation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..risk.covariance import portfolio_vol
from .base import Allocator, RiskBudget, apply_constraints


class VolTargetAllocator(Allocator):
    name = "vol_target"

    def __init__(self, inverse_vol_scale: bool = True) -> None:
        self.inverse_vol_scale = inverse_vol_scale

    def weights(self, views: pd.Series, cov: pd.DataFrame, budget: RiskBudget) -> pd.Series:
        v = views.reindex(cov.index).fillna(0.0)
        if budget.long_only:
            v = v.clip(lower=0.0)

        if self.inverse_vol_scale:
            vols = pd.Series(np.sqrt(np.diag(cov.to_numpy())), index=cov.index)
            raw = v / vols.replace(0.0, np.nan)
        else:
            raw = v

        raw = raw.fillna(0.0)
        if raw.abs().sum() == 0:
            raw = pd.Series(1.0, index=cov.index)  # fall back to equal weight

        raw = raw / raw.abs().sum()
        raw = apply_constraints(raw, budget)

        predicted = portfolio_vol(raw, cov)
        if predicted > 0:
            raw = raw * (budget.target_vol / predicted)
        return apply_constraints(raw, budget)
