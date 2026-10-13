# Week 1: Data Integrity and Return Math

> **For the student:** You implement every task below yourself, in order, under TDD.
> The tests in this brief are the acceptance criteria and may be copied verbatim. The
> implementation bodies are deliberately not given; signatures, behaviour, and hints are.
> When a task is done, say so and Claude reviews it before you move on. Steps use
> checkbox (`- [ ]`) syntax so you can track progress in the file.

**Goal:** Ingest eight real tickers and a risk-free series into the point-in-time store,
prove the store's guarantees with tests, and write lesson 1 on returns and data integrity.

**Architecture:** The existing `PriceStore` (`src/portfolio_lab/data/store.py`) gains a
second table for rates and a generic snapshot-collapse routine. A `Universe` loaded from
CSV replaces the hardcoded ETF tuple as the source of tickers and sleeves. A new
`data/returns.py` holds the return identities the rest of the course relies on.

**Tech Stack:** Python 3.12 in `.venv`, pandas, DuckDB, pyarrow, yfinance (prices), FRED
CSV endpoint (rates, no API key), pytest, ruff.

**Spec:** `docs/specs/2026-09-14-portfolio-lab-course-design.md`, section 5,
week 1.

## Global Constraints

- Tests never touch the network or `data/`. Network fetchers are exercised only through
  monkeypatched fakes; store tests use `InMemoryStore` or `tmp_path`.
- Every persistent write goes through `PriceStore`; no module calls `duckdb.connect`
  except the store.
- Writes are append-only dated snapshots; the curated view is the latest capture per key.
- A new config knob needs a `.get(...)` default in `experiment.py` and a line in both
  `configs/baseline.yaml` and `configs/synthetic.yaml`.
- `ruff check src tests` clean; line length 100; target py310. On 2026-09-14 the untouched
  repo has 11 findings (unsorted imports, `date.today()`, `dict()` literals, an unused
  import). Clear them as the first commit of Task 1 so every later check starts from zero;
  `ruff check --fix` handles six, the rest are one-line edits.
- Commit after every task with a message that says what changed and why.
- Time budget: 5-10 hours including the lesson. Tasks 1-4 are about an hour each.

---

## Before you code: the concepts

Read this section first. The derivations are yours to reproduce in the lesson in your own
words; the exercises at the end are what the lesson must answer.

### Simple vs log returns

With prices $P_t$, the simple return is $r_t = P_t / P_{t-1} - 1$ and the log return is
$\ell_t = \ln(P_t / P_{t-1}) = \ln(1 + r_t)$.

Two identities you will test:

1. **Log returns add over time.** $\sum_{t=1}^{T} \ell_t = \ln(P_T / P_0)$, because the
   product telescopes inside the log.
2. **Simple returns compound.** $\prod_{t=1}^{T} (1 + r_t) = P_T / P_0$.

Simple returns add *across assets* on the same day (a portfolio return is the
weight-averaged simple return), log returns do not. Log returns add *across time*, simple
returns do not. The backtest engine therefore uses simple returns day by day and the
metrics use compounding for horizons. Keep that asymmetry in the lesson.

For small $r$, $\ln(1 + r) \approx r - r^2/2$. The gap is the reason a stock that goes
+50% then -33% is flat in log terms and looks like +8.5% "average simple return".

### Annualisation and why the Sharpe shortcut is an approximation

If daily log returns are i.i.d. with mean $\mu$ and variance $\sigma^2$, then over $N$
days the mean is $N\mu$ and the variance is $N\sigma^2$. Hence the $\sqrt{252}$ rule for
volatility. The same rule applied to simple returns is only approximate because simple
returns compound rather than add. `metrics.summarise` computes Sharpe as CAGR divided by
annualised vol, which is exact for the growth rate but is not the classical
$\bar r / s \cdot \sqrt{252}$. Exercise 2 below quantifies the difference on real data.

### Price return vs total return

