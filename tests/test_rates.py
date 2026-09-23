"""Rates live beside prices in the store, with the same snapshot semantics."""
import io
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
    real_read_csv = pd.read_csv
    
    def fake_read_csv(url, **kwargs):
        assert "DTB3" in url
        return real_read_csv(io.StringIO(FRED_CSV), **kwargs)
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