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
    def snapshots(self) -> list[date]: ...


class ParquetDuckStore(PriceStore):
    """Parquet files on disk, DuckDB as the query engine. No server process.

    Long-format schema, one row per (date, ticker):
        date: DATE, ticker: VARCHAR, close: DOUBLE, volume: DOUBLE
    `close` is split- and dividend-adjusted (total return).
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

    def snapshots(self) -> list[date]:
        out = []
        for p in sorted(self.raw_dir.glob("prices_captured=*.parquet")):
            out.append(date.fromisoformat(p.stem.split("=")[1]))
        return out


class InMemoryStore(PriceStore):
    """For tests and synthetic runs -- same contract, no disk."""

    def __init__(self) -> None:
        self._snaps: dict[date, pd.DataFrame] = {}

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

    def snapshots(self) -> list[date]:
        return sorted(self._snaps)


REQUIRED_COLUMNS = {"date", "ticker", "close"}


def _validate_long_prices(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Price frame missing required columns: {sorted(missing)}")
    if df[["date", "ticker"]].duplicated().any():
        raise ValueError("Price frame has duplicate (date, ticker) rows.")
    if (df["close"] <= 0).any():
        raise ValueError("Non-positive close prices found.")