A "close" from most vendors is the price. A total-return series reinvests dividends: on an
ex-dividend date the price drops by the dividend but the holder is not poorer. Vendors
publish an *adjusted close* that scales all earlier prices down so that the adjusted series
compounds like a total-return index. Two consequences:

- Every new dividend restates the entire history. That is why the store keeps dated
  snapshots: the number you saw last week is gone from the vendor.
- Adjusted prices are not prices. Never use them for anything that depends on the price
  level (share counts, option strikes, round lots).

### The risk-free rate

FRED series `DTB3` is the 3-month Treasury bill *discount* yield, in percent per year, on a
360-day basis. For this course convert it to a daily accrual by
$r^{daily}_t = (1 + y_t/100)^{1/252} - 1$, which treats the quoted number as an annual
rate. It is off by a few basis points from the exact bond-equivalent yield; note that in the
lesson and move on. Weekends and holidays are missing from FRED and must be forward-filled
by the consumer, never by the store.

### Point-in-time

`load_prices(as_of=d)` replays only snapshots captured on or before `d`. The lesson's
experiment is to take two snapshots a week apart and diff them: the differences are the
restatements, and their dates should line up with ex-dividend dates.

---

## File Structure

| File | Responsibility |
|---|---|
| Create `src/portfolio_lab/data/returns.py` | Pure return identities: simple, log, compounding, annualisation, daily rate from annual |
| Modify `src/portfolio_lab/data/universe.py` | `Asset` gains membership dates; `Universe` class loaded from CSV with `members(as_of)` and `sleeves` |
| Create `configs/universe_week1.csv` | The eight-ticker seed |
| Modify `src/portfolio_lab/data/store.py` | Rates table (`write_rates`, `load_rate`); generic `_collapse_snapshots` |
| Modify `src/portfolio_lab/data/ingest.py` | `fetch_fred`, `ingest_rates`; `ingest` takes an explicit ticker list |
| Create `src/portfolio_lab/data/snapshots.py` | `snapshot_diff(store, earlier, later)` |
| Modify `src/portfolio_lab/cli.py` | `ingest --universe`, new `ingest-rates` and `diff-snapshots` subcommands |
| Modify `src/portfolio_lab/experiment.py` | `data.universe` config key selects tickers and sleeves |
| Modify `configs/baseline.yaml`, `configs/synthetic.yaml` | `data.universe` line |
| Create `configs/week1.yaml` | Store-backed run on the week 1 universe |
| Create `tests/test_returns.py`, `tests/test_universe.py`, `tests/test_rates.py`, `tests/test_snapshots.py` | One test file per unit |
| Create `docs/course/lessons/01-data-integrity.ipynb` | The deliverable (see decisions/0001) |

---

### Task 1: Return identities

**Files:**
- Create: `src/portfolio_lab/data/returns.py`
- Test: `tests/test_returns.py`

**Interfaces:**
- Produces:
  - `simple_returns(prices: pd.DataFrame) -> pd.DataFrame` (first row NaN)
  - `log_returns(prices: pd.DataFrame) -> pd.DataFrame` (first row NaN)
  - `compound(simple: pd.Series) -> float` (product of `1 + r`, NaNs skipped)
  - `annualise_vol(daily: pd.Series, periods: int = 252) -> float`
  - `daily_rate_from_annual(annual_pct: pd.Series, periods: int = 252) -> pd.Series`

- [x] **Step 1: Write the failing tests**

```python
"""Return identities every later lesson leans on."""
import numpy as np
import pandas as pd
import pytest

from portfolio_lab.data.returns import (
    annualise_vol, compound, daily_rate_from_annual, log_returns, simple_returns,
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
```

