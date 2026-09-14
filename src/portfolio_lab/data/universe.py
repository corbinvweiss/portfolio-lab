"""The traded universe.

Kept deliberately small and liquid: twelve ETFs spanning equity, duration,
credit, real assets and commodities. Small enough that a full backtest runs in
seconds, diverse enough that risk budgeting actually has something to do.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Asset:
    ticker: str
    name: str
    sleeve: str


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


def sleeve_of(ticker: str) -> str:
    return SLEEVES[ticker]
