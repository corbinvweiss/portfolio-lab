"""The traded universe, as point-in-time data rather than a constant.

Why this exists: a hardcoded list of tickers is a decision made today applied to
a backtest that starts years ago. Every name in it is one you already know
survived and stayed interesting, so the backtest is quietly handed an answer
key. That is survivorship bias, and on real equity universes it is worth one to
two percent a year of fake return.

The fix is to treat membership as a function of time. `Asset` carries a
`[member_from, member_to]` window and `Universe.members(as_of)` answers "which
names were held on this date" — the universe-side counterpart to
`PriceStore.load_prices(as_of=...)`, which answers "what was known on this
date". Both are lookahead controls, and the no-lookahead tests are only
meaningful when both hold.

`Universe.from_csv` loads the seed table (`configs/universe_week1.csv`);
`DEFAULT_UNIVERSE` keeps the original twelve-ETF list alive as the offline
default, since the synthetic config generates prices from `TICKERS` and needs no
ingested data. Week 5 replaces the hand-made seed with vendor membership and
retires the in-code default.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Asset:
    """One tradeable name and the window over which it belongs to a universe.

    `member_from` is the first date the asset is held and `member_to` the last —
    the window is CLOSED at both ends, so an asset deleted on 2018-06-30 is still
    a member that day and earns that day's return. Reading `member_to` as the
    first non-member day instead is a one-day error at every rebalance, which
    compounds into alpha that is not there.

    Both fields default so the twelve-ETF `ETF_SLEEVE` literals below still
    construct positionally. `date(1900, 1, 1)` is a deliberately absurd sentinel
    meaning "no membership data": it keeps the comparison in `members()` uniform
    without a `None` branch on both ends, and nobody will ever mistake it for a
    researched listing date. A plausible-looking fabricated date would be worse.

    Frozen, so an `Asset` is hashable and safe to use as a dict key.
    """

    ticker: str
    name: str
    sleeve: str
    member_from: date = date(1900, 1, 1)
    member_to: date | None = None


ETF_SLEEVE: tuple[Asset, ...] = (
    Asset("SPY", "US large cap equity", "equity"),
    Asset("QQQ", "US growth equity", "equity"),
    Asset("IWM", "US small cap equity", "equity"),
    Asset("EFA", "Developed ex-US equity", "equity"),
    Asset("EEM", "Emerging market equity", "equity"),
    Asset("TLT", "US long treasury", "duration"),
    Asset("IEF", "US intermediate treasury", "duration"),
    Asset("LQD", "US investment grade credit", "credit"),
    Asset("HYG", "US high yield credit", "credit"),
    Asset("GLD", "Gold", "real_asset"),
    Asset("DBC", "Broad commodities", "real_asset"),
    Asset("VNQ", "US REITs", "real_asset"),
)

TICKERS: tuple[str, ...] = tuple(a.ticker for a in ETF_SLEEVE)
SLEEVES: dict[str, str] = {a.ticker: a.sleeve for a in ETF_SLEEVE}


@dataclass(frozen=True)
class Universe:
    """An ordered, immutable set of assets with membership windows.

    Frozen because a run has to be reproducible from a YAML file plus a git SHA:
    if a signal or allocator could append a ticker or reassign a sleeve to the
    universe it was handed, the config would no longer describe the run that
    happened, and the failure would be silent and surface weeks later. Holding
    `assets` as a tuple of frozen `Asset`s — rather than a list — is what makes
    that immutability real, since `frozen=True` only blocks rebinding the field,
    not mutating what it points at.

    `tickers` and `sleeves` are derived on access rather than stored, so
    `assets` stays the single source of truth and the three cannot drift apart.
    Order is part of the contract: it is file order, and callers index against
    it positionally.
    """

    assets: tuple[Asset, ...]

    @property
    def tickers(self) -> tuple[str, ...]:
        """Every ticker, in file order."""
        return tuple(asset.ticker for asset in self.assets)

    @property
    def sleeves(self) -> dict[str, str]:
        """Map each ticker to its sleeve, for the risk-budgeting allocators."""
        return {a.ticker: a.sleeve for a in self.assets}

    @classmethod
    def from_csv(cls, path: str) -> Universe:
        """Load a universe from a `ticker,name,sleeve,member_from,member_to` CSV.

        Parsed with `csv.DictReader`, not pandas: eight rows do not need a
        DataFrame, and the conversions stay explicit. `DictReader` hands back
        every field as a string and an empty `member_to` as `""`, so the blank
        case is decided here rather than by dtype inference — `pd.read_csv`
        would type that column differently depending on whether any row in the
        file happens to be populated.

        `newline=""` is required by the csv module so newlines inside quoted
        fields survive; `utf-8-sig` strips the BOM that anything round-tripped
        through Excel carries, which would otherwise corrupt the first column
        name and raise a baffling `KeyError`.
        """
        assets: list[Asset] = []
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                asset = Asset(
                    row["ticker"],
                    row["name"],
                    row["sleeve"],
                    date.fromisoformat(row["member_from"]),
                    date.fromisoformat(v) if (v := row["member_to"]) else None,
                )
                assets.append(asset)
        return cls(tuple(assets))

    def members(self, as_of: date) -> tuple[str, ...]:
        """Tickers held on `as_of`, in file order.

        The window is closed at both ends: `member_from <= as_of <= member_to`,
        with an unset `member_to` meaning still a member. See `Asset` for why
        the end date is inclusive.
        """
        return tuple(
            asset.ticker
            for asset in self.assets
            if asset.member_from <= as_of
            and (asset.member_to is None or asset.member_to >= as_of)
        )


DEFAULT_UNIVERSE = Universe(ETF_SLEEVE)
