"""Fetch adjusted daily prices and write an append-only snapshot.

Run this on a machine with network access to the vendor:

    python scripts/ingest.py --start 2005-01-01

Note: yfinance is an optional dependency (`pip install -e '.[ingest]'`). It is a
scraper, not a contract -- it breaks. That is precisely why the store keeps
snapshots: when the vendor changes its adjustment methodology, you still have
what you saw before.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .store import PriceStore
from .universe import TICKERS

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def fetch_prices(
    tickers: list[str] | tuple[str, ...] = TICKERS,
    start: str = "2005-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    """Return a long-format frame: date, ticker, close (adjusted), volume."""
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "yfinance is required for ingestion. Install with: pip install -e '.[ingest]'"
        ) from exc

    raw = yf.download(
        list(tickers), start=start, end=end, auto_adjust=True, progress=False, group_by="column"
    )
    if raw.empty:
        raise RuntimeError(
            "Vendor returned no data. Check network egress -- some sandboxes block "
            "finance endpoints. Run this on a machine that can reach the vendor."
        )

    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    volume = raw["Volume"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Volume"]]

    long = (
        close.stack().rename("close").reset_index()
        .rename(columns={"level_0": "date", "Date": "date", "level_1": "ticker", "Ticker": "ticker"})
    )
    vol_long = (
        volume.stack().rename("volume").reset_index()
        .rename(columns={"level_0": "date", "Date": "date", "level_1": "ticker", "Ticker": "ticker"})
    )
    out = long.merge(vol_long, on=["date", "ticker"], how="left")
    out["date"] = pd.to_datetime(out["date"]).dt.date
    out = out.dropna(subset=["close"])
    out = out[out["close"] > 0].reset_index(drop=True)
    return out


def fetch_fred(series_id: str, start: str) -> pd.DataFrame:
    """Fetch one FRED series as a long frame: date, series, value

    Reads the public graph CSV endpoint. FRED marks missing observations with
    "." and has used both DATE and observation_date as the date header, so the
    columns are renamed by position. Values are returned as published, in percent.
    """
    url = f"{FRED_URL}?id={series_id}"
    raw = pd.read_csv(url, na_values=".")
    if raw.columns[1] != series_id:
        raise ValueError(f"Expected FRED column {series_id!r}, got {raw.columns[1]!r}.")

    df = (
        # name the columns
        raw.set_axis(["date", "value"], axis="columns")
        # set the date column to datetime
        .assign(date=lambda d: pd.to_datetime(d["date"]))
        # filter dates >= start (including time of day)
        .loc[lambda d: d["date"] >= pd.Timestamp(start)]
        # drop null values
        .dropna(subset=["value"])
        # set the date column to dt.date (day rather than timestamp),
        # set the series column to series_id
        .assign(date=lambda d: d["date"].dt.date, series=series_id)
        # sort by dates ascending
        .sort_values("date")
        # reset the frame's row index to 0, 1, 2, and throw out the old index.
        .reset_index(drop=True)
    )
    return df[["date", "series", "value"]]


def ingest(store: PriceStore, tickers=TICKERS, start: str = "2005-01-01", end: str | None = None):
    df = fetch_prices(tickers, start=start, end=end)
    path = store.write_snapshot(df, captured_on=datetime.now(timezone.utc).date())
    return path, df


def ingest_rates(
    store: PriceStore,
    series_id: str = "DTB3",
    start: str = "2015-01-01",
) -> tuple[Path, pd.DataFrame]:
    df = fetch_fred(series_id, start=start)
    path = store.write_rates(df, captured_on=datetime.now(timezone.utc).date())
    return path, df
