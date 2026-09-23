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
        "ticker,name,sleeve,member_from,member_to\n"
        "SPY,s,equity,2015-01-02,\n"
        "GLD,g,real_asset,2015-01-02,\n"
    )
    cfg = {"data": {"source": "synthetic", "n_days": 400, "universe": str(tmp_path / "u.csv")}}
    wide = load_prices(cfg)
    assert list(wide.columns) == ["GLD", "SPY"] or list(wide.columns) == ["SPY", "GLD"]


def test_experiment_default_universe_unchanged():
    from portfolio_lab.data.universe import TICKERS
    from portfolio_lab.experiment import load_prices
    wide = load_prices({"data": {"source": "synthetic", "n_days": 400}})
    assert set(wide.columns) == set(TICKERS)
