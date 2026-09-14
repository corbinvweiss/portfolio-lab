"""Storage contract, including the point-in-time replay."""
from datetime import date

import pandas as pd
import pytest

from portfolio_lab.data.store import InMemoryStore, ParquetDuckStore


def _frame(dates, tickers, close):
    rows = [{"date": d, "ticker": t, "close": close, "volume": 1.0}
            for d in dates for t in tickers]
    return pd.DataFrame(rows)


@pytest.fixture(params=["memory", "parquet"])
def store(request, tmp_path):
    return InMemoryStore() if request.param == "memory" else ParquetDuckStore(tmp_path)


def test_roundtrip(store):
    dates = [date(2024, 1, 2), date(2024, 1, 3)]
    store.write_snapshot(_frame(dates, ["AAA", "BBB"], 100.0), captured_on=date(2024, 1, 4))
    wide = store.load_prices()
    assert list(wide.columns) == ["AAA", "BBB"]
    assert wide.shape == (2, 2)


def test_later_snapshot_wins(store):
    dates = [date(2024, 1, 2)]
    store.write_snapshot(_frame(dates, ["AAA"], 100.0), captured_on=date(2024, 1, 3))
    store.write_snapshot(_frame(dates, ["AAA"], 111.0), captured_on=date(2024, 1, 10))
    assert store.load_prices()["AAA"].iloc[0] == pytest.approx(111.0)


def test_point_in_time_replay(store):
    """The reason snapshots exist: see the data as it looked back then."""
    dates = [date(2024, 1, 2)]
    store.write_snapshot(_frame(dates, ["AAA"], 100.0), captured_on=date(2024, 1, 3))
    store.write_snapshot(_frame(dates, ["AAA"], 111.0), captured_on=date(2024, 1, 10))
    as_of = store.load_prices(as_of=date(2024, 1, 5))
    assert as_of["AAA"].iloc[0] == pytest.approx(100.0), "restated value leaked backwards"


def test_rejects_bad_frames(store):
    with pytest.raises(ValueError):
        store.write_snapshot(pd.DataFrame({"date": [date(2024, 1, 2)]}), date(2024, 1, 3))
    dup = _frame([date(2024, 1, 2)] * 2, ["AAA"], 100.0)
    with pytest.raises(ValueError):
        store.write_snapshot(dup, date(2024, 1, 3))
