"""Performance metrics. Nothing exotic -- the point is that they are computed
the same way for every allocator so the comparison is apples to apples."""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def summarise(returns: pd.Series, weights: pd.DataFrame | None = None) -> dict:
    r = returns.dropna()
    if r.empty:
        return {}
    equity = (1 + r).cumprod()
    years = len(r) / TRADING_DAYS
    cagr = equity.iloc[-1] ** (1 / years) - 1 if years > 0 else np.nan
    vol = r.std() * np.sqrt(TRADING_DAYS)
    sharpe = cagr / vol if vol > 0 else np.nan
    drawdown = equity / equity.cummax() - 1
    downside = r[r < 0].std() * np.sqrt(TRADING_DAYS)

    out = {
        "cagr": float(cagr),
        "ann_vol": float(vol),
        "sharpe": float(sharpe),
        "sortino": float(cagr / downside) if downside > 0 else np.nan,
        "max_drawdown": float(drawdown.min()),
        "calmar": float(cagr / abs(drawdown.min())) if drawdown.min() < 0 else np.nan,
        "hit_rate": float((r > 0).mean()),
        "worst_day": float(r.min()),
        "n_days": int(len(r)),
    }
    if weights is not None and not weights.empty:
        # Annualise by elapsed time, not by row count: `weights` here holds one
        # row per REBALANCE, so multiplying a per-row mean by 252 would report a
        # monthly strategy as if it traded every day.
        turnover = weights.diff().abs().sum(axis=1)
        out["ann_turnover"] = float(turnover.sum() / years) if years > 0 else np.nan
        out["avg_gross"] = float(weights.abs().sum(axis=1).mean())
    return out


def drawdown_series(returns: pd.Series) -> pd.Series:
    equity = (1 + returns.dropna()).cumprod()
    return equity / equity.cummax() - 1