- [x] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_returns.py -q`
Expected: ImportError, `portfolio_lab.data.returns` does not exist.

- [x] **Step 3: Implement `returns.py`**

Hints: `pct_change()` and `np.log(prices).diff()`; `compound` is `np.prod(1 + r.dropna())`.
Keep the module free of any import from the rest of the package. Write a module docstring
that states the two identities and the cross-time vs cross-asset asymmetry.

- [x] **Step 4: Run to verify they pass, then lint**

Run: `.venv/bin/python -m pytest tests/test_returns.py -q && .venv/bin/ruff check src tests`

- [x] **Step 5: Commit**

```bash
git add src/portfolio_lab/data/returns.py tests/test_returns.py
git commit -m "Add return identities module with tests for log/simple compounding"
```

---

### Task 2: Universe from CSV

**Files:**
- Modify: `src/portfolio_lab/data/universe.py`
- Create: `configs/universe_week1.csv`
- Test: `tests/test_universe.py`

**Interfaces:**
- Produces:
  - `Asset(ticker, name, sleeve, member_from: date, member_to: date | None)` (frozen dataclass)
  - `Universe(assets: tuple[Asset, ...])` with
    - `Universe.from_csv(path) -> Universe`
    - `.tickers -> tuple[str, ...]` (all assets, in file order)
    - `.sleeves -> dict[str, str]`
    - `.members(as_of: date) -> tuple[str, ...]` (tickers with `member_from <= as_of` and `member_to` unset or `>= as_of`)
  - `ETF_SLEEVE`, `TICKERS`, `SLEEVES` remain as the default universe so existing code and tests keep working; `DEFAULT_UNIVERSE = Universe(ETF_SLEEVE)`.

- [x] **Step 1: Create the seed file**

`configs/universe_week1.csv`. `member_from` is the first date this course includes the
asset, not its listing date; week 5 replaces this hand-made seed with vendor membership.

```csv
ticker,name,sleeve,member_from,member_to
SPY,US large cap equity,equity,2015-01-02,
EFA,Developed ex-US equity,equity,2015-01-02,
IEF,US intermediate treasury,duration,2015-01-02,
GLD,Gold,real_asset,2015-01-02,
AAPL,Apple,equity,2015-01-02,
MSFT,Microsoft,equity,2015-01-02,
JNJ,Johnson & Johnson,equity,2015-01-02,
XOM,Exxon Mobil,equity,2015-01-02,
```

- [x] **Step 2: Write the failing tests**

```python
import dataclasses
from datetime import date

from portfolio_lab.data.universe import DEFAULT_UNIVERSE, Asset, Universe

CSV = """ticker,name,sleeve,member_from,member_to
AAA,Alpha,equity,2015-01-02,
BBB,Beta,duration,2015-01-02,2018-06-30
CCC,Gamma,equity,2019-01-02,
"""


def test_from_csv_parses_dates_and_blank_member_to(tmp_path):
    p = tmp_path / "u.csv"
    p.write_text(CSV)
    u = Universe.from_csv(p)
    assert u.tickers == ("AAA", "BBB", "CCC")
    assert u.sleeves == {"AAA": "equity", "BBB": "duration", "CCC": "equity"}
    assert u.assets[1].member_to == date(2018, 6, 30)
    assert u.assets[0].member_to is None


def test_members_respects_membership_window(tmp_path):
    p = tmp_path / "u.csv"
    p.write_text(CSV)
    u = Universe.from_csv(p)
    assert u.members(date(2016, 1, 1)) == ("AAA", "BBB")
    assert u.members(date(2018, 6, 30)) == ("AAA", "BBB")   # inclusive end
    assert u.members(date(2018, 7, 1)) == ("AAA",)
    assert u.members(date(2020, 1, 1)) == ("AAA", "CCC")


def test_default_universe_matches_legacy_constants():
    from portfolio_lab.data.universe import SLEEVES, TICKERS
    assert DEFAULT_UNIVERSE.tickers == TICKERS
    assert DEFAULT_UNIVERSE.sleeves == SLEEVES


def test_week1_seed_loads():
    u = Universe.from_csv("configs/universe_week1.csv")
    assert len(u.tickers) == 8
    assert set(u.sleeves.values()) == {"equity", "duration", "real_asset"}


def test_asset_is_frozen():
    a = Asset("X", "x", "equity", date(2015, 1, 2), None)
    try:
        a.ticker = "Y"
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("Asset must be immutable")
```

- [x] **Step 3: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_universe.py -q`

