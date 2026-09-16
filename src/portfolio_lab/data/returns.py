"""returns.py
Calculates returns in the following ways:
annualise_vol, 
compound, 
daily_rate_from_annual, 
log_returns, 
simple_returns
"""
import numpy as np
import pandas as pd


def simple_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """prices: wide (index=date, columns=ticker) -> same shape"""
    # return rate is each price divided by previous price (prices.shift(1))
    return prices/prices.shift(1) - 1


def log_returns(prices: pd.DataFrame) -> pd.DataFrame: 
    """prices: wide (index=date, columns=ticker) -> same shape"""
    # .diff() runs the same function with the index shifted down by 1
    # same as .shift(1)
    return np.log(prices).diff()
    
def annualise_vol(daily: pd.Series) -> float:
    """daily: series of daily returns -> annualised volatility"""
    # Variance is the mean squared deviation of returns from their mean.
    # Accumulated over 252 days of market trading, a year's variance = var * 252
    # Volatility is the standard deviation of returns = sqrt(var)
    # Accumulated over 252 days, a year's volatility is sqrt(var * 252) = below
    return daily.std() * np.sqrt(252)

def daily_rate_from_annual(annual: pd.Series) -> pd.Series:
    """annual: annual return rates for a set of tickers -> daily return rate for each ticker"""
    # inverse of return compounded for 252 days = (1+r)^252 - 1
    return (1 + annual/100)**(1/252) - 1

def compound(returns: pd.Series) -> float:
    """returns: a series of simple returns for one ticker -> growth factor over the period"""
    return (1 + returns).prod()

