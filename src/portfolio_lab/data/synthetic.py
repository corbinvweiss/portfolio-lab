"""Synthetic market generator with *known* structure.

The point is falsifiability. On real data you cannot tell whether a backtest
result is skill, luck, or a bug. Here you plant the answer, run the pipeline,
and check it comes back out. Every allocator and signal in this repo is tested
against data generated below.

Model: a small factor structure plus idiosyncratic noise, with an optional
persistent drift component that genuine momentum signals should be able to find.

    r_t = B f_t + e_t + mu_t

where f_t are k common factors, B are loadings, e_t is idiosyncratic noise, and
mu_t is a slow-moving per-asset drift (an AR(1)) that creates real, detectable
trend for a momentum signal to capture.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd


def make_synthetic_prices(
    tickers: list[str] | tuple[str, ...],
    n_days: int = 2520,
    n_factors: int = 2,
    start: date = date(2015, 1, 1),
    ann_factor_vol: float = 0.15,
    ann_idio_vol: float = 0.12,
    drift_persistence: float = 0.985,
    ann_drift_vol: float = 0.06,
    seed: int = 7,
) -> tuple[pd.DataFrame, dict]:
    """Return (long-format price frame, ground-truth dict).

    The truth dict carries the loadings, the realised drift path and the implied
    covariance, so tests can assert that estimators recover what was planted.
    """
    rng = np.random.default_rng(seed)
    n = len(tickers)
    d_factor_vol = ann_factor_vol / np.sqrt(252)
    d_idio_vol = ann_idio_vol / np.sqrt(252)
    d_drift_vol = ann_drift_vol / np.sqrt(252)

    # Loadings: first factor is a broad "market" everything loads on positively,
    # the rest are mixed sign so the covariance is not trivially rank-one.
    loadings = rng.normal(0.0, 0.6, size=(n, n_factors))
    loadings[:, 0] = rng.uniform(0.4, 1.2, size=n)

    factors = rng.normal(0.0, d_factor_vol, size=(n_days, n_factors))
    idio = rng.normal(0.0, d_idio_vol, size=(n_days, n))

    # AR(1) drift: this is the planted, findable trend.
    drift = np.zeros((n_days, n))
    shock_vol = d_drift_vol * np.sqrt(1 - drift_persistence**2)
    for t in range(1, n_days):
        drift[t] = drift_persistence * drift[t - 1] + rng.normal(0.0, shock_vol, size=n)

    returns = factors @ loadings.T + idio + drift
    prices = 100.0 * np.exp(np.cumsum(returns, axis=0))

    dates = pd.bdate_range(start=start, periods=n_days)
    wide = pd.DataFrame(prices, index=dates, columns=list(tickers))

    long = (
        wide.stack()
        .rename("close")
        .reset_index()
        .rename(columns={"level_0": "date", "level_1": "ticker"})
    )
    long["date"] = pd.to_datetime(long["date"]).dt.date
    long["volume"] = 1_000_000.0

    # Total variance = common factors + idiosyncratic + the stationary variance
    # of the AR(1) drift. Forgetting that last term is an easy way to write a
    # "failing" test for a perfectly good estimator.
    true_cov = (
        loadings @ np.diag(np.full(n_factors, d_factor_vol**2)) @ loadings.T
        + np.eye(n) * d_idio_vol**2
        + np.eye(n) * d_drift_vol**2
    ) * 252  # annualised

    truth = {
        "loadings": loadings,
        "drift": pd.DataFrame(drift, index=dates, columns=list(tickers)),
        "true_cov_annual": pd.DataFrame(true_cov, index=list(tickers), columns=list(tickers)),
        "returns": pd.DataFrame(returns, index=dates, columns=list(tickers)),
    }
    return long, truth
