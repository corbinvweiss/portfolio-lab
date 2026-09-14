"""Transaction costs.

A linear cost on turnover plus a fixed spread. Crude, but crude and present
beats precise and absent: the main job of a cost model in a research harness is
to kill strategies whose edge is smaller than their friction, and a flat
basis-point charge does that job.
"""
from __future__ import annotations

import pandas as pd


class LinearCostModel:
    def __init__(self, cost_bps: float = 5.0) -> None:
        """cost_bps: round-trip cost per unit of notional traded, in bps."""
        self.cost_bps = cost_bps

    def charge(self, prev_w: pd.Series, new_w: pd.Series) -> float:
        """Cost as a fraction of portfolio value for moving prev_w -> new_w."""
        aligned_prev = prev_w.reindex(new_w.index).fillna(0.0)
        turnover = (new_w - aligned_prev).abs().sum()
        return turnover * self.cost_bps / 10_000.0