- [x] **Step 4: Implement**

Hints: extend `Asset` with the two date fields, defaulting `member_from=date(1900, 1, 1)`
and `member_to=None` so the existing `ETF_SLEEVE` literal still constructs. Parse the CSV
with `csv.DictReader`, not pandas: eight rows do not need a DataFrame, and the date
parsing is explicit. Keep `TICKERS` and `SLEEVES` derived from `ETF_SLEEVE` exactly as now.

- [x] **Step 5: Run the whole suite and lint**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check src tests`
Expected: all previous tests still pass; nothing else imports the new fields yet.

- [x] **Step 6: Commit**

```bash
git add src/portfolio_lab/data/universe.py configs/universe_week1.csv tests/test_universe.py
git commit -m "Add Universe loaded from CSV with membership windows"
```

---

### Task 3: Rates table in the store, FRED fetcher, ingest by universe

**Files:**
- Modify: `src/portfolio_lab/data/store.py`
- Modify: `src/portfolio_lab/data/ingest.py`
- Modify: `src/portfolio_lab/cli.py`
- Test: `tests/test_rates.py`

**Interfaces:**
- Consumes: `Universe.from_csv`, `daily_rate_from_annual` (unused here but the consumer
  of `load_rate` in week 2 will call it).
- Produces on `PriceStore` (abstract, so both stores implement it):
  - `write_rates(df: pd.DataFrame, captured_on: date | None = None) -> Path`
    where `df` has columns `date, series, value` (value in percent as published)
  - `load_rate(series: str, as_of: date | None = None) -> pd.Series`
    indexed by `DatetimeIndex`, named after the series, raw published values, no
    forward-fill, `FileNotFoundError` if nothing was written
- Produces in `ingest.py`:
  - `fetch_fred(series_id: str, start: str) -> pd.DataFrame` (columns `date, series, value`; drops FRED's `.` missing markers)
  - `ingest_rates(store, series_id: str = "DTB3", start: str = "2015-01-01") -> tuple[Path, pd.DataFrame]`
  - `ingest(store, tickers, start, end)` unchanged in signature; the CLI now passes `Universe.from_csv(...).tickers` when `--universe` is given.
- Produces in `cli.py`:
  - `plab ingest --universe configs/universe_week1.csv --start 2015-01-01`
  - `plab ingest-rates --series DTB3 --start 2015-01-01`

- [x] **Step 1: Write the failing tests**

```python
"""Rates live beside prices in the store, with the same snapshot semantics."""
from datetime import date

import pandas as pd
import pytest

from portfolio_lab.data import ingest as ingest_mod
from portfolio_lab.data.store import InMemoryStore, ParquetDuckStore


def _rates(dates, value, series="DTB3"):
    return pd.DataFrame({"date": dates, "series": series, "value": value})


@pytest.fixture(params=["memory", "parquet"])
def store(request, tmp_path):
    return InMemoryStore() if request.param == "memory" else ParquetDuckStore(tmp_path)


def test_rates_roundtrip(store):
    dates = [date(2024, 1, 2), date(2024, 1, 3)]
    store.write_rates(_rates(dates, 5.25), captured_on=date(2024, 1, 4))
    s = store.load_rate("DTB3")
    assert s.name == "DTB3"
    assert isinstance(s.index, pd.DatetimeIndex)
    assert s.tolist() == [5.25, 5.25]


def test_rates_later_snapshot_wins_and_as_of_replays(store):
    d = [date(2024, 1, 2)]
    store.write_rates(_rates(d, 5.25), captured_on=date(2024, 1, 3))
    store.write_rates(_rates(d, 5.30), captured_on=date(2024, 1, 10))
    assert store.load_rate("DTB3").iloc[0] == pytest.approx(5.30)
    assert store.load_rate("DTB3", as_of=date(2024, 1, 5)).iloc[0] == pytest.approx(5.25)


