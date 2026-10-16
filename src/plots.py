"""
Figures for the README:

    volume_profile_<ticker>.png   the U-shaped intraday volume curve against TWAP's flat line
    one_day.png                   each strategy's cumulative schedule on one day
    slippage_box.png              distribution of VWAP slippage by strategy
    cost_vs_size.png              mean impact against order size
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")            # draw to files; no window needed
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np               # noqa: E402
import pandas as pd              # noqa: E402

import config                    # noqa: E402

FIG_DIR = Path(config.RESULTS_DIR) / "figures"


def bucket_times(n=config.N_BUCKETS):
    """Bucket start times as "HH:MM" labels."""
    starts = [config.OPEN_MINUTE + i * config.BUCKET_MINUTES for i in range(n)]
    return [f"{m // 60:02d}:{m % 60:02d}" for m in starts]


def _save(fig, name: str):
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG_DIR / name, dpi=150)
    plt.close(fig)
    print(f"[plots] saved {FIG_DIR / name}")


def plot_volume_profile(fractions: pd.DataFrame, ticker: str):
    """Average share of daily volume per bucket, its 10-90% range across days, and TWAP's flat share."""
    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(fractions.shape[1])
    mean = fractions.mean(axis=0)
    lo, hi = fractions.quantile(0.1), fractions.quantile(0.9)

    ax.fill_between(x, lo, hi, alpha=0.25, label="10–90% range across days")
    ax.plot(x, mean, marker="o", label="average volume share")
    ax.axhline(1 / len(x), linestyle="--", color="grey", label="TWAP (equal slices)")

    ax.set_xticks(x[::2])
    ax.set_xticklabels(bucket_times()[::2], rotation=45)
    ax.set_ylabel("share of daily volume")
    ax.set_title(f"{ticker}: intraday volume is U-shaped")
    ax.legend()
    _save(fig, f"volume_profile_{ticker}.png")


def plot_one_day(day: pd.DataFrame, schedules: dict, ticker: str, date):
    """Cumulative fraction of the order completed through one day, per strategy, against market volume."""
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for name, s in schedules.items():
        ax.plot(np.cumsum(s) / s.sum(), label=name)
    vol = day["volume"].to_numpy()
    ax.plot(np.cumsum(vol) / vol.sum(), "k:", linewidth=2, label="market volume")

    x = np.arange(len(vol))
    ax.set_xticks(x[::2])
    ax.set_xticklabels(bucket_times()[::2], rotation=45)
    ax.set_ylabel("fraction of order completed")
    ax.set_title(f"{ticker} {date}: execution schedules")
    ax.legend()
    _save(fig, "one_day.png")


def plot_slippage_box(results: pd.DataFrame, metric: str, pct_adv: float):
    """Box plot of `metric` by strategy for one order size."""
    fig, ax = plt.subplots(figsize=(8, 5))
    subset = results[results["pct_adv"] == pct_adv]
    subset.boxplot(column=metric, by="strategy", ax=ax)
    ax.axhline(0, color="grey", linewidth=0.8)
    ax.set_ylabel("bps (positive = cost)")
    ax.set_title(f"{metric} at {pct_adv:.0%} of ADV")
    fig.suptitle("")   # remove the automatic title pandas adds to grouped box plots
    _save(fig, "slippage_box.png")


def plot_cost_vs_size(results: pd.DataFrame, metric: str = "impact_bps"):
    """Mean `metric` against order size, one line per strategy."""
    fig, ax = plt.subplots(figsize=(8, 5))
    means = results.groupby(["pct_adv", "strategy"])[metric].mean().unstack()
    means.plot(marker="o", ax=ax)
    ax.set_xticks(config.ORDER_SIZES_PCT_ADV)
    ax.set_xticklabels([f"{p:.0%}" for p in config.ORDER_SIZES_PCT_ADV])
    ax.set_xlabel("order size (% of ADV)")
    ax.set_ylabel("mean market impact (bps)")
    ax.set_title("Impact grows with order size; VWAP grows slower")
    _save(fig, "cost_vs_size.png")
