# portfolio-lab: learning spec and course roadmap

Date: 2026-09-14. Status: draft for Corbin's review.

## 1. Purpose

portfolio-lab exists so that Corbin learns institutional portfolio management by building
the tooling himself. The code is disposable; the durable output is a set of written lessons
in `docs/lessons/`, each recording a concept, the experiment that tested it, what the numbers
showed, and the mistakes made along the way.

At the end of the course the repo should be a mature research tool that:

- ingests survivorship-bias-free equity data plus bonds and international proxies into
  point-in-time snapshots;
- runs backtests that are structurally protected against lookahead and that report
  overfitting-adjusted statistics;
- models financing (cash, margin, borrow, futures carry) and prices basic derivatives;
- attributes performance against a benchmark, before and after tax;
- given a desired risk level, recommends exposures under three framings (efficient
  frontier, policy portfolio, goal-based glide path) and explains where they disagree.

### Interview summary (2026-09-14)

| Question | Answer |
|---|---|
| Background | Math/CS double major; a year of .NET + React dashboards; some personal investing; no quant work |
| Purpose | Purely educational; no real money |
| Time | 5-10 hrs/week for about 3 months, so a 12-week course |
| Protect if scope shrinks | Documentation and lessons |
| Data | Willing to pay $30-60/month for historical index constituents |
| Math depth | Derive the key results (Markowitz, CAPM, Ledoit-Wolf, Kelly), not just cite them |
| Lesson format | One markdown lesson + lab per milestone |
| Derivatives | Exposure and financing, plus pricing basics (Black-Scholes, greeks, parity, futures fair value) |
| Work split | Corbin writes all code; Claude is the professor: direction, derivations, review |
| Recommender | All three framings, compared on the same inputs |
| Existing code | Corbin rebuilds the core engine as lesson 1 to own the invariants, then extends |
| Extra topics | Performance attribution; taxes and after-tax returns |

## 2. Operating model

**Roles.** Claude sets each week's brief, derives the math, specifies acceptance criteria and
test ideas, and reviews the implementation. Corbin implements everything, runs the
experiments, and writes the lesson. Claude does not write production code unless Corbin
asks for it explicitly for that task.

**Weekly loop.**

1. Brief: Claude posts the lesson's concept, derivation, reading, lab spec, and acceptance
   criteria.
2. Build: Corbin implements under TDD. Every invariant the lesson introduces gets a test
   before the feature.
3. Review: Claude reviews the diff against the acceptance criteria and probes understanding
   with questions.
4. Write-up: Corbin writes `docs/lessons/NN-topic.md`. The milestone is done when the lesson
   is written, not when the code passes.

**Lesson template** (`docs/lessons/NN-topic.md`):

```
# NN. Title
## The question this lesson answers
## Concept and derivation            (in Corbin's words; the math, not a link to it)
## The experiment                    (config, data, what was varied)
## What the numbers showed           (a table or two; the chart if one matters)
## What went wrong and what I'd do differently
## Pitfalls to remember
## Reading
```

**Definition of done for the course.** Twelve lessons written. `pytest` green. The
capstone report (lesson 12) produced from a config file plus a git SHA.

**Planning granularity.** This document is the course-level spec. Each week gets its own
brief (the lab spec expanded into steps and tests) at the start of that week, so the plan
can absorb what the previous week taught.

## 3. Where the code is today

Baseline verified 2026-09-14: 29 tests pass, `plab run --config configs/synthetic.yaml`
produces metrics for all three allocators, and no real data has ever been ingested. The
package is about 1,900 lines: 12 hardcoded ETFs, momentum signals, sample/EWMA/Ledoit-Wolf
covariance, three allocators, a walk-forward engine with lookahead tests, and an
append-only snapshot store.

