"""Storage, behind one narrow interface.

Why this exists: the single most common way a research codebase calcifies is
`duckdb.connect(...)` sprinkled through forty modules. Everything that touches
persistence goes through `PriceStore`, so swapping Parquet+DuckDB for Postgres
later is one new class, not a refactor.

Two design choices worth understanding:

1. Writes are APPEND-ONLY SNAPSHOTS, not overwrites. Every ingestion run lands
   in `raw/` tagged with the date it was captured. Vendors restate history
   (splits, dividend adjustments, fundamental restatements), and you cannot
   reconstruct after the fact what the data looked like on a past date. Keeping
   snapshots costs kilobytes now and is impossible to backfill later.

2. `curated/` holds the as-of-latest view built from those snapshots. That is
   what backtests read by default. Point-in-time reconstruction is available via
   `load_prices(as_of=...)`, which replays only snapshots captured on or before
   that date.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = REPO_ROOT / "data"


class PriceStore(ABC):
    """Minimal persistence contract. Implement this to swap the backend."""

    @abstractmethod
    def write_snapshot(self, df: pd.DataFrame, captured_on: date) -> Path: ...

    @abstractmethod
    def load_prices(self, as_of: date | None = None) -> pd.DataFrame: ...

    @abstractmethod
    def write_rates(self, df: pd.DataFrame, captured_on: date | None = None) -> Path:
        """df: long frame: (date, series id, value) -> path written to. 
        Validates that (date, series) keys never repeat or are missing."""

    @abstractmethod
    def load_rate(self, series: str, as_of: date | None = None) -> pd.Series:
        """series: FRED series ID -> (date, value) series of rates"""

    @abstractmethod
    def snapshots(self) -> list[date]: ...


class ParquetDuckStore(PriceStore):
    """Parquet files on disk, DuckDB as the query engine. No server process.

    Long-format price schema, one row per (date, ticker):
        date: DATE, ticker: VARCHAR, close: DOUBLE, volume: DOUBLE
    `close` is split- and dividend-adjusted (total return).

    Rate schema, one row per (date, series, captured_on):
        date: DATE, series: VARCHAR, captured_on: DATE, value: DOUBLE

    """

    def __init__(self, data_dir: Path | str = DEFAULT_DATA_DIR) -> None:
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.curated_dir = self.data_dir / "curated"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.curated_dir.mkdir(parents=True, exist_ok=True)

    # -- writing ---------------------------------------------------------
    def write_snapshot(self, df: pd.DataFrame, captured_on: date | None = None) -> Path:
        captured_on = captured_on or datetime.now(tz=timezone.utc).date()
        _validate_long_prices(df)
        out = self.raw_dir / f"prices_captured={captured_on.isoformat()}.parquet"
        df = df.copy()
        df["captured_on"] = pd.Timestamp(captured_on)
        df.to_parquet(out, index=False)
        self._rebuild_curated()
        return out

    def write_rates(self, df: pd.DataFrame, captured_on: date | None = None) -> Path:
        captured_on = captured_on or datetime.now(tz=timezone.utc).date()
        _validate_rates(df)
        out = self.raw_dir / f"rates_captured={captured_on.isoformat()}.parquet"
        df = df.copy()
        df["captured_on"] = pd.Timestamp(captured_on)
        df.to_parquet(out, index=False)
        return out


    def _rebuild_curated(self) -> None:
        """Collapse all snapshots to the latest observation per (date, ticker)."""
        files = sorted(self.raw_dir.glob("prices_captured=*.parquet"))
        if not files:
            return
        con = duckdb.connect()
        glob = str(self.raw_dir / "prices_captured=*.parquet")
        con.execute(
            f"""
            COPY (
                SELECT date, ticker, close, volume
                FROM (
                    SELECT *, ROW_NUMBER() OVER (
                        PARTITION BY date, ticker ORDER BY captured_on DESC
                    ) AS rn
                    FROM read_parquet('{glob}')
                ) WHERE rn = 1
                ORDER BY date, ticker
            ) TO '{self.curated_dir / "prices.parquet"}' (FORMAT PARQUET)
            """
        )
        con.close()

    # -- reading ---------------------------------------------------------
    def load_prices(self, as_of: date | None = None) -> pd.DataFrame:
        """Return a wide DataFrame: index=date, columns=ticker, values=close.

        `as_of=None` reads the curated latest view. Passing a date replays only
        snapshots captured on or before it -- this is your point-in-time view.
        """
        con = duckdb.connect()
        try:
            if as_of is None:
                path = self.curated_dir / "prices.parquet"
                if not path.exists():
                    raise FileNotFoundError(
                        f"No curated prices at {path}. Run ingestion first "
                        "(scripts/ingest.py) or use the synthetic generator."
                    )
                long = con.execute(f"SELECT * FROM read_parquet('{path}')").df()
            else:
                glob = str(self.raw_dir / "prices_captured=*.parquet")
                long = con.execute(
                    f"""
                    SELECT date, ticker, close, volume FROM (
                        SELECT *, ROW_NUMBER() OVER (
                            PARTITION BY date, ticker ORDER BY captured_on DESC
                        ) AS rn
                        FROM read_parquet('{glob}')
                        WHERE captured_on <= DATE '{as_of.isoformat()}'
                    ) WHERE rn = 1
                    """
                ).df()
        finally:
            con.close()
        wide = long.pivot(index="date", columns="ticker", values="close").sort_index()
        wide.index = pd.to_datetime(wide.index)
        wide.columns.name = None
        return wide

    def load_rate(self, series: str, as_of: date | None = None) -> pd.Series:
        """Reads the rates for the selected series.
        If as_of is None, returns the latest version of all rates """
        # Rate schema: (date, series, captured_on, value)
        # check for whether there are any rates parquet files
        pattern = self.raw_dir / "rates_captured=*.parquet"
        if not list(self.raw_dir.glob(pattern.name)):
            raise FileNotFoundError("No rates parquets found. Run write_rates first.")

        con = duckdb.connect()
        # if as_of has a value, restrict captured_on to before as_of
        as_of_clause = "" if as_of is None else f"AND captured_on <= '{as_of.isoformat()}'"

        # load date, values prioritized by most recent captured_on
        query = f"""
                SELECT date, value FROM (
                    SELECT *, ROW_NUMBER() OVER (
                        PARTITION BY date, series ORDER BY captured_on DESC
                    ) AS rn
                    FROM read_parquet('{pattern}') 
                    WHERE series = '{series}' {as_of_clause}
                ) WHERE rn = 1
                """
        try:
            raw = con.execute(query).df()
        finally:
            con.close()

        if raw.empty:
            raise FileNotFoundError("Rates series loaded empty.")
        # set the date column as the index, and select the value column
        s = raw.set_index("date")["value"]
        # convert the index to a DatetimeIndex
        s.index = pd.to_datetime(s.index)
        # drop the index name
        s.index.name = None
        # sort the result by the index and rename it to the requested series
        return s.sort_index().rename(series)

    def snapshots(self) -> list[date]:
        out = []
        for p in sorted(self.raw_dir.glob("prices_captured=*.parquet")):
            out.append(date.fromisoformat(p.stem.split("=")[1]))
        return out


class InMemoryStore(PriceStore):
    """For tests and synthetic runs -- same contract, no disk."""

    def __init__(self) -> None:
        self._snaps: dict[date, pd.DataFrame] = {} # Key: the captured_on date of the snapshot. Value: price frame (date, ticker, close, volume?)
        self._rates: dict[date, pd.DataFrame] = {} # Key: the captured_on date of the snapshot. Value: rate frame (date, series, value)

    def write_snapshot(self, df: pd.DataFrame, captured_on: date | None = None) -> Path:
        _validate_long_prices(df)
        self._snaps[captured_on or datetime.now(tz=timezone.utc).date()] = df.copy()
        return Path("<memory>")

    def load_prices(self, as_of: date | None = None) -> pd.DataFrame:
        keys = sorted(k for k in self._snaps if as_of is None or k <= as_of)
        if not keys:
            raise FileNotFoundError("No snapshots written.")
        long = pd.concat([self._snaps[k].assign(captured_on=k) for k in keys])
        long = long.sort_values("captured_on").drop_duplicates(["date", "ticker"], keep="last")
        wide = long.pivot(index="date", columns="ticker", values="close").sort_index()
        wide.index = pd.to_datetime(wide.index)
        wide.columns.name = None
        return wide

    def write_rates(self, df: pd.DataFrame, captured_on: date | None = None) -> Path:
        """df: long frame: (date, series id, value) -> path written to. 
        Validates that (date, series) keys never repeat or are missing."""
        _validate_rates(df)
        self._rates[captured_on or datetime.now(tz=timezone.utc).date()] = df.copy()
        return Path("<memory>")

    def load_rate(self, series: str, as_of: date | None = None) -> pd.Series:
        """series: FRED series ID -> (date, value) series of rates"""
        keys = sorted(k for k in self._rates if as_of is None or k <= as_of)
        if not keys:
            raise FileNotFoundError("No rate snapshots written.")
        rates = pd.concat([self._rates[k].assign(captured_on=k) for k in keys])
        rates = rates.sort_values("captured_on").drop_duplicates(["date", "series"], keep="last")
        filtered = rates[rates["series"] == series]
        if filtered.empty:
            raise FileNotFoundError(f"No data found for series '{series}'.")
        # set the date as the index, select the value column
        s = filtered.set_index("date")["value"]
        # convert the index to datetime
        s.index = pd.to_datetime(s.index)
        s.index.name = None
        # sort the results by the index and rename to the series name
        return s.sort_index().rename(series)
        
        

    def snapshots(self) -> list[date]:
        return sorted(self._snaps)


REQUIRED_PRICE_COLUMNS = {"date", "ticker", "close"}


def _validate_long_prices(df: pd.DataFrame) -> None:
    missing = REQUIRED_PRICE_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Price frame missing required columns: {sorted(missing)}")
    if df[["date", "ticker"]].duplicated().any():
        raise ValueError("Price frame has duplicate (date, ticker) rows.")
    if (df["close"] <= 0).any():
        raise ValueError("Non-positive close prices found.")


REQUIRED_RATE_COLUMNS = {"date", "series", "value"}


def _validate_rates(df: pd.DataFrame) -> None:
    """df: DataFrame of (date, series, value). 
    Enforces no missing columns or repeated (date, series) keys"""
    missing = REQUIRED_RATE_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Rate frame missing required columns: {sorted(missing)}")
    if df[["date", "series"]].duplicated().any():
        raise ValueError("Rate frame has duplicated (date, series) rows")
