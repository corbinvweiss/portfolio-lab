"""Config -> results. One function so a run is reproducible from a YAML file."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from .allocate import ALLOCATORS, RiskBudget
from .backtest.costs import LinearCostModel
from .backtest.engine import run_backtest
from .data.store import ParquetDuckStore
from .data.synthetic import make_synthetic_prices
from .data.universe import SLEEVES, TICKERS
from .signals.base import blend
from .signals.momentum import CrossSectionalMomentum, TimeSeriesMomentum
from .signals.regime import VolTrendRegime

SIGNAL_REGISTRY = {"ts_momentum": TimeSeriesMomentum, "xs_momentum": CrossSectionalMomentum}


def load_config(path: str | Path) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)


def load_prices(cfg: dict, store=None) -> pd.DataFrame:
    src = cfg["data"].get("source", "store")
    if src == "synthetic":
        long, _ = make_synthetic_prices(TICKERS, n_days=cfg["data"].get("n_days", 2520))
        return long.pivot(index="date", columns="ticker", values="close").pipe(
            lambda d: d.set_axis(pd.to_datetime(d.index)).rename_axis(None, axis=1)
        ).sort_index()
    store = store or ParquetDuckStore()
    as_of = cfg["data"].get("as_of")
    return store.load_prices(as_of=date.fromisoformat(as_of) if as_of else None)


def build_signal_fn(cfg: dict):
    specs = cfg.get("signals", {})
    instances, weights = {}, {}
    for key, params in specs.items():
        params = dict(params)
        weights[key] = params.pop("weight", 1.0)
        instances[key] = SIGNAL_REGISTRY[key](**params)

    def signal_fn(prices: pd.DataFrame) -> pd.DataFrame:
        scores = {k: sig.compute(prices) for k, sig in instances.items()}
        return blend(scores, weights) if len(scores) > 1 else next(iter(scores.values()))

    return signal_fn


def build_regime_fn(cfg: dict):
    rc = cfg.get("regime", {})
    if not rc.get("enabled"):
        return None
    overlay = VolTrendRegime(
        vol_window=rc.get("vol_window", 21),
        vol_ref_window=rc.get("vol_ref_window", 252),
        trend_window=rc.get("trend_window", 200),
        floor=rc.get("floor", 0.25),
    )
    return overlay.compute


def run_experiment(cfg: dict, store=None) -> dict:
    prices = load_prices(cfg, store=store)
    signal_fn = build_signal_fn(cfg)
    regime_fn = build_regime_fn(cfg)

    b = cfg["budget"]
    budget = RiskBudget(
        target_vol=b.get("target_vol", 0.10),
        max_gross=b.get("max_gross", 1.0),
        max_weight=b.get("max_weight", 0.35),
        long_only=b.get("long_only", True),
        sleeve_budgets=b.get("sleeve_budgets"),
    )
    bt = cfg.get("backtest", {})
    cost_model = LinearCostModel(cost_bps=bt.get("cost_bps", 5.0))

    results = {}
    for name in cfg["allocators"]:
        cls = ALLOCATORS[name]
        allocator = cls(sleeve_map=SLEEVES) if name == "risk_parity" else cls()
        results[name] = run_backtest(
            prices, signal_fn, allocator, budget,
            cov_method=cfg["risk"].get("cov_method", "shrunk"),
            cov_window=cfg["risk"].get("cov_window", 252),
            warmup=bt.get("warmup", 300),
            rebalance=bt.get("rebalance", "monthly"),
            cost_model=cost_model,
            regime_fn=regime_fn,
        )
    return results