| Learning goal | Current state | Gap |
|---|---|---|
| Backtesting mechanics | Walk-forward engine with one-day lag, drifting weights, linear costs | Sound, but not Corbin's. Rebuild as lessons 1-2. No benchmark, no risk-free rate; Sharpe is CAGR/vol with rf=0 |
| Lookahead | Two structural tests (causal signals; scrambled-future engine) | Good foundation. Missing point-in-time universe membership and data-availability lag; as-of replay never exercised on real snapshots |
| Survivorship bias | 12 hardcoded, currently listed ETFs | Absent. Needs a `Universe` with membership-by-date and delisting returns |
| Overfitting | Single in-sample pass | Absent. Needs walk-forward selection, purged CV, deflated Sharpe, a trial ledger |
| Risk calculation | Sample/EWMA/Ledoit-Wolf, risk contributions, vol target | Ledoit-Wolf imported from sklearn, not derived. No factor risk model, VaR/CVaR, or sleeve decomposition |
| Financing | None: `max_gross=1.0`, `long_only=True`, no cash leg | Absent. Needs cash/T-bill leg, margin interest, borrow cost, futures carry |
| Futures | None | Absent |
| Options | None | Absent |
| Shorts | Latent: `apply_constraints` can clip negatives; nothing uses it | Needs borrow cost, short rebate, dollar-neutral construction |
| International stocks and bonds | ETF proxies only | Proxies are fine to start. Missing single names, currency exposure, bond math |
| Risk-level recommendations | Allocators size to a target vol | Nothing maps "desired risk" to an allocation with a rationale |
| Attribution | CAGR, vol, Sharpe, drawdown, turnover | No benchmark, tracking error, information ratio, Brinson, or factor regression |
| Taxes | None | Absent |
| Lesson documentation | README and NOTES.md, both Claude-written | The actual deliverable. `docs/lessons/` does not exist |

**Architectural pressure points the roadmap must relieve.**

- `run_backtest` assumes every column is a tradeable asset with a price every day. Single
  names that enter, exit, or delist break that.
- `RiskBudget` and `apply_constraints` have no cash concept. Weights are shares of NAV
  with no explicit residual, so leverage and financing have nowhere to attach.
- `experiment.py` hard-wires `SLEEVES` from `universe.py`. Sleeve metadata must come from
  the data layer once the universe is dynamic.
- `metrics.summarise` takes no benchmark or risk-free input.

## 4. What the institutions teach

Condensed from the research pass. Full citations are in section 9.

**Academic (Yale, Harvard, Princeton, MIT).** The theory sequence is stable across
schools: return math and utility, mean-variance and diversification, CAPM/APT and the
stochastic discount factor, market efficiency and its evidence, then fixed income and
derivatives. MIT puts estimation and inference last (15.450); for someone who implements
everything, estimation must come early because covariance is the engine's contract.
Swensen's endowment model (policy portfolio, equity bias, functional diversification,
disciplined rebalancing, fee skepticism) reads best after mean-variance so its rules are
seen as approximations, not axioms. Campbell and Viceira show long-horizon investors should
hedge changes in investment opportunities, and that mean reversion implies conservative
long-horizon investors hold more equity, which is the theory behind glide paths. Harvard
Management Company expresses its portfolio as betas and alphas rather than asset classes,
which is exactly what `RiskBudget` is reaching for.

**Backtesting rigor (Lopez de Prado, Bailey, Harvey and Liu).** Most backtest failures are
data handling and testing errors, not model errors. The order of defence is: survivorship
(data) before lookahead and purging (splits) before multiple testing (inference).
Survivorship alone overstates returns by roughly 1.4% per year and grows with sample
length. A new factor needs a t-statistic above 3 to survive the multiple-testing haircut.

**Practitioner (Vanguard, Morningstar, Bogle, Sharpe).**

- Cost is the one lever fully under the investor's control, and expense ratio is the single
  best ex-ante predictor of fund success. Star ratings flag the bottom and cannot pick the
  top.
