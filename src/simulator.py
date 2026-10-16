"""
Fill simulation. Each child order fills at the bucket's market VWAP plus a cost:

    participation = your shares / market shares in the bucket
    impact_bps    = impact_y * sigma_bps * sqrt(participation)    (square-root law)
    cost_bps      = half_spread_bps + impact_bps
    fill_px       = ref_px * (1 + side * cost_bps / 10_000)

ref_px is the bucket VWAP. side is +1 for a buy and -1 for a sell, so the cost
always works against the trader. Impact per share grows with the square root
of participation, so a bucket's total cost (shares x impact) grows like
shares^1.5: concentrating shares in a thin bucket is disproportionately expensive.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class CostModel:
    """Cost parameters: half spread in bps and the square-root impact coefficient."""
    half_spread_bps: float = 1.0
    impact_y: float = 0.5


def simulate_execution(day: pd.DataFrame, schedule: np.ndarray, side: int,
                       sigma_bps: float, cost: CostModel) -> pd.DataFrame:
    """Fill a schedule against one day of bucketed market data.

    Args:
        day: the day's buckets, sorted by bucket, with columns bucket, vwap, volume.
        schedule: shares to trade in each bucket.
        side: +1 for a buy, -1 for a sell.
        sigma_bps: daily volatility estimate in bps.
        cost: spread and impact parameters.

    Returns:
        One row per bucket with columns bucket, qty, ref_px, mkt_volume,
        participation, impact_bps, cost_bps, fill_px.

    Raises:
        ValueError: if the schedule length does not match the day, or if it
            trades in a bucket where the market traded nothing.
    """
    qty = np.asarray(schedule, dtype=float)
    if len(qty) != len(day):
        raise ValueError(f"schedule has {len(qty)} buckets but the day has {len(day)}")

    ref_px = day["vwap"].to_numpy()
    mkt_volume = day["volume"].to_numpy()
    if ((qty > 0) & (mkt_volume == 0)).any():
        raise ValueError("schedule trades in a bucket with zero market volume")

    participation = np.divide(qty, mkt_volume, out=np.zeros_like(qty), where=mkt_volume > 0)
    impact_bps = cost.impact_y * sigma_bps * np.sqrt(participation)
    cost_bps = np.where(qty > 0, cost.half_spread_bps + impact_bps, 0.0)   # no trade, no cost
    fill_px = ref_px * (1 + side * cost_bps / 10_000)

    return pd.DataFrame({
        "bucket": day["bucket"].to_numpy(),
        "qty": qty,
        "ref_px": ref_px,
        "mkt_volume": mkt_volume,
        "participation": participation,
        "impact_bps": impact_bps,
        "cost_bps": cost_bps,
        "fill_px": fill_px,
    })
