"""
Pre-trade estimates: the intraday volume curve, its forecast, average daily
volume (ADV) and volatility.

US stocks trade most at the open and close and least around midday, a U-shaped
curve. VWAP needs a forecast of the day's curve. Every forecast and estimate
here uses only days strictly before the trade date, enforced by `past_days`;
using the trade date's own data would be look-ahead bias.
"""
import numpy as np
import pandas as pd


def volume_fractions(bucketed: pd.DataFrame) -> pd.DataFrame:
    """Share of each day's volume traded in each bucket.

    Returns a DataFrame indexed by date (sorted) with one column per bucket.
    Each row sums to 1. Days with a missing bucket are dropped.
    """
    by_day = bucketed.pivot(index="date", columns="bucket", values="volume").dropna()
    return by_day.div(by_day.sum(axis=1), axis=0).sort_index()


def past_days(df: pd.DataFrame, date, lookback: int) -> pd.DataFrame:
    """The `lookback` rows of a date-indexed table strictly before `date`.

    This is the look-ahead guard used by every estimate in this module.
    Raises ValueError if fewer than `lookback` earlier rows exist.
    """
    past = df[df.index < date].tail(lookback)
    if len(past) < lookback:
        raise ValueError(f"need {lookback} past days before {date}, only have {len(past)}")
    return past


def forecast_profile(fractions: pd.DataFrame, date, lookback: int) -> np.ndarray:
    """Forecast of the day's volume curve: the average curve of the previous `lookback` days.

    Returns an array with one value per bucket, summing to 1.
    """
    curve = past_days(fractions, date, lookback).mean(axis=0).to_numpy()
    return curve / curve.sum()


def realized_profile(fractions: pd.DataFrame, date) -> np.ndarray:
    """The day's actual volume curve. Used only by the oracle benchmark and to measure forecast error."""
    return fractions.loc[date].to_numpy()


def profile_forecast_error(forecast: np.ndarray, realized: np.ndarray) -> float:
    """Fraction of the order placed in the wrong buckets: half the L1 distance between the curves.

    0 means a perfect forecast; 1 means the curves do not overlap at all.
    """
    return 0.5 * sum(np.abs(forecast - realized))


# ---------------------------------------------------------------- daily estimates

def daily_table(bucketed: pd.DataFrame) -> pd.DataFrame:
    """One row per date with the day's total volume and closing price."""
    return bucketed.groupby("date").agg(volume=("volume", "sum"), close=("close", "last"))


def estimate_adv(daily: pd.DataFrame, date, lookback: int) -> float:
    """Average daily volume over the previous `lookback` days."""
    return float(past_days(daily, date, lookback)["volume"].mean())


def estimate_sigma_bps(daily: pd.DataFrame, date, lookback: int) -> float:
    """Daily volatility in bps: standard deviation of the previous `lookback` close-to-close returns.

    The first day in the data has no previous close. Its missing return is
    dropped after the window is selected, so the earliest test day uses one
    return fewer.
    """
    returns = daily["close"].pct_change()
    past = past_days(returns.to_frame("r"), date, lookback)["r"].dropna()
    return float(past.std() * 10_000)
