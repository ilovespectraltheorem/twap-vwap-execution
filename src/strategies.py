"""
Execution schedules. A schedule is an array with one entry per bucket: the
number of shares to trade in that bucket.

    TWAP          equal shares in every bucket; ignores volume
    VWAP          shares proportional to the forecast volume curve
    VWAP_oracle   shares proportional to the realized curve; impossible live,
                  used to measure what forecast error costs
    VWAP_capped   VWAP with a participation limit in each bucket
"""
import numpy as np


def twap_schedule(total_qty: float, n_buckets: int) -> np.ndarray:
    """Split the order into `n_buckets` equal slices."""
    return np.full(n_buckets, total_qty / n_buckets)


def vwap_schedule(total_qty: float, profile: np.ndarray) -> np.ndarray:
    """Split the order in proportion to a volume profile (non-negative, summing to 1)."""
    total = np.sum(profile)
    if np.any(profile < 0) or not np.isclose(total, 1.0):
        raise ValueError(f"volume profile must be non-negative and sum to 1, got sum {total:.6f}")
    return total_qty * profile


def cap_participation(schedule: np.ndarray, expected_volume: np.ndarray,
                      max_pov: float) -> np.ndarray:
    """Limit each bucket to `max_pov` of its expected volume, carrying the excess forward.

    Shares that cannot be traded in a bucket are added to the next one. Shares
    still left after the last bucket stay unfilled, so the result can sum to
    less than the original order.
    """
    capped = np.zeros(len(schedule))
    carry = 0.0
    for i in range(len(schedule)):
        want = schedule[i] + carry                  # this bucket's shares plus leftovers
        capped[i] = min(want, max_pov * expected_volume[i])
        carry = want - capped[i]                    # leftovers move to the next bucket
    return capped
