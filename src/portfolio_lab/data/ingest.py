"""Fetch adjusted daily prices and write an append-only snapshot.

Run this on a machine with network access to the vendor:

    python scripts/ingest.py --start 2005-01-01

Note: yfinance is an optional dependency (`pip install -e '.[ingest]'`). It is a
scraper, not a contract -- it breaks. That is precisely why the store keeps
snapshots: when the vendor changes its adjustment methodology, you still have
what you saw before.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from .universe import TICKERS


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


def ingest(store, tickers=TICKERS, start: str = "2005-01-01", end: str | None = None):
    df = fetch_prices(tickers, start=start, end=end)
    path = store.write_snapshot(df, captured_on=date.today())
    return path, df
