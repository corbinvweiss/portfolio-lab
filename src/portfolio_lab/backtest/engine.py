"""Walk-forward backtest engine.

The whole design exists to make one specific mistake impossible. Lookahead bias
is the single most common reason a research backtest is wrong, and it is almost
never introduced deliberately -- it sneaks in through a `.rolling()` that is
centred, a fillna that back-fills, or a covariance fitted on the full sample.

The contract enforced here:

    decision at date t  ->  uses prices[:t] only
                        ->  weights applied to the return from t to t+1

Between rebalances, weights DRIFT with returns rather than being silently
rebalanced daily. That matters: a "monthly rebalanced" backtest that quietly
rebalances every day understates turnover and overstates the rebalancing bonus.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..allocate.base import Allocator, RiskBudget
from ..risk import covariance as cov_mod
from .costs import LinearCostModel
from .metrics import summarise


@dataclass
class BacktestResult:
    returns: pd.Series
    weights: pd.DataFrame
    targets: pd.DataFrame
    costs: pd.Series
    gross_exposure: pd.Series
    predicted_vol: pd.Series
    metrics: dict = field(default_factory=dict)

    @property
    def equity(self) -> pd.Series:
        return (1 + self.returns.fillna(0.0)).cumprod()


REBALANCE_RULES = {"daily": "D", "weekly": "W-FRI", "monthly": "ME", "quarterly": "QE"}


def rebalance_dates(index: pd.DatetimeIndex, rule: str = "monthly") -> pd.DatetimeIndex:
    if rule == "daily":
        return index
    freq = REBALANCE_RULES.get(rule)
    if freq is None:
        raise ValueError(f"Unknown rebalance rule {rule!r}. Options: {sorted(REBALANCE_RULES)}")
    marks = pd.Series(index, index=index).resample(freq).last().dropna()
    return pd.DatetimeIndex(marks.values)


def run_backtest(
    prices: pd.DataFrame,
    signal_fn,
    allocator: Allocator,
    budget: RiskBudget,
    *,
    cov_method: str = "shrunk",
    cov_window: int = 252,
    warmup: int = 300,
    rebalance: str = "monthly",
    cost_model: LinearCostModel | None = None,
    regime_fn=None,
) -> BacktestResult:
    """Run one configuration end to end.

    signal_fn: prices (wide, history only) -> DataFrame of scores, same shape.
               Called ONCE on the full history; the engine then reads only row t
               at decision time, so a signal that peeks forward inside its own
               computation is the caller's bug -- `tests/test_no_lookahead.py`
               is what catches it.
    regime_fn: optional prices -> Series of gross-exposure multipliers.
    """
    cost_model = cost_model or LinearCostModel()
    prices = prices.sort_index().dropna(how="all")
    returns = prices.pct_change().fillna(0.0)

    scores = signal_fn(prices)
    regime = regime_fn(prices) if regime_fn is not None else None

    index = prices.index
    decision_days = set(rebalance_dates(index[warmup:], rebalance))

    tickers = list(prices.columns)
    w = pd.Series(0.0, index=tickers)
    pending: pd.Series | None = None

    rows_ret, rows_cost, rows_gross, rows_pvol = [], [], [], []
    weight_hist: dict[pd.Timestamp, pd.Series] = {}
    target_hist: dict[pd.Timestamp, pd.Series] = {}

    for i, day in enumerate(index):
        if i < warmup:
            continue

        # 1. Apply any target decided on the PREVIOUS day. This single line is
        #    the no-lookahead guarantee.
        cost = 0.0
        if pending is not None:
            cost = cost_model.charge(w, pending)
            w = pending.copy()
            pending = None

        # 2. Earn today's return on the weights we entered the day holding.
        day_ret = float((w * returns.loc[day]).sum()) - cost

        # 3. Let weights drift with realised returns.
        if w.abs().sum() > 0:
            grown = w * (1.0 + returns.loc[day])
            denom = 1.0 + float((w * returns.loc[day]).sum())
            w = grown / denom if denom != 0 else grown

        # 4. Decide tomorrow's target using information through today only.
        predicted = np.nan
        if day in decision_days:
            hist = returns.loc[:day].iloc[-cov_window:]
            if len(hist) >= max(30, cov_window // 4):
                cov = cov_mod.estimate(hist, method=cov_method)
                views = scores.loc[day].reindex(tickers)
                if views.notna().any():
                    eff_budget = budget
                    if regime is not None:
                        mult = float(regime.loc[day]) if day in regime.index else 1.0
                        if np.isfinite(mult):
                            eff_budget = RiskBudget(
                                target_vol=budget.target_vol * mult,
                                max_gross=budget.max_gross,
                                max_weight=budget.max_weight,
                                long_only=budget.long_only,
                                sleeve_budgets=budget.sleeve_budgets,
                            )
                    target = allocator.weights(views.fillna(0.0), cov, eff_budget)
                    pending = target
                    target_hist[day] = target
                    predicted = cov_mod.portfolio_vol(target, cov)

        rows_ret.append((day, day_ret))
        rows_cost.append((day, cost))
        rows_gross.append((day, float(w.abs().sum())))
        rows_pvol.append((day, predicted))
        weight_hist[day] = w.copy()

    ret_s = pd.Series(dict(rows_ret)).sort_index()
    weights_df = pd.DataFrame(weight_hist).T.sort_index()
    targets_df = pd.DataFrame(target_hist).T.sort_index()
    costs_s = pd.Series(dict(rows_cost)).sort_index()
    gross_s = pd.Series(dict(rows_gross)).sort_index()
    pvol_s = pd.Series(dict(rows_pvol)).sort_index()

    return BacktestResult(
        returns=ret_s,
        weights=weights_df,
        targets=targets_df,
        costs=costs_s,
        gross_exposure=gross_s,
        predicted_vol=pvol_s,
        metrics=summarise(ret_s, targets_df),
    )
