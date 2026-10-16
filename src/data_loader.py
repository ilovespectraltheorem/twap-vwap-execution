"""
Market data: download 5-minute bars, cache them, clean them and aggregate them
into fixed intraday buckets.

    load_bars -> clean_bars -> to_buckets

`build_dataset(ticker)` returns one row per (date, bucket), sorted by date then
bucket, with columns:

    date                     datetime.date
    bucket                   int, 0 .. N_BUCKETS - 1
    open, high, low, close   float
    volume                   float, shares traded in the bucket
    vwap                     float, volume-weighted average price in the bucket
"""
from pathlib import Path

import numpy as np
import pandas as pd

import config

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def download_bars(ticker: str) -> pd.DataFrame:
    """Download the last `HISTORY_DAYS` of intraday bars from Yahoo Finance.

    Yahoo refuses intraday requests spanning more than about 7 days, so the
    history is fetched in 7-day windows and concatenated. Empty windows
    (weekends, holidays, today before the open) are skipped.

    Raises RuntimeError if nothing is returned at all, which usually means
    Yahoo is rate-limiting the connection.
    """
    import yfinance as yf   # imported here so the rest of the project runs without it

    end = pd.Timestamp.today().normalize() + pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=config.HISTORY_DAYS)

    parts = []
    window_start = start
    while window_start < end:
        window_end = min(window_start + pd.Timedelta(days=7), end)
        df = yf.download(ticker, start=window_start, end=window_end, interval=config.INTERVAL,
                         auto_adjust=False, progress=False, multi_level_index=False)
        if not df.empty:
            parts.append(df)
        window_start = window_end

    if not parts:
        raise RuntimeError(f"No data downloaded for {ticker}; Yahoo may be rate-limiting, retry later")
    df = pd.concat(parts)
    df = df[~df.index.duplicated()]   # windows can overlap at their edges
    return df.sort_index()


def load_bars(ticker: str) -> pd.DataFrame:
    """Raw bars for `ticker`, cached in data/<ticker>_<interval>.csv.

    Yahoo keeps only about 60 days of intraday history, so the cached CSVs are
    the project's permanent dataset: download once, then always read from disk.
    """
    path = DATA_DIR / f"{ticker}_{config.INTERVAL}.csv"
    if path.exists():
        return pd.read_csv(path, index_col=0)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = download_bars(ticker)
    df.to_csv(path)
    return df


def clean_bars(raw: pd.DataFrame) -> pd.DataFrame:
    """Regular-hours bars with lowercase OHLCV columns and a New York time index.

    - Converts timestamps to New York time, which handles daylight-saving changes.
    - Keeps bars starting from the open up to, but not including, the close.
    - Drops bars with no price, and days with fewer than MIN_BARS_PER_DAY bars
      (early closes and data gaps). Zero-volume bars are kept.
    """
    df = raw.copy()
    df.columns = [name.lower() for name in df.columns]
    df = df[["open", "high", "low", "close", "volume"]]
    df.index = pd.to_datetime(df.index, utc=True).tz_convert(config.TZ)
    df = df.between_time(config.MARKET_OPEN, config.MARKET_CLOSE, inclusive="left")
    df = df.dropna(subset=["close"])

    bars_per_day = df.groupby(df.index.date).size()
    full_days = bars_per_day[bars_per_day >= config.MIN_BARS_PER_DAY].index
    df = df[pd.Index(df.index.date).isin(full_days)]

    df["volume"] = df["volume"].astype(float)
    return df


def to_buckets(bars: pd.DataFrame, bucket_minutes: int = config.BUCKET_MINUTES) -> pd.DataFrame:
    """Aggregate clean bars into fixed buckets within each day.

    Each bucket keeps the first open, highest high, lowest low, last close and
    total volume of its bars. Its VWAP is estimated from each bar's typical
    price (high + low + close) / 3, weighted by the bar's volume; a bucket with
    no volume uses its close.
    """
    df = bars.copy()
    minutes_since_open = bars.index.hour * 60 + bars.index.minute - config.OPEN_MINUTE
    df["date"] = bars.index.date
    df["bucket"] = minutes_since_open // bucket_minutes
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    df["pv"] = typical_price * df["volume"]

    buckets = df.groupby(["date", "bucket"]).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        pv=("pv", "sum"),
    )
    buckets["vwap"] = np.where(buckets["volume"] > 0, buckets["pv"] / buckets["volume"], buckets["close"])
    return buckets.drop(columns="pv").reset_index()


def build_dataset(ticker: str) -> pd.DataFrame:
    """Load, clean and bucket one ticker, keeping only days that have all N_BUCKETS buckets."""
    bucketed = to_buckets(clean_bars(load_bars(ticker)))
    counts = bucketed.groupby("date")["bucket"].transform("count")
    return bucketed[counts == config.N_BUCKETS].reset_index(drop=True)
