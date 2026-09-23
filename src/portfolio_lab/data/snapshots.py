from datetime import date

import pandas as pd

from .store import PriceStore


def snapshot_diff(store: PriceStore, earlier: date, later: date, tol: float = 1e-9) -> pd.DataFrame:
    """Report closes restated between two snapshots.

    Returns (date, ticker, close_before, close_after, rel_change): one row per
    (date, ticker) present in both replays whose close differs by more than tol,
    sorted by date, ticker. Rows only in one snapshot are excluded (they are
    additions, not restatements).
    """
    before = _to_long(store.load_prices(as_of=earlier))
    after = _to_long(store.load_prices(as_of=later))
    merged = before.merge(
        after, how="inner", on=["date", "ticker"], suffixes=("_before", "_after")
    )
    diff = merged[(merged["close_after"] - merged["close_before"]).abs() > tol]
    return (
        diff.assign(rel_change=lambda d: d["close_after"] / d["close_before"] - 1)
        .sort_values(["date", "ticker"])
        .reset_index(drop=True)
    )


def _to_long(wide: pd.DataFrame) -> pd.DataFrame:
    """Stack a wide (index=date, columns=ticker) frame to long (date, ticker, close)."""
    return (
        wide.stack()
        .dropna()
        .rename("close")
        .rename_axis(["date", "ticker"])
        .reset_index()
    )
