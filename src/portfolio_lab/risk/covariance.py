"""Covariance estimation.

This is where most of the damage happens. With 12 assets and 252 days you are
estimating 78 free parameters from 3,024 observations, which sounds comfortable
and is not: the sample covariance's smallest eigenvalues are badly biased
downward, and a mean-variance optimiser will find them and lever into them. The
optimiser is an error-maximiser fed a noisy Sigma.

Three estimators, increasing in robustness:
  sample   -- the naive one, included so you can see it misbehave
  ewma     -- exponential weighting, responsive to regime change
  shrunk   -- Ledoit-Wolf shrinkage toward a structured target

All return ANNUALISED covariance matrices.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def sample_cov(returns: pd.DataFrame, ann: int = TRADING_DAYS) -> pd.DataFrame:
    return returns.cov() * ann


def ewma_cov(returns: pd.DataFrame, halflife: int = 63, ann: int = TRADING_DAYS) -> pd.DataFrame:
    """Exponentially weighted covariance. Halflife in trading days."""
    lam = np.exp(np.log(0.5) / halflife)
    n = len(returns)
    weights = lam ** np.arange(n - 1, -1, -1)
    weights = weights / weights.sum()
    x = returns.to_numpy()
    mu = np.average(x, axis=0, weights=weights)
    centred = x - mu
    cov = (centred * weights[:, None]).T @ centred
    cov = cov / (1.0 - np.sum(weights**2))
    return pd.DataFrame(cov * ann, index=returns.columns, columns=returns.columns)


def ledoit_wolf_cov(returns: pd.DataFrame, ann: int = TRADING_DAYS) -> pd.DataFrame:
    """Ledoit-Wolf shrinkage toward a constant-correlation target.

    Shrinkage trades a little bias for a lot of variance reduction. In practice
    this is the single highest-value line of code in an optimiser pipeline.
    """
    from sklearn.covariance import LedoitWolf

    lw = LedoitWolf().fit(returns.to_numpy())
    return pd.DataFrame(lw.covariance_ * ann, index=returns.columns, columns=returns.columns)


ESTIMATORS = {"sample": sample_cov, "ewma": ewma_cov, "shrunk": ledoit_wolf_cov}


def estimate(returns: pd.DataFrame, method: str = "shrunk", **kwargs) -> pd.DataFrame:
    if method not in ESTIMATORS:
        raise ValueError(f"Unknown covariance method {method!r}. Options: {sorted(ESTIMATORS)}")
    cov = ESTIMATORS[method](returns, **kwargs)
    return _nearest_psd(cov)


def _nearest_psd(cov: pd.DataFrame, eps: float = 1e-10) -> pd.DataFrame:
    """Clip negative eigenvalues. Cheap insurance against an optimiser blowup."""
    vals, vecs = np.linalg.eigh(cov.to_numpy())
    if (vals > eps).all():
        return cov
    vals = np.clip(vals, eps, None)
    fixed = vecs @ np.diag(vals) @ vecs.T
    return pd.DataFrame(fixed, index=cov.index, columns=cov.columns)


def portfolio_vol(weights: pd.Series, cov: pd.DataFrame) -> float:
    w = weights.reindex(cov.index).fillna(0.0).to_numpy()
    return float(np.sqrt(w @ cov.to_numpy() @ w))


def risk_contributions(weights: pd.Series, cov: pd.DataFrame) -> pd.Series:
    """Each asset's share of total portfolio risk. Sums to 1."""
    w = weights.reindex(cov.index).fillna(0.0).to_numpy()
    sigma = cov.to_numpy()
    vol = np.sqrt(w @ sigma @ w)
    if vol <= 0:
        return pd.Series(0.0, index=cov.index)
    marginal = sigma @ w / vol
    contrib = w * marginal / vol
    return pd.Series(contrib, index=cov.index)
