# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Course context (syllabus, weekly briefs, lessons, docs rules) lives in `docs/SYLLABUS.md`
and `docs/specs/`; this file covers only the code.

```bash
pip install -e ".[dev,ingest]"          # ingest extra pulls in yfinance

pytest                                   # full suite (~seconds, synthetic data only)
pytest tests/test_no_lookahead.py        # the suite that matters most
pytest tests/test_allocators.py::test_risk_parity_ignores_views -x
pytest -k causal

ruff check src tests                     # line-length 100, target py310

plab run --config configs/synthetic.yaml # no network, no ingested data required
plab run --config configs/baseline.yaml --outdir runs --no-chart
plab ingest --start 2005-01-01           # writes a dated snapshot to data/raw/
plab snapshots                           # list captured snapshot dates
```

`plab run` writes `<name>_metrics.csv` and (unless `--no-chart`) `<name>_tearsheet.png`
into `--outdir` (default `runs/`, gitignored).

Tests never touch the network or `data/` — `tests/conftest.py` builds prices from
`data/synthetic.py`, and store tests use `InMemoryStore` or a tmp dir.

## Architecture

The pipeline is one linear flow, and each stage is swappable because the stage
boundaries are typed contracts rather than shared DataFrames:

```
prices (wide: index=date, columns=ticker)
  -> signal_fn      -> scores, same shape as prices    (signals/base.Signal)
  -> cov_mod.estimate -> ANNUALISED covariance matrix   (risk/covariance.py)
  -> allocator      -> weights                          (allocate/base.Allocator + RiskBudget)
  -> run_backtest   -> BacktestResult                   (backtest/engine.py)
  -> build_tearsheet                                    (report/tearsheet.py)
```

`experiment.py` is the only place that wires the stages together: `run_experiment(cfg)`
reads a YAML dict, builds the signal blend, regime overlay, `RiskBudget` and cost model,
then loops over `cfg["allocators"]` calling `run_backtest` once per allocator with
*identical* signals and covariance. That invariant is what makes cross-allocator
comparison meaningful — keep it when adding features.

`cli.py` is a thin argparse shell over `experiment.run_experiment` plus report writing.

### Three registries are the extension points

| Registry | Location | Adding an entry |
|---|---|---|
| `SIGNAL_REGISTRY` | `experiment.py` | subclass `Signal`, register the YAML key; per-signal `weight` is popped by `build_signal_fn` and the rest passed as kwargs |
| `ALLOCATORS` | `allocate/__init__.py` | subclass `Allocator`; `experiment.py` special-cases `risk_parity` to receive `sleeve_map=SLEEVES` |
| `ESTIMATORS` | `risk/covariance.py` | must return an annualised frame; `estimate()` wraps every result in `_nearest_psd` |

`REBALANCE_RULES` in `backtest/engine.py` is a fourth, smaller one.

### Invariants that tests enforce — do not break these

**No lookahead.** A decision made on day `t` sets `pending`, which the engine applies at
the *start* of day `t+1`. `signal_fn` is called once on the full history but the engine
only ever reads row `t`, so a non-causal signal (centred rolling window, `bfill`,
full-sample fit) is a caller bug that `tests/test_no_lookahead.py` catches two ways:
truncating history must not change already-computed scores, and scrambling returns after
a cutoff must leave earlier backtest returns bit-identical.

**Weights drift between rebalances** rather than being silently re-set daily — step 3 of
the engine loop renormalises `w` by the realised portfolio return. Removing that would
manufacture a rebalancing bonus and understate turnover.

**Covariance is always annualised** (×252) at the estimator boundary. `portfolio_vol`,
`predicted_vol` and `RiskBudget.target_vol` all assume annual units.

**Signals emit views, not weights.** Scores are cross-sectionally z-scored (`blend`,
`zscore_cross_section`); position sizing belongs to the allocator. `MeanVarianceAllocator`
converts a z-score to an expected return via `view_scale`.

**All allocators end in `apply_constraints(w, budget)`** — long-only clip, per-asset
`max_weight` box, then gross rescale. Tests assert no run breaches the budget.

### Storage

Everything persistent goes through the `PriceStore` ABC (`data/store.py`); no module
calls `duckdb.connect` directly except the store. Writes are **append-only dated
snapshots** (`data/raw/prices_captured=YYYY-MM-DD.parquet`); `_rebuild_curated` collapses
them to `data/curated/prices.parquet` (latest capture wins per `(date, ticker)`), which is
what backtests read by default. `load_prices(as_of=date(...))` replays only snapshots
captured on or before that date — the point-in-time view. Long-format schema is
`date, ticker, close, volume` with `close` total-return adjusted; `_validate_long_prices`
rejects duplicate keys and non-positive closes.

`data/` is gitignored: the ingestion script, not the parquet, is the reproducible artifact.

### Config contract

A run is reproducible from a YAML file plus a git SHA. `configs/baseline.yaml` is the
annotated reference and documents the legal values for `risk.cov_method`,
`backtest.rebalance` and `data.source`. `configs/synthetic.yaml` is the offline path —
prefer it when iterating, since `source: store` fails with `FileNotFoundError` until
`plab ingest` has run and vendor endpoints are often blocked (see `docs/reference/data-sources.md`).

`experiment.py` reads config keys with `.get(...)` defaults throughout; a new knob needs a
default there as well as a line in both config files.

### Charts

`report/style.py` holds a fixed, validated categorical palette. Take slots from the front
in order; never cycle or shuffle. Three slots fall below 3:1 contrast on the surface, so
charts using them must carry direct labels — identity is never carried by colour alone.
