"""Mean-variance with an explicit variance cap.

    maximise   w' mu
    subject to w' Sigma w <= target_vol^2
               sum w = gross (or <= gross)
               bounds on each w_i

This is the textbook framing and the one that will hurt you, which is why it is
worth building yourself. Two things to watch in the backtest:

1. Estimation error dominates. `mu` here is the signal z-score scaled to a
   plausible return dispersion -- it is a *view*, not a forecast, and the
   optimiser will treat it as gospel and concentrate accordingly. Compare the
   turnover against risk parity to see the cost.

2. The variance constraint binds almost always, because the objective is linear
   and wants unlimited exposure. So the solution sits on the boundary of the
   risk budget by construction -- which makes this the most literal reading of
   "maximise returns subject to a risk budget".

Solved with SLSQP. For 12 assets that is instant and exact enough; a production
system would use a proper conic solver.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ..risk.covariance import portfolio_vol
from .base import Allocator, RiskBudget, apply_constraints


class MeanVarianceAllocator(Allocator):
    name = "mean_variance"

    def __init__(self, view_scale: float = 0.05, ridge: float = 0.0) -> None:
        """view_scale: converts a unit z-score view into an annual return
        assumption. 0.05 means a +1 sigma view implies +5% expected return.
        ridge: optional penalty on w'w, a crude but effective brake on the
        concentration that pure MVO produces."""
        self.view_scale = view_scale
        self.ridge = ridge

    def weights(self, views: pd.Series, cov: pd.DataFrame, budget: RiskBudget) -> pd.Series:
        tickers = cov.index
        n = len(tickers)
        sigma = cov.to_numpy()
        mu = views.reindex(tickers).fillna(0.0).to_numpy() * self.view_scale

        if not np.isfinite(mu).all() or np.allclose(mu, 0.0):
            # No usable view: fall back to minimum variance, which is the
            # honest thing to do when you have no opinion.
            return self._min_variance(tickers, sigma, budget)

        var_cap = budget.target_vol**2

        def objective(w: np.ndarray) -> float:
            return -(w @ mu) + self.ridge * (w @ w)

        def objective_grad(w: np.ndarray) -> np.ndarray:
            return -mu + 2.0 * self.ridge * w

        constraints = [
            {  # variance cap
                "type": "ineq",
                "fun": lambda w: var_cap - w @ sigma @ w,
                "jac": lambda w: -2.0 * sigma @ w,
            },
            {  # gross exposure cap (long-only -> sum w <= max_gross)
                "type": "ineq",
                "fun": lambda w: budget.max_gross - np.sum(np.abs(w)),
            },
        ]
        lower = 0.0 if budget.long_only else -budget.max_weight
        bounds = [(lower, budget.max_weight)] * n

        w0 = np.full(n, min(budget.max_gross / n, budget.max_weight))
        res = minimize(
            objective, w0, jac=objective_grad, bounds=bounds,
            constraints=constraints, method="SLSQP",
            options={"maxiter": 500, "ftol": 1e-12},
        )
        w = res.x if res.success else w0
        weights = apply_constraints(pd.Series(w, index=tickers), budget)

        # Enforce the cap exactly -- SLSQP satisfies it only to tolerance.
        predicted = portfolio_vol(weights, cov)
        if predicted > budget.target_vol and predicted > 0:
            weights = weights * (budget.target_vol / predicted)
        return weights

    def _min_variance(self, tickers, sigma: np.ndarray, budget: RiskBudget) -> pd.Series:
        n = len(tickers)
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - budget.max_gross}]
        lower = 0.0 if budget.long_only else -budget.max_weight
        bounds = [(lower, budget.max_weight)] * n
        w0 = np.full(n, budget.max_gross / n)
        res = minimize(
            lambda w: w @ sigma @ w, w0, jac=lambda w: 2.0 * sigma @ w,
            bounds=bounds, constraints=constraints, method="SLSQP",
            options={"maxiter": 500, "ftol": 1e-12},
        )
        return apply_constraints(pd.Series(res.x if res.success else w0, index=tickers), budget)
