"""
Execution quality metrics, all in basis points with one sign convention:
positive = cost, for buys and sells alike.

    Implementation shortfall (IS)   average fill vs the arrival price (09:30 open).
                                    Includes the market's move during the day.
    VWAP slippage                   average fill vs the day's market VWAP.
                                    The standard benchmark for a VWAP algorithm.
"""
import numpy as np
import pandas as pd


def avg_exec_price(fills: pd.DataFrame) -> float:
    """Share-weighted average fill price."""
    return (fills["qty"] * fills["fill_px"]).sum() / fills["qty"].sum()


def market_vwap(day: pd.DataFrame) -> float:
    """The day's market VWAP: bucket VWAPs weighted by bucket volume."""
    return (day["vwap"] * day["volume"]).sum() / day["volume"].sum()


def arrival_price(day: pd.DataFrame) -> float:
    """Decision price: the open of the first bucket."""
    return float(day["open"].iloc[0])


def slippage_bps(price: float, benchmark: float, side: int) -> float:
    """Signed distance from a benchmark in bps; positive is a cost.

    Buying at 101 against 100 gives +100 bps; selling at 101 against 100 gives -100 bps.
    """
    return side * (price - benchmark) / benchmark * 10_000


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    """Mean, std, median and count of IS and VWAP slippage per order size and strategy.

    The mean is the expected cost; the standard deviation is the risk, how
    unpredictable the cost is from day to day.
    """
    return (results.groupby(["pct_adv", "strategy"])[["is_bps", "vwap_slip_bps"]]
            .agg(["mean", "std", "median", "count"])
            .round(2))


def paired_bootstrap_ci(results: pd.DataFrame, metric: str, strat_a: str, strat_b: str,
                        n_boot: int = 10_000, alpha: float = 0.05, seed: int = 42):
    """Mean of metric(a) - metric(b) and its bootstrap confidence interval.

    Both strategies trade the same ticker on the same day with the same order
    size, so the comparison is paired: differencing each row removes the day's
    market move, which is far larger than the effect being measured. The
    per-row differences are resampled with replacement `n_boot` times.

    Returns (mean_diff, ci_low, ci_high). An interval entirely below zero means
    strat_a is significantly cheaper.
    """
    wide = results.pivot_table(index=["ticker", "date", "pct_adv"],
                               columns="strategy", values=metric)
    diff = (wide[strat_a] - wide[strat_b]).dropna().to_numpy()
    rng = np.random.default_rng(seed)
    boot_means = rng.choice(diff, size=(n_boot, len(diff))).mean(axis=1)
    lo, hi = np.percentile(boot_means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(diff.mean()), float(lo), float(hi)
