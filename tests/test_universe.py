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