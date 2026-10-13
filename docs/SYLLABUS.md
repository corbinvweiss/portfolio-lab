# portfolio-lab syllabus

Twelve weeks, four phases. This is the index of a self-directed course in institutional
portfolio management, worked through by building the research tool week by week.

**Who writes what.** Two authors share the work. Claude, Anthropic's AI model, acts as the
instructor: it writes each week's brief (the concept, the derivations, the reading, and
the acceptance tests the code must pass) and reviews the implementation. Corbin Weiss,
the student, writes all of the code, runs the week's experiments with it, and writes the
lesson. The lesson is the deliverable; the milestone is done when it is written.

**What a lesson is.** A Jupyter notebook in which the prose and the code that produced its
numbers sit together, run top to bottom and committed with outputs, so it reads on GitHub
without anything installed ([decision 0001](decisions/0001-lessons-are-notebooks.md)).
Every lesson follows the [lesson template](course/lesson-template.ipynb) and has the same
sections: the question this lesson answers; concept and derivation; the experiment; what
the numbers showed; what went wrong and what I'd do differently; pitfalls to remember;
reading.

**Status.** Weeks whose brief or lesson is marked *pending* have not been reached yet. A
lesson marked *in progress* opens with a note listing what is still to be written.
Design rationale for the whole course lives in the
[course spec](specs/2026-09-14-portfolio-lab-course-design.md).

## Week 0. pandas primer

Written by Claude, worked through by Corbin; no lesson to write. Each notebook ends in
exercises with expected answers. Runs on synthetic data, so no ingestion is needed.

| Part | Topic | Before |
|---|---|---|
| [00a](course/primers/00a-pandas-series-frames-selection.ipynb) | Series, DataFrames, selection, Copy-on-Write | week 1 step 2 |
| [00b](course/primers/00b-pandas-alignment-axis-missing.ipynb) | Alignment, `axis`, vectorising, iteration, missing data | week 1 step 3 |
| [00c](course/primers/00c-pandas-time-series.ipynb) | Shifts, cumulative, rolling, resample, lookahead | week 2 |
| [00d](course/primers/00d-pandas-reshape-groupby-merge.ipynb) | Reshape, groupby, merge_asof, linear algebra, course toolkit | week 3 |

## Phase A. Foundations on eight tickers (free data)

| Wk | Topic | Brief | Lesson | Milestone |
|---|---|---|---|---|
| 1 | Data integrity and return math | [brief](course/briefs/01-data-integrity.md) | [lesson](course/lessons/01-data-integrity.ipynb) (in progress) | Eight tickers and DTB3 in the snapshot store; two snapshots diffed |
| 2 | The backtest engine, rebuilt | pending | pending | Own engine with cash leg; lookahead tests rebuilt; old engine deleted |
| 3 | Mean-variance, diversification, CAPM | pending | pending | Frontier derived and plotted; estimation error shown by bootstrap |
| 4 | Estimating risk | pending | pending | Hand-derived Ledoit-Wolf; risk parity; VaR/CVaR; planted-covariance recovery |

## Phase B. Rigor on the S&P 500 (paid data)

| Wk | Topic | Brief | Lesson | Milestone |
|---|---|---|---|---|
| 5 | Survivorship bias and point-in-time universes | pending | pending | Membership and delisting tables; measured survivorship gap |
| 6 | Signals as views; factor models | pending | pending | Value signal with reporting lag; Fama-French regressions |
| 7 | Overfitting and multiple testing | pending | pending | Trial ledger; purged CV; deflated Sharpe; PBO |

## Phase C. Instruments and financing

| Wk | Topic | Brief | Lesson | Milestone |
|---|---|---|---|---|
| 8 | Cash, leverage, shorts, the cost of money | pending | pending | Financing model; long-short and levered risk parity with costs |
| 9 | Futures and bonds | pending | pending | Continuous contracts and fair value; duration; hedged vs unhedged bonds |
| 10 | Options | pending | pending | Black-Scholes and greeks; protective-put and covered-call overlays |

## Phase D. Portfolio management

| Wk | Topic | Brief | Lesson | Milestone |
|---|---|---|---|---|
| 11 | Attribution and taxes | pending | pending | Brinson vs 60/40; tax-lot ledger with harvesting |
| 12 | The recommender and capstone | pending | pending | `plab recommend` comparing three risk framings; capstone report |

## Reference

- [The code before week 1](reference/starting-point.md)
- [Data sources and vendor quirks](reference/data-sources.md)
- [Reading list](reference/reading-list.md)
- [Glossary](reference/glossary.md)
- [Decision records](decisions/README.md)
