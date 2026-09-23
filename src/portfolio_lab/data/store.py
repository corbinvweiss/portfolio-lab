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
        self._collapse_snapshots("prices", ("date", "ticker"), ("close", "volume"))
        return out

    def write_rates(self, df: pd.DataFrame, captured_on: date | None = None) -> Path:
        captured_on = captured_on or datetime.now(tz=timezone.utc).date()
        _validate_long_rates(df)
        out = self.raw_dir / f"rates_captured={captured_on.isoformat()}.parquet"
        df = df.copy()
        df["captured_on"] = pd.Timestamp(captured_on)
        df.to_parquet(out, index=False)
        self._collapse_snapshots("rates", ("date", "series"), ("value",))
        return out

    def _collapse_snapshots(
        self, prefix: str, key_cols: tuple[str, ...], value_cols: tuple[str, ...]
    ) -> None:
        """Collapse all snapshots to the latest observation per key_cols set"""
        con = duckdb.connect()
        con.execute(
            f"""
            COPY (
                {self._latest_per_key_sql(prefix, key_cols=key_cols, value_cols=value_cols)}
                ORDER BY {', '.join(key_cols)}
            ) TO '{self.curated_dir / f"{prefix}.parquet"}' (FORMAT PARQUET)"""
        )
        con.close()

    def _latest_per_key_sql(
        self,
        prefix: str,
        key_cols: tuple[str, ...],
        value_cols: tuple[str, ...],
        as_of: date | None = None,
        extra_where: str = "",
    ) -> str:
        """return the latest values per key with optional as_of date.

        extra_where is simply the predicate with no AND, e.g. series = {series}"""
        pattern = self.raw_dir / f"{prefix}_captured=*.parquet"
        if not any(self.raw_dir.glob(pattern.name)):
            raise FileNotFoundError(
                f"No {prefix} snapshots in {self.raw_dir}. "
                "Run `plab ingest` or `plab ingest-rates` first."
            )
        preds: list[str] = []
        where_clause: str = ""
        if as_of is not None:
            preds.append(f"captured_on <= DATE '{as_of.isoformat()}'")
        if extra_where != "":
            preds.append(extra_where)
        if len(preds) > 0:
            where_clause = f"WHERE {' AND '.join(preds)}"

        sql = f"""
            SELECT {", ".join(key_cols + value_cols)}
            FROM (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY {", ".join(key_cols)}
                    ORDER BY captured_on DESC
                ) AS rn
                FROM read_parquet('{pattern}')
                {where_clause}
            ) WHERE rn = 1"""

        return sql

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
                        f"No curated prices at {path}. Run `plab ingest` first "
                        "or use the synthetic generator."
                    )
                long = con.execute(f"SELECT * FROM read_parquet('{path}')").df()
            else:
                long = con.execute(self._latest_per_key_sql(
                    "prices", ("date", "ticker"), ("close", "volume"), as_of=as_of)).df()
        finally:
            con.close()
        wide = long.pivot(index="date", columns="ticker", values="close").sort_index()
        wide.index = pd.to_datetime(wide.index)
        wide.columns.name = None
        return wide

    def load_rate(self, series: str, as_of: date | None = None) -> pd.Series:
        """Reads the rates for the selected series.
        If as_of is None, returns the latest curated version of all rates """
        # Rate schema: (date, series, captured_on, value)
        # check for whether there are any rates parquet files
        con = duckdb.connect()
        try:
            if as_of is None:
                path = self.curated_dir / "rates.parquet"
                if not path.exists():
                    raise FileNotFoundError(
                        f"No curated rates at {path}. Run `plab ingest-rates` first."
                    )
                # `?` is DuckDB parameter binding: the series name never enters the SQL text.
                long = con.execute(
                    f"SELECT * FROM read_parquet('{path}') WHERE series = ?", [series]
                ).df()
            else:
                sql = self._latest_per_key_sql(
                    "rates", ("date", "series"), ("value",), as_of=as_of, extra_where="series = ?"
                )
                long = con.execute(sql, [series]).df()
        finally:
            con.close()

        if long.empty:
            raise FileNotFoundError(f"Rates for series '{series}' loaded empty.")
        # set the index to the date column, and select the value, reshaping to a series.
        s = long.set_index("date")["value"]
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
        # Both dicts: key is the captured_on date, value is the long frame as written.
        self._snaps: dict[date, pd.DataFrame] = {}  # (date, ticker, close[, volume])
        self._rates: dict[date, pd.DataFrame] = {}  # (date, series, value)

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
        _validate_long_rates(df)
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


def _validate_long_rates(df: pd.DataFrame) -> None:
    """df: DataFrame of (date, series, value).
    Enforces no missing columns or repeated (date, series) keys"""
    missing = REQUIRED_RATE_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Rate frame missing required columns: {sorted(missing)}")
    if df[["date", "series"]].duplicated().any():
        raise ValueError("Rate frame has duplicated (date, series) rows")
