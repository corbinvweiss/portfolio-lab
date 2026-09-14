# portfolio-lab syllabus

Twelve weeks, four phases. Each week has a brief (what to build, written by Claude) and a
lesson (what was learned, written by Corbin). The lesson is the deliverable; the milestone
is done when it is written. Design rationale lives in the
[course spec](specs/2026-09-14-portfolio-lab-course-design.md). Lessons follow the
[lesson template](course/lesson-template.md).

## Phase A. Foundations on eight tickers (free data)

| Wk | Topic | Brief | Lesson | Milestone |
|---|---|---|---|---|
| 1 | Data integrity and return math | [brief](course/briefs/01-data-integrity.md) | pending | Eight tickers and DTB3 in the snapshot store; two snapshots diffed |
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

- [Data sources and vendor quirks](reference/data-sources.md)
- [Reading list](reference/reading-list.md)
- [Glossary](reference/glossary.md)
- [Decision records](decisions/README.md)
