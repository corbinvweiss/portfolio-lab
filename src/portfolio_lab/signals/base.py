"""Signal contract.

A Signal maps a price history to a score per asset per date. Scores are
*views*, not weights -- turning a view into a position is the allocator's job,
and keeping that boundary clean is the main architectural idea in this repo.

The no-lookahead rule, enforced here by convention and in tests by assertion:
the score at row `t` may use data up to and including `t`, and is traded on the
return from `t` to `t+1`. Any signal that violates this will look brilliant.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Signal(ABC):
    name: str = "signal"

    @abstractmethod
    def compute(self, prices: pd.DataFrame) -> pd.DataFrame:
        """prices: wide (index=date, columns=ticker) -> scores, same shape."""

    def __repr__(self) -> str:  # pragma: no cover
        return f"{self.__class__.__name__}(name={self.name!r})"


def zscore_cross_section(df: pd.DataFrame, clip: float = 3.0) -> pd.DataFrame:
    """Standardise each row across assets. Makes signals comparable and blendable."""
    mu = df.mean(axis=1)
    sd = df.std(axis=1).replace(0.0, pd.NA)
    z = df.sub(mu, axis=0).div(sd, axis=0)
    return z.clip(-clip, clip).astype(float)


def blend(signals: dict[str, pd.DataFrame], weights: dict[str, float] | None = None) -> pd.DataFrame:
    """Weighted average of z-scored signals, re-standardised."""
    weights = weights or {k: 1.0 / len(signals) for k in signals}
    total = sum(weights.values())
    acc = None
    for key, frame in signals.items():
        contrib = zscore_cross_section(frame) * (weights[key] / total)
        acc = contrib if acc is None else acc.add(contrib, fill_value=0.0)
    return zscore_cross_section(acc)
