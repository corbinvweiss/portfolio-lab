"""Risk parity: equalise each asset's contribution to portfolio risk.

Needs no return forecast at all, which is the point -- it is the allocator that
says "I trust my covariance estimate and distrust my expected returns". Given
how much worse return estimation is than risk estimation, that is a defensible
position and explains why risk parity survived contact with reality.

Solved by cyclical coordinate descent on the convex formulation:

    min_w  0.5 * w' Sigma w  -  sum_i b_i * log(w_i),   w > 0

whose stationary point has risk contributions proportional to b. Optional
`budget.sleeve_budgets` distributes b across sleeves rather than assets, which
is how the term "risk budget" is actually used on a multi-strategy desk.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..risk.covariance import portfolio_vol
from .base import Allocator, RiskBudget, apply_constraints


class RiskParityAllocator(Allocator):
    name = "risk_parity"

    def __init__(
        self,
        tilt_by_views: bool = False,
        sleeve_map: dict[str, str] | None = None,
        max_iter: int = 2000,
        tol: float = 1e-10,
    ) -> None:
        self.tilt_by_views = tilt_by_views
        self.sleeve_map = sleeve_map
        self.max_iter = max_iter
        self.tol = tol

    def _budget_vector(self, views: pd.Series, cov: pd.DataFrame, budget: RiskBudget) -> np.ndarray:
        n = len(cov)
        b = np.full(n, 1.0 / n)

        if budget.sleeve_budgets and self.sleeve_map:
            sleeves = np.array([self.sleeve_map.get(t, "other") for t in cov.index])
            b = np.zeros(n)
            for sleeve, share in budget.sleeve_budgets.items():
                mask = sleeves == sleeve
                if mask.sum():
                    b[mask] = share / mask.sum()
            if b.sum() <= 0:
                b = np.full(n, 1.0 / n)
            b = b / b.sum()

        if self.tilt_by_views:
            v = views.reindex(cov.index).fillna(0.0).to_numpy()
            # Map views to a positive multiplier centred on 1; bounded so a
            # single strong view cannot claim the entire risk budget.
            tilt = np.clip(1.0 + 0.5 * np.tanh(v), 0.25, 2.0)
            b = b * tilt
            b = b / b.sum()
        return b

    def weights(self, views: pd.Series, cov: pd.DataFrame, budget: RiskBudget) -> pd.Series:
        sigma = cov.to_numpy()
        n = sigma.shape[0]
        b = self._budget_vector(views, cov, budget)

        # Initialise at inverse-vol, which is the exact solution when all
        # correlations are equal -- a good warm start.
        vols = np.sqrt(np.diag(sigma))
        w = (b / np.where(vols > 0, vols, 1.0))
        w = w / w.sum()

        for _ in range(self.max_iter):
            w_old = w.copy()
            for i in range(n):
                # Coordinate update: solve the quadratic for w_i holding others.
                others = sigma[i] @ w - sigma[i, i] * w[i]
                disc = others**2 + 4.0 * sigma[i, i] * b[i]
                w[i] = (-others + np.sqrt(disc)) / (2.0 * sigma[i, i])
            w = np.maximum(w, 1e-12)
            if np.max(np.abs(w - w_old)) < self.tol:
                break

        weights = pd.Series(w / w.sum(), index=cov.index)
        weights = apply_constraints(weights, budget)

        predicted = portfolio_vol(weights, cov)
        if predicted > 0:
            weights = weights * (budget.target_vol / predicted)
        return apply_constraints(weights, budget)