- Alpha is zero-sum before costs (Sharpe's arithmetic). A strategy needs a losing
  counterparty.
- Rebalancing is risk control, not return enhancement. Frequency barely matters; never
  rebalancing lets a 60/40 drift to 84% equity.
- The Brinson "90%" finding is about time-series variance, not the level of returns.
  Misquoting it is the classic student error.
- Investor returns lag fund returns by about 1.2 points per year (Mind the Gap). Read it
  as "flows matter", not "investors are stupid".
- Hedge the currency on foreign bonds (unhedged FX is a fifth of the risk); equity hedging
  is optional. Most equity diversification benefit arrives by 20% ex-US.
- Asset location and tax-loss harvesting are real but second-order: tens of basis points.

## 5. The course

Twelve weeks in four phases. Each week is one lesson and one lab. Data grows from a handful
of tickers over ten years (free) to S&P 500 constituents over 25 years (paid) to
international and bond proxies. The hour estimates assume 5-10 hours per week; the heavier
weeks are marked.

### Phase A. Foundations on a handful of tickers (weeks 1-4, free data)

**Week 1. Data integrity and return math.**
Concept: price vs total return, simple vs log returns, annualisation, why adjusted closes
get restated, point-in-time snapshots. Derivation: compounding identities; why
`Sharpe = mean/std * sqrt(252)` is an approximation.
Lab: ingest four ETFs (SPY, EFA, IEF, GLD) and four large-cap stocks, 2015-2025, from a
free vendor into the snapshot store. Take two snapshots a week apart and diff them. Add a
risk-free series (FRED DTB3) to the store. Write the `Universe` seed: a table of
`ticker, name, sleeve, listed_from, listed_to`.
Acceptance: the store round-trips; `as_of` replay returns the earlier snapshot; a test
proves the curated view picks the latest capture per key.

**Week 2. The backtest engine, rebuilt.** (heavy)
Concept: the pending-order convention, drift between rebalances, turnover and linear
costs, the risk-free leg, benchmark-relative returns. Derivation: why weights must be
renormalised by the realised portfolio return; why daily rebalancing manufactures a bonus.
Lab: rewrite `run_backtest` from scratch in a new module without reading the old one.
Add an explicit cash residual earning the T-bill rate. Rebuild the lookahead tests
(causal signals under truncation; scrambled future leaves the past bit-identical; weights
applied one day late). Use the old engine as an oracle: on the synthetic data the two must
agree to 1e-12 when cash earns zero. Then delete the old engine.
Acceptance: the oracle test passes, then is removed with the old engine; `summarise` takes
`rf` and `benchmark` and reports excess return, tracking error, and information ratio.

**Week 3. Mean-variance, diversification, CAPM.**
Concept: utility and risk aversion, the efficient frontier, two-fund separation, the
tangency portfolio, CAPM as an equilibrium consequence, why estimation error makes the
optimiser an error maximiser. Derivation: Lagrangian for min-variance with a return
target; closed-form frontier; CAPM from the tangency condition.
Lab: frontier plotter on the eight tickers; closed-form vs SLSQP agreement; bootstrap the
sample means and watch the tangency weights swing. Estimate each ticker's beta and alpha
against SPY and report t-statistics.
Acceptance: analytic and numeric frontiers agree to 1e-6; a test shows the sample
tangency portfolio's out-of-sample Sharpe is below the equal-weight portfolio's on
resampled data.

**Week 4. Estimating risk.** (heavy)
Concept: sample covariance's eigenvalue bias, EWMA, Ledoit-Wolf shrinkage, PSD repair,
risk contributions, vol targeting, risk parity, VaR and CVaR.
Derivation: Ledoit-Wolf constant-correlation shrinkage intensity from first principles
(replace the sklearn import with Corbin's own implementation and test them against each
other); risk parity as the stationary point of `0.5 w'Sw - sum b_i log w_i`.
Lab: rebuild the estimator registry and the three allocators. Synthetic data with a
planted factor structure must recover the planted covariance; shrinkage must beat sample
in small samples. Add VaR/CVaR to `summarise`.
Acceptance: hand-written Ledoit-Wolf matches sklearn to 1e-8; risk-parity risk
contributions are equal to 1e-6; the predicted-vs-realised vol gap is plotted and
discussed in the lesson.

### Phase B. Rigor on the S&P 500 (weeks 5-7, paid data begins)

**Week 5. Survivorship bias and point-in-time universes.** (heavy)
Concept: survivorship, look-ahead in membership, delisting returns, data-availability
lag. Reading: Elton-Gruber-Blake; Brown-Goetzmann-Ibbotson-Ross.
Lab: subscribe to Norgate Platinum (or Sharadar SEP if Mac-only blocks the Norgate
updater). Extend the store with an `index_membership` table (`index, ticker, from, to`)
and a `delistings` table. Make `Universe.members(as_of)` the only way the engine learns
what is tradeable, and make the engine tolerate assets that enter, exit, and have missing
prices. Using the existing 12-1 momentum signal (the registry is rebuilt in week 6), run
today's constituents vs point-in-time constituents, 1995-2025.
Acceptance: a test with a synthetic universe where a loser delists proves the two runs
differ and the PIT run is lower; the lesson records the measured gap against the
literature's 1-1.5% per year.

**Week 6. Signals as views; factor models.**
Concept: momentum and value as views, cross-sectional z-scoring, blending, Fama-French
three- and five-factor regressions, alpha t-statistics, the t > 3 bar.
Reading: AQR "Fact, Fiction and Momentum Investing"; Dimensional's three-part test for a
factor (sensible, robust, cheap to capture).
Lab: rebuild the signal registry; add a value signal (book-to-market from the vendor's
fundamentals, lagged by the reporting delay). Regress each strategy's returns on Ken
French factors and report loadings and alpha.
Acceptance: signals pass the truncation test; the value signal is lagged by at least the
filing delay and a test enforces it; the lesson reports factor loadings for each
allocator.

**Week 7. Overfitting and multiple testing.** (heavy)
Concept: walk-forward parameter selection, purged k-fold with embargo, combinatorial
purged CV, the deflated Sharpe ratio, probability of backtest overfitting, the trial
ledger. Derivation: the deflated Sharpe's expected maximum under N trials; why
overlapping labels leak.
Lab: sweep momentum lookback and skip over a grid; log every trial; compute PBO and the
deflated Sharpe of the best. Implement purged CV as a utility the engine can call.
Acceptance: a test shows that on pure noise the best-of-grid raw Sharpe is positive and
the deflated Sharpe is not; the trial ledger is a committed artifact.

### Phase C. Instruments and financing (weeks 8-10)

**Week 8. Cash, leverage, shorts, and the cost of money.**
Concept: the cash leg, margin interest, borrow cost and short rebate, dollar-neutral and
beta-neutral construction, leverage aversion, the Kelly criterion. Derivation: Kelly for
a single risky asset; the AQR leverage-aversion argument for risk parity.
Lab: give `RiskBudget` a financing model (`cash_rate`, `margin_spread`, `borrow_bps`).
Run long-short momentum at gross 1.3/0.3 and 2.0; run risk parity levered to the equity
vol. Show each result with and without financing.
Acceptance: with all rates zero the engine reproduces week 7 results bit-identically; a
test proves a short position pays borrow and earns rebate; the lesson shows where
leverage stops paying.

**Week 9. Futures and bonds.**
Concept: cost of carry and fair value, continuous contracts and roll yield, notional vs
margin, trend following on futures; duration, convexity, yield-to-return decomposition;
international bonds and currency hedging.
Lab: build continuous ES and ZN series (Stooq free, or Norgate Futures if budget allows)
and verify fair value against spot and the T-bill rate. Add a `Futures` instrument type
whose position is notional with margin financing. Add bond ETF proxies (AGG, BNDX, hedged
and unhedged) and decompose their returns into carry and price. Add a currency-hedged
return calculation for an EFA sleeve.
Acceptance: a synthetic contract with known carry prices to fair value; the lesson shows
the hedged vs unhedged bond volatility gap and compares it to Vanguard's finding.

**Week 10. Options.**
Concept: put-call parity, risk-neutral pricing, Black-Scholes, the greeks, implied vs
realised volatility, how an overlay changes the return distribution. Derivation:
Black-Scholes from the risk-neutral expectation; parity from no-arbitrage.
Lab: pricer with tests for parity and known limits; greeks by analytic formula and finite
difference; a protective-put and a covered-call overlay on SPY priced with VIX as the
volatility input. Report the change in skew, drawdown, and average return.
Acceptance: parity holds to 1e-10; analytic and numeric greeks agree; the lesson explains
why the protective put has a negative expected return and when it is still worth buying.

### Phase D. Portfolio management (weeks 11-12)

**Week 11. Attribution and taxes.**
Concept: benchmark selection, tracking error and information ratio, Brinson allocation
and selection effects, factor attribution, active share; tax lots, realised vs unrealised
gains, loss harvesting, asset location.
Lab: Brinson attribution of each allocator against a 60/40 benchmark by sleeve; a
tax-lot ledger with a harvesting rule; after-tax equity curves at two bracket assumptions.
Acceptance: allocation plus selection plus interaction sums to the active return to 1e-10;
the harvesting uplift is reported and compared to Vanguard's 0.5-4% range.

**Week 12. The recommender and the capstone.** (heavy)
Concept: the three framings of "how much risk". Efficient frontier with a vol or drawdown
target; Swensen policy portfolio with corridor rebalancing and an investment policy
statement; goal-based glide path from horizon and liabilities, with Campbell-Viceira's
intertemporal hedging as the theory. Capital-market assumptions as inputs, not forecasts.
Lab: `plab recommend --risk <level>` that runs all three framings on the same inputs and
writes a report: the proposed exposures by sleeve, the rationale, where the framings
disagree and why, and the backtested behaviour of each with overfitting-adjusted
statistics.
Acceptance: the report is generated from a config plus a git SHA; the capstone lesson
reads as a standalone document a peer could learn from.

### Sequencing rationale

- Rigor (weeks 5-7) comes before instruments (weeks 8-10) so every later experiment is
  run on a survivorship-free universe with a trial ledger.
- Estimation (week 4) precedes single names (week 5) because covariance is the engine's
  contract and must be trusted before the universe grows.
- Financing (week 8) precedes futures (week 9) because a future is a financed position.
- The endowment model and the glide path land last so they are seen as approximations to
  mean-variance and Campbell-Viceira rather than as rules.

### If time runs short

Protect the lessons. Weeks 9 and 10 can shrink to pricing plus a single overlay each, and
week 11's tax module can drop to a tax-lot ledger without harvesting. Do not drop weeks 5
and 7: without them every number in the capstone is suspect.

## 6. Data roadmap

| Weeks | Universe | Source | Cost |
|---|---|---|---|
| 1-4 | 4 ETFs + 4 stocks, 2015-2025; FRED DTB3; Ken French factors | Tiingo free tier or EODHD free tier; `fredapi`; `pandas_datareader` | $0 |
| 5-8 | S&P 500 constituents with membership and delistings, 1995-2025 | Norgate Platinum (about $53/month on annual plan; needs the Windows updater, so a VM on Mac) or Sharadar SEP + SP500 table via Nasdaq Data Link | $40-60/month |
| 9-12 | ES/ZN continuous, bond ETFs, EFA/EEM, hedged vs unhedged proxies, VIX | Stooq free continuous series (unadjusted; Norgate Futures at $270/year if adjusted is wanted); FRED VIXCLS | $0-25/month |

Every vendor pull lands as a dated snapshot in the existing `PriceStore`, so all later
work is offline and replayable. Options history is not free; week 10 prices options from
VIX rather than ingesting quotes.

## 7. Architecture evolution

The stage boundaries stay as they are: prices, signals, covariance, allocator, engine,
report, with three registries. Planned changes by week:

- Week 1: `Universe` table in the store; `rf` series.
- Week 2: engine rewritten; explicit cash leg; `summarise(rf, benchmark)`.
- Week 4: `ESTIMATORS` rebuilt; VaR/CVaR.
- Week 5: `index_membership` and `delistings` tables; `Universe.members(as_of)`; engine
  tolerates entry/exit and missing prices; `SLEEVES` moves from a module constant to the
  data layer.
- Week 6: fundamentals table with a reporting-lag column.
- Week 7: `research/` package: trial ledger, purged CV, deflated Sharpe, PBO.
- Week 8: `Financing` model on `RiskBudget`; `long_only=False` exercised.
- Week 9: `Instrument` abstraction (cash equity, ETF, future) so the engine finances
  positions by type.
- Week 10: `derivatives/` package: pricer, greeks, overlays as a post-allocator step.
- Week 11: `attribution/` and `tax/` packages.
- Week 12: `recommend/` package and `plab recommend`.

Invariants from `CLAUDE.md` remain in force throughout: no lookahead, weights drift,
covariance annualised, signals emit views, all allocators end in `apply_constraints`.

## 8. Alternatives considered

- **Keep and extend without a rebuild.** Faster, but Corbin would be reading Claude's
  invariants rather than owning them. Rejected per the interview.
- **Notebook-first course.** Better for plots, worse for the durable record and for tests.
  Rejected; notebooks may be used as scratch under `notebooks/`.
- **Breadth-first (every instrument on ETFs) before rigor.** More fun early, but every
  later number would be untrustworthy. Rejected; rigor sits in the middle so the first
  four weeks still feel productive.
- **Free data only, reconstructing S&P 500 membership from Wikipedia.** Possible, but
  ticker renames and missing delisted prices would consume the survivorship week itself.
  Rejected given the stated budget.

## 9. Sources

Academic: Swensen, *Pioneering Portfolio Management* and *Unconventional Success*;
Dimmock, Wang and Yang, "The Endowment Model and Modern Portfolio Theory" (NBER w25559);
Shiller, ECON 252 (oyc.yale.edu/economics/econ-252); Campbell, *Financial Decisions and
Markets*; Campbell and Viceira, *Strategic Asset Allocation*; Malkiel, *A Random Walk Down
Wall Street*; Princeton ECO 362, FIN 501, ORF 435; MIT OCW 15.401, 15.433, 15.450; CFA
Level III portfolio management learning outcomes.

Rigor: Lopez de Prado, *Advances in Financial Machine Learning*; Bailey and Lopez de Prado,
"The Deflated Sharpe Ratio" (SSRN 2460551); Bailey, Borwein, Lopez de Prado and Zhu, "The
Probability of Backtest Overfitting" (SSRN 2326253); Harvey and Liu, "Backtesting" (JPM
2015) and Harvey, Liu and Zhu, "...and the Cross-Section of Expected Returns" (RFS 2016);
Brown, Goetzmann, Ibbotson and Ross (RFS 1992); Elton, Gruber and Blake (RFS 1996).

Factors: Asness, Moskowitz and Pedersen, "Value and Momentum Everywhere" (JF 2013); Asness,
Frazzini, Israel and Moskowitz, "Fact, Fiction and Momentum Investing" (JPM 2014); Asness,
Frazzini and Pedersen, "Leverage Aversion and Risk Parity" (FAJ 2012).

Practitioner: Vanguard, "Principles for Investing Success", "Advisor's Alpha", "Best
Practices for Portfolio Rebalancing", "Global Equity Investing: Diversification and
Sizing", "Going Global with Bonds", "Asset Location for Equity", VCMM forecasts; Morningstar,
"Mind the Gap 2025", Kinnel "Fund Fees Predict Future Success or Failure", Style Box and
Factor Profile methodologies, safe withdrawal rate research; Blake and Morey on star
ratings; Bogle's cost matters hypothesis; Sharpe, "The Arithmetic of Active Management".

Data: Norgate (norgatedata.com), Sharadar via Nasdaq Data Link, EODHD, Tiingo, Stooq,
FRED (DTB3, DGS10, SOFR, VIXCLS), Ken French Data Library.
