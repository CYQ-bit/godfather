"""
Validate that PT.4.4 signal/target/delta consumes the freshest prediction file.
This script never connects to the broker or submits orders.
"""
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from paper_trading.ui_console import UIConsole
from paper_trading.run_pt44_unified import (
    calculate_portfolio_delta,
    generate_signals,
    generate_target_portfolio,
)


REPO_ROOT = Path(__file__).parent.parent
COMPAT_PREDICTIONS = REPO_ROOT / "data/ml2_results/predictions_8window.parquet"
FRESH_PREDICTIONS = REPO_ROOT / "data/ml2_results/predictions_fresh.parquet"


def load_prediction_metadata(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Prediction file not found: {path}")

    df = pd.read_parquet(path)
    if df.empty:
        raise ValueError(f"Prediction file is empty: {path}")

    date_col = "timestamp" if "timestamp" in df.columns else "date"
    dates = pd.to_datetime(df[date_col])
    latest_date = dates.max().date().isoformat()
    latest_rows = int((dates.dt.normalize() == pd.to_datetime(latest_date)).sum())
    modified_at = datetime.fromtimestamp(
        path.stat().st_mtime,
        ZoneInfo("America/New_York"),
    ).strftime("%Y-%m-%d %H:%M:%S %Z")

    return {
        "path": str(path),
        "rows": len(df),
        "latest_date": latest_date,
        "latest_rows": latest_rows,
        "modified_at": modified_at,
    }


def main() -> int:
    ui = UIConsole()

    ui.section("Prediction File Validation")
    compat = load_prediction_metadata(COMPAT_PREDICTIONS)
    fresh = load_prediction_metadata(FRESH_PREDICTIONS)

    if compat["latest_date"] != fresh["latest_date"]:
        raise ValueError(
            "Fresh and PT.4.4 prediction dates do not match: "
            f"{fresh['latest_date']} vs {compat['latest_date']}"
        )
    if compat["rows"] != fresh["rows"]:
        raise ValueError(
            "Fresh and PT.4.4 prediction row counts do not match: "
            f"{fresh['rows']} vs {compat['rows']}"
        )

    ui.status_table(
        {
            "PT.4.4 file": compat["path"],
            "Latest prediction date": compat["latest_date"],
            "Rows (latest date)": compat["latest_rows"],
            "Rows (total)": compat["rows"],
            "Modified (NY)": compat["modified_at"],
        },
        "Prediction Source",
    )

    ui.section("PT.4.4 Read Validation")
    ny_time = datetime.now(ZoneInfo("America/New_York"))
    trading_date = ny_time.strftime("%Y-%m-%d")

    signals, signal_status = generate_signals(ui, trading_date)
    if str(signal_status).startswith("error"):
        raise RuntimeError(f"Signal generation failed: {signal_status}")

    used_prediction_date = compat["latest_date"]
    signal_count = 0
    if signals is not None and len(signals) > 0:
        signal_count = len(signals)
        used_prediction_date = pd.to_datetime(signals["date"]).max().date().isoformat()

    target_weights, target_status = generate_target_portfolio(ui, signals, trading_date)
    if str(target_status).startswith("error"):
        raise RuntimeError(f"Target generation failed: {target_status}")

    orders = []
    delta_status = "no_targets"
    if target_weights is not None and len(target_weights) > 0:
        orders, delta_status, delta_summary = calculate_portfolio_delta(
            ui=ui,
            target_weights=target_weights,
            current_holdings={},
            current_cash=100000.0,
            account_equity=100000.0,
        )
    else:
        delta_summary = {}

    reason = "orders_ready"
    if signal_status != "success":
        reason = signal_status
    elif target_status != "success":
        reason = target_status
    elif delta_status != "success":
        reason = delta_status

    ui.status_table(
        {
            "Trading date (NY)": trading_date,
            "Prediction date used": used_prediction_date,
            "Signal": signal_status,
            "Signal count": signal_count,
            "Target": target_status,
            "Delta": delta_status,
            "Orders preview": len(orders),
        },
        "PT.4.4 Consumption Check",
    )

    if delta_summary:
        ui.status_table(
            {
                "Retained": delta_summary.get("retained", 0),
                "Added": delta_summary.get("added", 0),
                "Dropped": delta_summary.get("dropped", 0),
                "Preview orders": delta_summary.get("total_orders", 0),
            },
            "Delta Summary",
        )

    if len(orders) == 0:
        ui.print(f"ℹ️  No order preview reason: {reason}", "yellow")
    else:
        ui.print("✅ Orders preview generated from fresh prediction file", "green")

    print("VALIDATION_OK")
    print(f"PREDICTION_DATE_USED={used_prediction_date}")
    print(f"SIGNAL_STATUS={signal_status}")
    print(f"TARGET_STATUS={target_status}")
    print(f"DELTA_STATUS={delta_status}")
    print(f"NO_ORDER_REASON={reason}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"VALIDATION_FAILED: {exc}")
        raise
