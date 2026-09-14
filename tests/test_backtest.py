"""End-to-end behaviour of the engine."""
import numpy as np
import pandas as pd

from portfolio_lab.allocate import (
    MeanVarianceAllocator, RiskBudget, RiskParityAllocator, VolTargetAllocator,
)
from portfolio_lab.backtest.costs import LinearCostModel
from portfolio_lab.backtest.engine import rebalance_dates, run_backtest
from portfolio_lab.signals.momentum import TimeSeriesMomentum

BUDGET = RiskBudget(target_vol=0.10, max_gross=1.0, max_weight=0.35, long_only=True)


def signal_fn(px):
    return TimeSeriesMomentum().compute(px)


def test_all_allocators_run(synth):
    prices, _ = synth
    for alloc in (VolTargetAllocator(), RiskParityAllocator(), MeanVarianceAllocator()):
        res = run_backtest(prices, signal_fn, alloc, BUDGET, warmup=400)
        assert len(res.returns) > 500
        assert res.returns.notna().all()
        assert np.isfinite(res.metrics["sharpe"])


def test_realised_vol_lands_near_the_target(synth):
    """Not exact -- that gap is the lesson -- but it should be in the ballpark."""
    prices, _ = synth
    res = run_backtest(prices, signal_fn, RiskParityAllocator(), BUDGET, warmup=400)
    realised = res.returns.std() * np.sqrt(252)
    assert 0.4 * BUDGET.target_vol < realised < 2.2 * BUDGET.target_vol


def test_costs_reduce_returns(synth):
    prices, _ = synth
    free = run_backtest(prices, signal_fn, VolTargetAllocator(), BUDGET,
                        warmup=400, cost_model=LinearCostModel(0.0))
    pricey = run_backtest(prices, signal_fn, VolTargetAllocator(), BUDGET,
                          warmup=400, cost_model=LinearCostModel(50.0))
    assert pricey.returns.sum() < free.returns.sum()


def test_higher_rebalance_frequency_raises_turnover(synth):
    prices, _ = synth
    monthly = run_backtest(prices, signal_fn, VolTargetAllocator(), BUDGET,
                           warmup=400, rebalance="monthly")
    quarterly = run_backtest(prices, signal_fn, VolTargetAllocator(), BUDGET,
                             warmup=400, rebalance="quarterly")
    assert monthly.costs.sum() > quarterly.costs.sum()


def test_rebalance_dates_are_subset_of_index(synth):
    prices, _ = synth
    for rule in ("weekly", "monthly", "quarterly"):
        dates = rebalance_dates(prices.index, rule)
        assert set(dates).issubset(set(prices.index))
        assert len(dates) > 0


def test_weights_never_breach_the_budget(synth):
    prices, _ = synth
    res = run_backtest(prices, signal_fn, MeanVarianceAllocator(), BUDGET, warmup=400)
    assert res.targets.max().max() <= BUDGET.max_weight + 1e-9
    assert res.targets.abs().sum(axis=1).max() <= BUDGET.max_gross + 1e-9
    assert (res.targets >= -1e-12).all().all()