def test_rates_do_not_disturb_prices(store):
    prices = pd.DataFrame({"date": [date(2024, 1, 2)], "ticker": ["AAA"],
                           "close": [100.0], "volume": [1.0]})
    store.write_snapshot(prices, captured_on=date(2024, 1, 3))
    store.write_rates(_rates([date(2024, 1, 2)], 5.0), captured_on=date(2024, 1, 3))
    assert store.load_prices().shape == (1, 1)
    assert store.snapshots() == [date(2024, 1, 3)]


def test_load_rate_unknown_series_raises(store):
    with pytest.raises(FileNotFoundError):
        store.load_rate("DGS10")


def test_write_rates_rejects_duplicates_and_missing_columns(store):
    with pytest.raises(ValueError):
        store.write_rates(pd.DataFrame({"date": [date(2024, 1, 2)]}), date(2024, 1, 3))
    dup = _rates([date(2024, 1, 2)] * 2, 5.0)
    with pytest.raises(ValueError):
        store.write_rates(dup, date(2024, 1, 3))


FRED_CSV = """observation_date,DTB3
2024-01-01,.
2024-01-02,5.25
2024-01-03,5.24
"""


def test_fetch_fred_parses_and_drops_missing(monkeypatch):
    def fake_read_csv(url, **kwargs):
        assert "DTB3" in url
        import io
        return pd.read_csv(io.StringIO(FRED_CSV), **kwargs)
    monkeypatch.setattr(ingest_mod.pd, "read_csv", fake_read_csv)
    df = ingest_mod.fetch_fred("DTB3", start="2024-01-01")
    assert list(df.columns) == ["date", "series", "value"]
    assert len(df) == 2
    assert df["value"].tolist() == [5.25, 5.24]
    assert (df["series"] == "DTB3").all()


def test_ingest_rates_writes_snapshot(monkeypatch):
    monkeypatch.setattr(
        ingest_mod, "fetch_fred",
        lambda series_id, start: _rates([date(2024, 1, 2)], 5.0, series_id),
    )
    store = InMemoryStore()
    ingest_mod.ingest_rates(store, "DTB3", start="2024-01-01")
    assert store.load_rate("DTB3").iloc[0] == 5.0


def test_cli_ingest_uses_universe_file(monkeypatch, tmp_path):
    from portfolio_lab import cli
    captured = {}

    def fake_ingest(store, tickers, start, end=None):
        captured["tickers"] = tuple(tickers)
        return tmp_path / "x.parquet", pd.DataFrame({"ticker": list(tickers)})
    monkeypatch.setattr(ingest_mod, "ingest", fake_ingest)
    monkeypatch.setattr(cli, "ParquetDuckStore", lambda: InMemoryStore())
    cli.main(["ingest", "--universe", "configs/universe_week1.csv", "--start", "2015-01-01"])
    assert captured["tickers"] == ("SPY", "EFA", "IEF", "GLD", "AAPL", "MSFT", "JNJ", "XOM")
```

- [x] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_rates.py -q`

- [x] **Step 3: Implement the store side**

Design this before typing. `_rebuild_curated` is price-specific SQL. Generalise it into
`_collapse_snapshots(prefix: str, key_cols: tuple[str, ...], value_cols: tuple[str, ...])`
that reads `raw/{prefix}_captured=*.parquet`, keeps the latest `captured_on` per key, and
writes `curated/{prefix}.parquet`. Prices call it with `("prices", ("date", "ticker"),
("close", "volume"))`; rates with `("rates", ("date", "series"), ("value",))`. The `as_of`
branch of `load_prices` has the same shape and should share a helper. `snapshots()` must
keep listing only price snapshots (the test asserts that), so do not glob `*_captured=*`.

Validation: write `_validate_long_rates` beside `_validate_long_prices`, or generalise the
validator to take the required columns and key. Duplicate `(date, series)` rows are
rejected; values may be any float.

`InMemoryStore` gets a second dict. Same replay logic as prices.

- [x] **Step 4: Implement the fetcher and CLI**

