"""Each allocator must do what its name claims."""
import numpy as np
import pandas as pd
import pytest

from portfolio_lab.allocate import (
    MeanVarianceAllocator,
    RiskBudget,
    RiskParityAllocator,
    VolTargetAllocator,
)
from portfolio_lab.risk import covariance as cov_mod


@pytest.fixture
def cov(synth):
    prices, _ = synth
    return cov_mod.estimate(np.log(prices).diff().dropna())


@pytest.fixture
def views(cov):
    rng = np.random.default_rng(3)
    return pd.Series(rng.normal(size=len(cov)), index=cov.index)


BUDGET = RiskBudget(target_vol=0.10, max_gross=1.0, max_weight=0.35, long_only=True)


def test_risk_parity_equalises_risk_contributions(cov, views):
    w = RiskParityAllocator().weights(views, cov, RiskBudget(target_vol=0.10, max_gross=10.0,
                                                            max_weight=10.0, long_only=True))
    rc = cov_mod.risk_contributions(w, cov)
    target = 1.0 / len(cov)
    assert np.abs(rc - target).max() < 0.01, f"risk contributions not equal: {rc.to_dict()}"


def test_risk_parity_ignores_views(cov, views):
    """Its whole premise: no return forecast is used."""
    alloc = RiskParityAllocator()
    w1 = alloc.weights(views, cov, BUDGET)
    w2 = alloc.weights(views * -5.0, cov, BUDGET)
    pd.testing.assert_series_equal(w1, w2)


@pytest.mark.parametrize("cls", [VolTargetAllocator, RiskParityAllocator, MeanVarianceAllocator])
def test_respects_the_risk_budget(cls, cov, views):
    w = cls().weights(views, cov, BUDGET)
    predicted = cov_mod.portfolio_vol(w, cov)
    assert predicted <= BUDGET.target_vol + 1e-6, f"{cls.__name__} breached the vol cap"
    assert w.abs().sum() <= BUDGET.max_gross + 1e-9
    assert w.max() <= BUDGET.max_weight + 1e-9
    assert (w >= -1e-12).all(), "long_only violated"


def test_mean_variance_tilts_toward_the_view(cov):
    """Sanity: raise the view on one asset, its weight should not fall."""
    base = pd.Series(0.0, index=cov.index)
    base.iloc[0] = 0.5
    tilted = base.copy()
    tilted.iloc[0] = 2.5

    alloc = MeanVarianceAllocator()
    w_base = alloc.weights(base, cov, BUDGET)
    w_tilt = alloc.weights(tilted, cov, BUDGET)
    assert w_tilt.iloc[0] >= w_base.iloc[0] - 1e-9


def test_vol_target_scales_with_the_budget(cov, views):
    alloc = VolTargetAllocator()
    low = alloc.weights(views, cov, RiskBudget(target_vol=0.05, max_gross=5.0, max_weight=5.0))
    high = alloc.weights(views, cov, RiskBudget(target_vol=0.15, max_gross=5.0, max_weight=5.0))
    assert high.abs().sum() > low.abs().sum() * 2.5
