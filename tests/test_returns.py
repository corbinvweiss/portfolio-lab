"""Return identities every later lesson leans on."""
import numpy as np
import pandas as pd
import pytest

from portfolio_lab.data.returns import (
    annualise_vol,
    compound,
    daily_rate_from_annual,
    log_returns,
    simple_returns,
)


@pytest.fixture
def prices():
    rng = np.random.default_rng(1)
    idx = pd.bdate_range("2020-01-01", periods=300)
    px = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, size=(300, 2)), axis=0))
    return pd.DataFrame(px, index=idx, columns=["AAA", "BBB"])


def test_log_returns_sum_to_log_price_ratio(prices):
    total = log_returns(prices).sum()
    expected = np.log(prices.iloc[-1] / prices.iloc[0])
    pd.testing.assert_series_equal(total, expected, check_names=False, atol=1e-12)


def test_simple_returns_compound_to_price_ratio(prices):
    r = simple_returns(prices)["AAA"]
    assert compound(r) == pytest.approx(prices["AAA"].iloc[-1] / prices["AAA"].iloc[0])


def test_first_row_is_nan(prices):
    assert simple_returns(prices).iloc[0].isna().all()
    assert log_returns(prices).iloc[0].isna().all()


def test_log_below_simple_for_positive_moves():
    px = pd.DataFrame({"X": [100.0, 150.0, 100.0]})
    s = simple_returns(px)["X"].dropna()
    lg = log_returns(px)["X"].dropna()
    assert s.mean() > 0            # +50% then -33%: simple average says you made money
    assert lg.sum() == pytest.approx(0.0, abs=1e-12)  # log says you are flat


def test_annualise_vol_scales_by_sqrt_periods():
    daily = pd.Series([0.01, -0.01] * 100)
    assert annualise_vol(daily) == pytest.approx(daily.std() * np.sqrt(252))


def test_daily_rate_from_annual_compounds_back():
    annual = pd.Series([5.0, 5.0])  # percent
    d = daily_rate_from_annual(annual)
    assert (1 + d.iloc[0]) ** 252 == pytest.approx(1.05)
