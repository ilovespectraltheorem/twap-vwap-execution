"""
Project settings. Every experiment is run by changing a value here and
re-running `python main.py`; no other file needs editing.
"""

# ---------------------------------------------------------------- data
TICKERS = ["SPY", "AAPL", "MSFT", "JPM", "XOM"]   # liquid names from different sectors

# Yahoo Finance intraday limits: "1m" bars go back about 29 days, "5m" and "15m"
# about 58 days, and each request may span at most about 7 days.
# 5-minute bars give about 40 trading days of history.
INTERVAL = "5m"
HISTORY_DAYS = {"1m": 28, "5m": 57, "15m": 57}[INTERVAL]

TZ = "America/New_York"
MARKET_OPEN = "09:30"
MARKET_CLOSE = "16:00"
OPEN_MINUTE = int(MARKET_OPEN[:2]) * 60 + int(MARKET_OPEN[3:])      # 570 minutes after midnight
CLOSE_MINUTE = int(MARKET_CLOSE[:2]) * 60 + int(MARKET_CLOSE[3:])   # 960
SESSION_MINUTES = CLOSE_MINUTE - OPEN_MINUTE                        # 390

# ---------------------------------------------------------------- buckets
BUCKET_MINUTES = 15                               # 390 / 15 = 26 buckets per day
N_BUCKETS = SESSION_MINUTES // BUCKET_MINUTES
# A full day has 390 / 78 / 26 bars. Allow a couple of missing bars; drop early closes.
MIN_BARS_PER_DAY = {"1m": 380, "5m": 76, "15m": 25}[INTERVAL]

# ---------------------------------------------------------------- strategy
LOOKBACK_DAYS = 10                                # past days used for the volume forecast, ADV and volatility
ORDER_SIZES_PCT_ADV = [0.01, 0.05, 0.10, 0.20]    # parent order size as a fraction of ADV
SIDE = +1                                         # +1 = buy, -1 = sell
MAX_PARTICIPATION = 0.10                          # VWAP_capped: at most 10% of forecast bucket volume

# ---------------------------------------------------------------- cost model
HALF_SPREAD_BPS = 1.0     # paid on every share (large caps: roughly 0.5-2 bps)
IMPACT_Y = 0.5            # square-root impact coefficient (literature: roughly 0.5-1)

# ---------------------------------------------------------------- output
RESULTS_DIR = "results"
