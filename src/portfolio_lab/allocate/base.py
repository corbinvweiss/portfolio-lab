"""Allocator contract and the risk budget definition.

An Allocator maps (views, covariance, risk budget) -> weights. Every
implementation takes the same three inputs and returns a weight vector, so you
can run identical signals through all three and attribute the difference purely
to the risk model.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RiskBudget:
    """The risk constraint, in the three senses the word is used.

    target_vol      annualised portfolio volatility to target or cap (e.g. 0.10)
    max_gross       sum of |w|, the leverage cap
    max_weight      per-asset cap, the concentration limit
    long_only       forbid shorts
    sleeve_budgets  optional {sleeve: max share of total risk}
    """

    target_vol: float = 0.10
    max_gross: float = 1.0
    max_weight: float = 0.35
    long_only: bool = True
    sleeve_budgets: dict[str, float] | None = None


class Allocator(ABC):
    name: str = "allocator"

    @abstractmethod
    def weights(
        self, views: pd.Series, cov: pd.DataFrame, budget: RiskBudget
    ) -> pd.Series:
        """views: per-asset score (may be ignored). cov: annualised. -> weights."""

    def __repr__(self) -> str:  # pragma: no cover
        return f"{self.__class__.__name__}(name={self.name!r})"


def apply_constraints(w: pd.Series, budget: RiskBudget) -> pd.Series:
    """Clip to the box, then scale to respect the gross cap."""
    if budget.long_only:
        w = w.clip(lower=0.0)
    w = w.clip(lower=-budget.max_weight, upper=budget.max_weight)
    gross = w.abs().sum()
    if gross > budget.max_gross and gross > 0:
        w = w * (budget.max_gross / gross)
    return w.fillna(0.0)
