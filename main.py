"""
Run the project.

    python main.py               backtest, print the report, save results and figures
    python main.py --no-plots    skip the figures
    python main.py --plots-only  redraw the figures from results/results.csv
"""
import argparse
from pathlib import Path

import pandas as pd

import config
from src import plots
from src.backtest import make_schedules, run_backtest
from src.data_loader import build_dataset
from src.metrics import paired_bootstrap_ci, summarize
from src.volume_profile import (daily_table, estimate_adv, forecast_profile,
                                realized_profile, volume_fractions)

RESULTS_CSV = Path(config.RESULTS_DIR) / "results.csv"


def report(results: pd.DataFrame):
    """Print the summary table, the VWAP vs TWAP significance tests and the forecast error."""
    print("\n=== Summary (bps, positive = cost) ===")
    print(summarize(results).to_string())

    print("\n=== Is VWAP cheaper than TWAP? (paired bootstrap, 95% CI of VWAP - TWAP) ===")
    for metric in ["impact_bps", "vwap_slip_bps", "is_bps"]:
        for pct in config.ORDER_SIZES_PCT_ADV:
            sub = results[results.pct_adv == pct]
            mean, lo, hi = paired_bootstrap_ci(sub, metric, "VWAP", "TWAP")
            if hi < 0:
                verdict = "VWAP cheaper"
            elif lo > 0:
                verdict = "TWAP cheaper"
            else:
                verdict = "no significant difference"
            print(f"{metric:>14}  {pct:>5.0%} ADV:  {mean:+7.2f} bps  [{lo:+.2f}, {hi:+.2f}]  {verdict}")

    print("\n=== Volume forecast error (fraction of order in the wrong bucket) ===")
    print(results.groupby("ticker")["forecast_error"].mean().round(3).to_string())


def make_plots(results: pd.DataFrame):
    """Draw the four README figures. The one-day example is the first ticker's last day at 5% of ADV."""
    ticker = config.TICKERS[0]
    bucketed = build_dataset(ticker)
    fractions = volume_fractions(bucketed)
    plots.plot_volume_profile(fractions, ticker)

    date = fractions.index[-1]
    day = bucketed[bucketed["date"] == date].sort_values("bucket")
    adv = estimate_adv(daily_table(bucketed), date, config.LOOKBACK_DAYS)
    schedules = make_schedules(0.05 * adv,
                               forecast_profile(fractions, date, config.LOOKBACK_DAYS),
                               realized_profile(fractions, date), adv)
    plots.plot_one_day(day, schedules, ticker, date)

    plots.plot_slippage_box(results, "vwap_slip_bps", pct_adv=0.05)
    plots.plot_cost_vs_size(results, "impact_bps")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TWAP vs VWAP execution backtest")
    parser.add_argument("--no-plots", action="store_true", help="skip the figures")
    parser.add_argument("--plots-only", action="store_true",
                        help="redraw the figures from results/results.csv")
    args = parser.parse_args()

    Path(config.RESULTS_DIR).mkdir(exist_ok=True)

    if args.plots_only:
        results = pd.read_csv(RESULTS_CSV, parse_dates=["date"])
    else:
        results = run_backtest(config.TICKERS)
        results.to_csv(RESULTS_CSV, index=False)
        print(f"[main] {len(results)} rows -> {RESULTS_CSV}")
        report(results)

    if not args.no_plots:
        make_plots(results)