`fetch_fred` reads `https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}` with
`pd.read_csv(url, na_values=".")`. FRED has used both `DATE` and `observation_date` as the
first column name; handle both by renaming the first column to `date`. Filter `date >=
start`, drop NaN values, add the `series` column. Keep the test's monkeypatch target in
mind: the function must call `pd.read_csv` via the `pd` module attribute, not a
`from pandas import read_csv`.

CLI: add `--universe` (default `None`) to `ingest`; when given, load `Universe.from_csv`
and pass `.tickers`. Add the `ingest-rates` subcommand. The `ingest` handler must
reference `ingest_mod.ingest` at call time (not a module-level `from .data.ingest import
ingest`) so the CLI test can patch it; the current code already imports inside the
handler, keep that shape.

- [x] **Step 5: Run the full suite and lint**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check src tests`
Expected: the four pre-existing store tests still pass alongside the new ones.

- [x] **Step 6: Commit**

```bash
git add src/portfolio_lab/data/store.py src/portfolio_lab/data/ingest.py src/portfolio_lab/cli.py tests/test_rates.py
git commit -m "Add rates table to the store, FRED fetcher, and ingest by universe file"
```

---

### Task 4: Snapshot diff and the config knob

**Files:**
- Create: `src/portfolio_lab/data/snapshots.py`
- Modify: `src/portfolio_lab/cli.py`
- Modify: `src/portfolio_lab/experiment.py`
- Modify: `configs/baseline.yaml`, `configs/synthetic.yaml`
- Create: `configs/week1.yaml`
- Test: `tests/test_snapshots.py`

**Interfaces:**
- Produces:
  - `snapshot_diff(store, earlier: date, later: date, tol: float = 1e-9) -> pd.DataFrame`
    with columns `date, ticker, close_before, close_after, rel_change`, one row per
    `(date, ticker)` present in both replays whose close differs by more than `tol`,
    sorted by `date, ticker`. Rows only in one snapshot are excluded (they are additions,
    not restatements).
  - `plab diff-snapshots EARLIER LATER` prints the frame and a one-line count.
  - `experiment.load_prices` honours `cfg["data"].get("universe")`: when set, the wide
    frame is restricted to that universe's tickers (both synthetic and store sources), and
    `run_experiment` passes that universe's `sleeves` to `risk_parity` instead of the
    module constant `SLEEVES`.

- [x] **Step 1: Write the failing tests**

```python
from datetime import date

import pandas as pd
import pytest

from portfolio_lab.data.snapshots import snapshot_diff
from portfolio_lab.data.store import InMemoryStore


def _frame(rows):
    return pd.DataFrame(
        [{"date": d, "ticker": t, "close": c, "volume": 1.0} for d, t, c in rows]
    )


def test_diff_reports_only_restated_rows():
    store = InMemoryStore()
    d1, d2 = date(2024, 1, 2), date(2024, 1, 3)
    store.write_snapshot(_frame([(d1, "AAA", 100.0), (d2, "AAA", 101.0)]), date(2024, 1, 4))
    store.write_snapshot(
        _frame([(d1, "AAA", 99.0), (d2, "AAA", 101.0), (d2, "BBB", 50.0)]), date(2024, 1, 11)
    )
    diff = snapshot_diff(store, date(2024, 1, 4), date(2024, 1, 11))
    assert list(diff.columns) == ["date", "ticker", "close_before", "close_after", "rel_change"]
    assert len(diff) == 1
    row = diff.iloc[0]
    assert row["ticker"] == "AAA" and row["close_before"] == 100.0 and row["close_after"] == 99.0
    assert row["rel_change"] == pytest.approx(-0.01)


def test_diff_is_empty_when_nothing_restated():
    store = InMemoryStore()
    f = _frame([(date(2024, 1, 2), "AAA", 100.0)])
    store.write_snapshot(f, date(2024, 1, 4))
    store.write_snapshot(f, date(2024, 1, 11))
    assert snapshot_diff(store, date(2024, 1, 4), date(2024, 1, 11)).empty


