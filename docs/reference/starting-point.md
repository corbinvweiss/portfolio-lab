# The starting point: the code before week 1

This records what the repo contained at the initial commit (`a2bc913`), all of it written
in a Claude session before the course began. Week 2 rebuilds the engine and uses this code
as the oracle it must match; week 4 rebuilds the estimators and allocators; week 6 rebuilds
the signals. Read this to know what the oracle does, not as a description of the current
tool.

Twelve liquid ETFs, three allocators that interpret "risk budget" three different ways,
and a backtest engine built so that lookahead bias is structurally difficult rather than
merely discouraged.

![tearsheet of the three allocators on the twelve-ETF universe](../figures/00-tearsheet.png)

## The three readings of "risk budget"

All three take the same signals and the same covariance matrix, so any difference in the
result is attributable to the risk model alone.

| Allocator | Risk budget means | Needs return forecasts? |
|---|---|---|
| `vol_target` | one number for the whole portfolio: scale gross exposure until predicted vol hits the target | yes, for relative weights |
| `risk_parity` | a per-asset (or per-sleeve) share of total portfolio risk, equalised | no |
| `mean_variance` | a variance cap: maximise `w'mu` subject to `w'Sigma w <= sigma^2` | yes, heavily |

Run all three and compare turnover. Mean-variance trades the most and concentrates the
hardest, because a linear objective against a noisy `mu` is an error-maximiser. That is
the lesson, not a bug.

## Design decisions the original code made

**Signals produce views, not weights.** A signal says "I like this asset"; the allocator
decides what that is worth given the covariance and the budget. Keeping that boundary
clean is what lets you swap either side independently.

**Weights are applied one day late.** A decision made using data through `t` earns the
return from `t` to `t+1`. `tests/test_no_lookahead.py` enforces this two ways: signals
must be causal under truncation, and scrambling returns after a cutoff must not change a
single backtest return before it.

**Weights drift between rebalances.** A "monthly" backtest that quietly rebalances daily
understates turnover and manufactures a rebalancing bonus.

**Storage is append-only snapshots.** Each ingestion run writes
`prices_captured=YYYY-MM-DD.parquet`. Vendors restate history, and you cannot reconstruct
after the fact what the data looked like on a past date. `store.load_prices(as_of=...)`
replays the point-in-time view.

**Synthetic data with a planted answer.** `data/synthetic.py` generates returns from a
known factor structure plus an AR(1) drift. Tests assert the covariance estimators
recover the planted values and that shrinkage beats the sample estimator in small
samples. On real data you cannot distinguish skill from luck from a bug; here you can.

**No database server.** Twelve ETFs of daily history is a few hundred kilobytes. Parquet
on disk with DuckDB as the query layer, all behind `PriceStore`, so swapping in Postgres
later is one new class rather than a refactor.

## Experiments the original README suggested

1. Set `risk.cov_method: sample` and watch mean-variance concentration get worse.
2. Set `regime.enabled: false`. How much of the drawdown reduction was the overlay?
3. Push `backtest.cost_bps` to 25 and see which allocator dies first.
4. Change `backtest.rebalance` to `weekly`. Does the extra responsiveness pay for the
   turnover?
5. Add `budget.sleeve_budgets` and give `risk_parity` an explicit per-sleeve risk split.

## What it did not have

No slippage or market impact model, no borrow costs or financing, no dividend or tax
treatment beyond whatever the vendor's adjusted prices assume, no survivorship-bias
handling (the ETF sleeve was hardcoded and current), and a single in-sample pass with no
walk-forward parameter selection. The syllabus turns each of these into a week.
