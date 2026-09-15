"""The test that matters most.

If future data can leak into a decision, every other result in the repo is
meaningless. Two independent checks:

1. Signals are causal: truncating the price history must not change any score
   that was already computable. A centred rolling window or a backfill fails
   this immediately.

2. The engine is causal: scrambling returns AFTER a cutoff date must leave the
   backtest's returns before that date bit-for-bit identical.
"""
import numpy as np
import pandas as pd

from portfolio_lab.allocate import RiskBudget, VolTargetAllocator
from portfolio_lab.backtest.engine import run_backtest
from portfolio_lab.signals.momentum import CrossSectionalMomentum, TimeSeriesMomentum
from portfolio_lab.signals.regime import VolTrendRegime

BUDGET = RiskBudget(target_vol=0.10, max_gross=1.0, max_weight=0.35, long_only=True)


def test_signals_are_causal(synth):
    prices, _ = synth
    cutoff = 1000
    for sig in (TimeSeriesMomentum(), CrossSectionalMomentum()):
        full = sig.compute(prices).iloc[:cutoff]
        truncated = sig.compute(prices.iloc[:cutoff])
        pd.testing.assert_frame_equal(full, truncated, check_exact=False, atol=1e-12)


def test_regime_overlay_is_causal(synth):
    prices, _ = synth
    cutoff = 1000
    overlay = VolTrendRegime()
    full = overlay.compute(prices).iloc[:cutoff]
    truncated = overlay.compute(prices.iloc[:cutoff])
    pd.testing.assert_series_equal(full, truncated, check_exact=False, atol=1e-12)


def test_engine_ignores_the_future(synth):
    """Corrupt the future; the past must not move."""
    prices, _ = synth
    cutoff = 1200
    rng = np.random.default_rng(99)

    corrupted = prices.copy()
    tail = corrupted.iloc[cutoff:]
    shock = pd.DataFrame(
        rng.normal(1.0, 0.25, size=tail.shape), index=tail.index, columns=tail.columns
    )
    corrupted.iloc[cutoff:] = (tail * shock).to_numpy()

    def signal_fn(px):
        return TimeSeriesMomentum().compute(px)

    kwargs = {"warmup": 400, "rebalance": "monthly", "cov_window": 252}
    clean = run_backtest(prices, signal_fn, VolTargetAllocator(), BUDGET, **kwargs)
    dirty = run_backtest(corrupted, signal_fn, VolTargetAllocator(), BUDGET, **kwargs)

    boundary = prices.index[cutoff]
    a = clean.returns.loc[clean.returns.index < boundary]
    b = dirty.returns.loc[dirty.returns.index < boundary]
    pd.testing.assert_series_equal(a, b, check_exact=False, atol=1e-12)


def test_weights_are_applied_one_day_late(synth):
    """A weight decided at t must not earn t's return."""
    prices, _ = synth

    def signal_fn(px):
        return TimeSeriesMomentum().compute(px)

    res = run_backtest(prices, signal_fn, VolTargetAllocator(), BUDGET,
                       warmup=400, rebalance="monthly")
    first_decision = res.targets.index[0]
    held = res.weights.loc[first_decision]
    target = res.targets.loc[first_decision]
    # On the decision day itself we are still holding the OLD book, not the new one.
    assert not np.allclose(held.to_numpy(), target.to_numpy()), (
        "weights were applied on the decision day -- that is lookahead"
    )