def test_experiment_restricts_to_config_universe(tmp_path):
    from portfolio_lab.experiment import load_prices
    (tmp_path / "u.csv").write_text(
        "ticker,name,sleeve,member_from,member_to\nSPY,s,equity,2015-01-02,\nGLD,g,real_asset,2015-01-02,\n"
    )
    cfg = {"data": {"source": "synthetic", "n_days": 400, "universe": str(tmp_path / "u.csv")}}
    wide = load_prices(cfg)
    assert list(wide.columns) == ["GLD", "SPY"] or list(wide.columns) == ["SPY", "GLD"]


def test_experiment_default_universe_unchanged():
    from portfolio_lab.data.universe import TICKERS
    from portfolio_lab.experiment import load_prices
    wide = load_prices({"data": {"source": "synthetic", "n_days": 400}})
    assert set(wide.columns) == set(TICKERS)
```

- [x] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_snapshots.py -q`

- [x] **Step 3: Implement `snapshot_diff`**

Hint: `store.load_prices(as_of=earlier)` and `as_of=later` give two wide frames. Stack
both to long, inner-join on `(date, ticker)`, keep rows where `abs(after - before) > tol`.
Do not query parquet directly; the store is the only reader.

- [x] **Step 4: Wire the config knob and CLI**

In `experiment.py`, add `_universe_from_cfg(cfg) -> Universe` returning
`Universe.from_csv(path)` when `cfg["data"].get("universe")` is set, else
`DEFAULT_UNIVERSE`. Use its `.tickers` in `load_prices` (for synthetic, generate for those
tickers; for store, select those columns and raise a clear `KeyError` naming any ticker the
store does not have) and its `.sleeves` in `run_experiment`. Add `universe: null  # path to a
universe CSV, or null for the built-in 12-ETF sleeve` under `data:` in both config files.

Create `configs/week1.yaml` as a copy of `baseline.yaml` with `name: week1`,
`data.universe: configs/universe_week1.csv`, `backtest.warmup: 300`, and everything else
unchanged. It will not run until you have ingested; that is Task 5.

Add the `diff-snapshots` subcommand.

