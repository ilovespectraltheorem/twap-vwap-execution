"""
Sensitivity check: do the conclusions survive different assumptions?

For each setting below, re-run the whole backtest with that one value changed,
then measure VWAP vs TWAP again. Run from the project folder:

    python sensitivity.py
"""
from pathlib import Path

import pandas as pd

import config
from src.backtest import run_backtest
from src.metrics import paired_bootstrap_ci

SETTINGS = {
    "IMPACT_Y": [0.25, 0.5, 1.0],      # how strong market impact is
    "LOOKBACK_DAYS": [5, 10, 20],      # how many past days feed the forecast, ADV and sigma
}
SIZES = [0.05, 0.20]                   # order sizes (fraction of ADV) to report

rows = []
for param, values in SETTINGS.items():
    original = getattr(config, param)              # remember the normal value
    for value in values:
        setattr(config, param, value)              # same as writing config.IMPACT_Y = value
        print(f"\n=== {param} = {value} ===")
        results = run_backtest(config.TICKERS)

        for pct in SIZES:
            sub = results[results["pct_adv"] == pct]
            imp_diff, imp_lo, imp_hi = paired_bootstrap_ci(sub, "impact_bps", "VWAP", "TWAP")
            is_diff, is_lo, is_hi = paired_bootstrap_ci(sub, "is_bps", "VWAP", "TWAP")
            mean_impact = sub.groupby("strategy")["impact_bps"].mean()
            rows.append({
                "setting": param,
                "value": value,
                "pct_adv": pct,
                "ticker_days": sub[sub["strategy"] == "VWAP"].shape[0],
                "TWAP_impact": mean_impact["TWAP"],
                "VWAP_impact": mean_impact["VWAP"],
                "impact_diff": imp_diff,
                "impact_CI": f"[{imp_lo:+.2f}, {imp_hi:+.2f}]",
                "IS_diff": is_diff,
                "IS_CI": f"[{is_lo:+.2f}, {is_hi:+.2f}]",
                "forecast_error": sub["forecast_error"].mean(),
            })
    setattr(config, param, original)               # put the normal value back

table = pd.DataFrame(rows).round(3)
print("\n=== Sensitivity of VWAP - TWAP (bps, negative = VWAP cheaper) ===")
print(table.to_string(index=False))

Path(config.RESULTS_DIR).mkdir(exist_ok=True)
table.to_csv(Path(config.RESULTS_DIR) / "sensitivity.csv", index=False)
print(f"\nSaved to {config.RESULTS_DIR}/sensitivity.csv")
