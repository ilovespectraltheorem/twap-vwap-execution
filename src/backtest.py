"""
The experiment loop: for every ticker, test day, order size and strategy,
build the schedule, simulate the fills and record one row of metrics.

The first LOOKBACK_DAYS days of each ticker are used only as history. The
output has one row per (ticker, date, pct_adv, strategy).
"""
import numpy as np
import pandas as pd

import config
from src.data_loader import build_dataset
from src.metrics import arrival_price, avg_exec_price, market_vwap, slippage_bps
from src.simulator import CostModel, simulate_execution
from src.strategies import cap_participation, twap_schedule, vwap_schedule
from src.volume_profile import (daily_table, estimate_adv, estimate_sigma_bps,
                                forecast_profile, profile_forecast_error,
                                realized_profile, volume_fractions)


def make_schedules(qty: float, forecast: np.ndarray, realized: np.ndarray,
                   adv: float) -> dict:
    """The four strategies' schedules for one order, as {name: shares per bucket}."""
    vwap = vwap_schedule(qty, forecast)
    return {
        "TWAP": twap_schedule(qty, len(forecast)),
        "VWAP": vwap,
        "VWAP_oracle": vwap_schedule(qty, realized),
        "VWAP_capped": cap_participation(vwap, forecast * adv, config.MAX_PARTICIPATION),
    }


def evaluate(day: pd.DataFrame, schedule: np.ndarray, ordered_qty: float,
             sigma_bps: float, cost: CostModel) -> dict:
    """Simulate one schedule on one day and return its scorecard.

    Prices and impact are averaged over the buckets actually traded.
    `fill_rate` is below 1 only when a participation cap left shares unfilled.
    """
    fills = simulate_execution(day, schedule, config.SIDE, sigma_bps, cost)
    traded = fills[fills["qty"] > 0]

    avg_px = avg_exec_price(traded)
    arrival_px = arrival_price(day)
    mkt_vwap = market_vwap(day)

    return {
        "avg_px": avg_px,
        "arrival_px": arrival_px,
        "mkt_vwap": mkt_vwap,
        "is_bps": slippage_bps(avg_px, arrival_px, config.SIDE),
        "vwap_slip_bps": slippage_bps(avg_px, mkt_vwap, config.SIDE),
        "impact_bps": float((traded["qty"] * traded["impact_bps"]).sum() / traded["qty"].sum()),
        "max_participation": float(fills["participation"].max()),
        "fill_rate": float(schedule.sum() / ordered_qty),
    }


def backtest_ticker(ticker: str, bucketed: pd.DataFrame, cost: CostModel) -> list:
    """All result rows for one ticker."""
    fractions = volume_fractions(bucketed)
    daily = daily_table(bucketed)
    rows = []

    for date in fractions.index[config.LOOKBACK_DAYS:]:
        day = bucketed[bucketed["date"] == date].sort_values("bucket")

        # Pre-trade estimates: only data from days before `date`.
        forecast = forecast_profile(fractions, date, config.LOOKBACK_DAYS)
        adv = estimate_adv(daily, date, config.LOOKBACK_DAYS)
        sigma = estimate_sigma_bps(daily, date, config.LOOKBACK_DAYS)
        # The realized curve, for the oracle benchmark and forecast error only.
        realized = realized_profile(fractions, date)
        fc_error = profile_forecast_error(forecast, realized)

        for pct in config.ORDER_SIZES_PCT_ADV:
            qty = pct * adv
            for name, schedule in make_schedules(qty, forecast, realized, adv).items():
                row = {"ticker": ticker, "date": date, "pct_adv": pct,
                       "strategy": name, "forecast_error": fc_error}
                row.update(evaluate(day, schedule, qty, sigma, cost))
                rows.append(row)
    return rows


def run_backtest(tickers=config.TICKERS, loader=build_dataset) -> pd.DataFrame:
    """Run the backtest for all tickers and return one DataFrame of results.

    `loader` returns the bucketed data for a ticker. It can be replaced by a
    function that returns synthetic data, for testing without real data.
    """
    cost = CostModel(config.HALF_SPREAD_BPS, config.IMPACT_Y)
    rows = []
    for ticker in tickers:
        print(f"[backtest] {ticker} ...")
        rows += backtest_ticker(ticker, loader(ticker), cost)
    return pd.DataFrame(rows)