- [x] **Step 5: Run everything and lint**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check src tests && .venv/bin/plab run --config configs/synthetic.yaml --no-chart --outdir /tmp/plab-check`
Expected: suite green; the synthetic run still prints three allocator rows.

- [x] **Step 6: Commit**

```bash
git add src/portfolio_lab/data/snapshots.py src/portfolio_lab/cli.py src/portfolio_lab/experiment.py configs tests/test_snapshots.py
git commit -m "Add snapshot diff and a data.universe config knob"
```

---

### Task 5: The experiment and the lesson

**Files:**
- Create: `docs/course/lessons/01-data-integrity.ipynb` (copy `docs/course/lesson-template.ipynb`)

Steps 2-6 are done in the lesson notebook itself: the code that produces each number sits
in the cell beneath the prose that claims it. `notebooks/` stays available for dead ends.

This task has a calendar dependency: the second snapshot must be taken about a week after
the first. Do steps 1-3 on day one and steps 4-7 a week later. Fill the other days with
the derivations and the lesson skeleton.

- [x] **Step 1: First ingestion (day 1)**

```bash
.venv/bin/plab ingest --universe configs/universe_week1.csv --start 2015-01-01
.venv/bin/plab ingest-rates --series DTB3 --start 2015-01-01
.venv/bin/plab snapshots
```

If yfinance fails (it is a scraper, and `docs/reference/data-sources.md` records blocked endpoints), run the
same commands from a machine that can reach the vendor and copy `data/raw/` across. The
FRED CSV endpoint is rarely blocked.

- [ ] **Step 2: Sanity checks (day 1)**

In the lesson notebook, load the wide prices and answer:

- How many trading days per ticker? Do all eight start on 2015-01-02?
- Is `SPY` adjusted close on 2015-01-02 equal to the price you can find quoted for that
  day? (It will not be. Explain the gap.)
- Compute `simple_returns` and `log_returns`; report mean and std of each for `SPY` and
  `AAPL`, daily and annualised.

- [ ] **Step 3: Exercise 2, Sharpe two ways (day 1)**

For each of the eight tickers compute both:

- the classical `mean(daily simple) / std(daily simple) * sqrt(252)`, and
- the growth-rate version `CAGR / (std(daily simple) * sqrt(252))` exactly as
  `metrics.summarise` does,

with and without subtracting the daily risk-free rate from `load_rate("DTB3")` (forward-fill
the gaps, convert with `daily_rate_from_annual`, align on the price index). Put the eight
rows in a table in the lesson. State which ticker shows the largest gap between the two
definitions and why (hint: it is the one with the highest volatility; expand
$\ln(1+r)$ to second order).

- [ ] **Step 4: Second ingestion (day 7 or later)**

```bash
.venv/bin/plab ingest --universe configs/universe_week1.csv --start 2015-01-01
.venv/bin/plab snapshots
.venv/bin/plab diff-snapshots <first date> <second date>
```

- [ ] **Step 5: Exercise 1, restatements (day 7)**

Record in the lesson: how many `(date, ticker)` rows changed, for which tickers, and the
typical `rel_change`. Look up the ex-dividend dates that fell in the week for the tickers
that changed (SPY, IEF, JNJ, XOM pay quarterly; check which had an ex-date). Confirm that
every earlier price of a ticker with a new ex-dividend moved by the same relative amount,
and tickers without one did not move at all. If the vendor also changed something else,
say so; that is the point of keeping snapshots.

- [ ] **Step 6: Run the week 1 config both ways (day 7)**

```bash
.venv/bin/plab run --config configs/week1.yaml --no-chart --outdir runs
```

Then set `data.as_of` to the first snapshot date and run again. Note in the lesson whether
any metric moved and by how much. With one week of restatements the answer should be
"barely"; explain why a backtest over ten years is insensitive to a small uniform rescale of
a ticker's history, and what kind of vendor change would *not* be harmless.

- [ ] **Step 7: Write the lesson**

Finish `docs/course/lessons/01-data-integrity.ipynb`, then Kernel > Restart & Run All so
the committed outputs come from one clean top-to-bottom run (`tests/test_docs.py` checks).
The "Concept and derivation" section must contain, in your own words and notation:

1. the two return identities and the cross-time vs cross-asset asymmetry;
2. the second-order expansion showing why simple averages overstate growth;
3. the $\sqrt{252}$ rule and the assumption it needs;
4. what an adjusted close is and why it restates history;
5. how the store's snapshot replay gives a point-in-time view, in one paragraph a
   colleague could act on.

"What the numbers showed" holds the two exercise tables. "What went wrong" is mandatory
even if the answer is short.

- [ ] **Step 8: Commit**

```bash
git add docs/course/lessons/01-data-integrity.ipynb
git commit -m "Lesson 1: data integrity and return math"
```

---

## Review checklist (Claude runs this when you say a task is done)

- Tests exist before implementation in the commit history (check `git log -p` ordering
  within the task's commits, or at least that the test commit is not after a green
  implementation commit).
- No module other than `store.py` imports `duckdb`.
- `snapshots()` still lists only price snapshots.
- `ruff` clean; full suite green; `plab run --config configs/synthetic.yaml` unchanged.
- The lesson answers all five derivation points and both exercises with numbers.
- Nothing under `data/` is committed.

## Self-review against the spec

- Store round-trips: `test_rates_roundtrip` plus the existing `test_roundtrip`.
- As-of replay returns the earlier snapshot: existing `test_point_in_time_replay` plus
  `test_rates_later_snapshot_wins_and_as_of_replays`.
- Curated view picks the latest capture per key: existing `test_later_snapshot_wins`,
  now exercised through the generalised collapse routine.
- Eight tickers ingested 2015-2025: Task 5 step 1 on the Task 2 seed.
- Two snapshots a week apart, diffed: Task 4 tool, Task 5 steps 4-5.
- Risk-free series in the store: Task 3.
- Universe seed table: Task 2.
- Derivations (compounding identities, Sharpe approximation): the concepts section and
  Task 5 step 7.
