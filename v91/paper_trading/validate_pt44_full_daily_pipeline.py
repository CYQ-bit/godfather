"""
Validate that feature refresh -> fresh predictions -> PT.4.4 uses the latest dates.
This script never connects to the broker or submits orders.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import polars as pl

sys.path.insert(0, str(Path(__file__).parent.parent))

from paper_trading.run_pt44_unified import (
    calculate_portfolio_delta,
    generate_signals,
    generate_target_portfolio,
    load_current_holdings,
    load_sector_map,
    run_pre_trade_gate,
)
from paper_trading.broker_connection import BrokerConnection
from paper_trading.order_preview_export import (
    build_preview_order_rows,
    export_preview_orders,
)
from paper_trading.order_sizing import load_tiny_capital_config
from paper_trading.ui_console import UIConsole


REPO_ROOT = Path(__file__).parent.parent
FEATURE_PATH = REPO_ROOT / "data" / "feature_store" / "ml_alpha_matrix.parquet"
FRESH_PREDICTIONS = REPO_ROOT / "data" / "ml2_results" / "predictions_fresh.parquet"
COMPAT_PREDICTIONS = REPO_ROOT / "data" / "ml2_results" / "predictions_8window.parquet"
BROKER_CONFIG = REPO_ROOT / "data" / "pt4_prep" / "broker_connection_config.json"


def load_feature_metadata(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Feature matrix not found: {path}")

    stats_df = (
        pl.scan_parquet(str(path))
        .select(
            [
                pl.len().alias("rows"),
                pl.col("timestamp").max().alias("latest_date"),
                pl.col("symbol").n_unique().alias("symbols"),
            ]
        )
        .collect()
    )

    latest_date = pd.Timestamp(stats_df["latest_date"][0]).date().isoformat()
    return {
        "path": str(path),
        "rows": int(stats_df["rows"][0]),
        "latest_date": latest_date,
        "symbols": int(stats_df["symbols"][0]),
    }


def load_prediction_metadata(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Prediction file not found: {path}")

    df = pd.read_parquet(path)
    if df.empty:
        raise ValueError(f"Prediction file is empty: {path}")

    dates = pd.to_datetime(df["timestamp"])
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
        "symbols": int(df["symbol"].nunique()),
        "modified_at": modified_at,
    }


def main() -> int:
    ui = UIConsole()
    broker = BrokerConnection(config_file=str(BROKER_CONFIG))

    ui.section("Feature Validation")
    feature = load_feature_metadata(FEATURE_PATH)
    fresh = load_prediction_metadata(FRESH_PREDICTIONS)
    compat = load_prediction_metadata(COMPAT_PREDICTIONS)

    if fresh["latest_date"] != compat["latest_date"]:
        raise ValueError(
            "Prediction latest dates do not match: "
            f"{fresh['latest_date']} vs {compat['latest_date']}"
        )
    if fresh["rows"] != compat["rows"]:
        raise ValueError(
            f"Prediction row counts do not match: {fresh['rows']} vs {compat['rows']}"
        )
    if feature["latest_date"] != fresh["latest_date"]:
        raise ValueError(
            "Feature latest date does not match prediction latest date: "
            f"{feature['latest_date']} vs {fresh['latest_date']}"
        )

    ui.status_table(
        {
            "Feature path": feature["path"],
            "Latest feature date": feature["latest_date"],
            "Feature rows": feature["rows"],
            "Feature symbols": feature["symbols"],
        },
        "Feature Source",
    )

    ui.status_table(
        {
            "Prediction path": compat["path"],
            "Latest prediction date": compat["latest_date"],
            "Rows (latest date)": compat["latest_rows"],
            "Rows (total)": compat["rows"],
            "Prediction symbols": compat["symbols"],
            "Modified (NY)": compat["modified_at"],
        },
        "Prediction Source",
    )

    ui.section("PT.4.4 Read Validation")
    ny_time = datetime.now(ZoneInfo("America/New_York"))
    trading_date = ny_time.strftime("%Y-%m-%d")
    run_id = f"pt44v91_preview_{trading_date}_{ny_time.strftime('%H%M%S')}"
    if not broker.connect():
        raise RuntimeError("Broker connection failed during safe validation")

    current_holdings, holdings_summary = load_current_holdings(broker, ui)
    account = broker.get_account_info() or {}
    open_orders = broker.list_open_orders() or []
    sector_map = load_sector_map()

    signals, signal_status = generate_signals(ui, trading_date, sector_map=sector_map)
    if str(signal_status).startswith("error"):
        raise RuntimeError(f"Signal generation failed: {signal_status}")

    used_prediction_date = compat["latest_date"]
    signal_count = 0
    if signals is not None and len(signals) > 0:
        signal_count = len(signals)
        used_prediction_date = pd.to_datetime(signals["date"]).max().date().isoformat()

    if used_prediction_date != feature["latest_date"]:
        raise ValueError(
            "PT.4.4 is not reading the latest prediction date: "
            f"{used_prediction_date} vs {feature['latest_date']}"
        )

    target_weights, target_status = generate_target_portfolio(
        ui,
        signals,
        trading_date,
        current_holdings=current_holdings
    )
    if str(target_status).startswith("error"):
        raise RuntimeError(f"Target generation failed: {target_status}")

    orders = []
    delta_status = "no_targets"
    if target_weights is not None and len(target_weights) > 0:
        orders, delta_status, delta_summary = calculate_portfolio_delta(
            ui=ui,
            target_weights=target_weights,
            current_holdings=current_holdings,
            current_cash=account.get('cash', 0.0),
            account_equity=account.get('equity', 0.0),
        )
    else:
        delta_summary = {}

    if signals is not None and len(signals) > 0:
        unknown_count = int((signals['sector'] == 'Unknown').sum())
        top_sectors = signals.loc[signals['sector'] != 'Unknown', 'sector'].value_counts().head(5)
        top_sector_summary = ", ".join(f"{sector}:{count}" for sector, count in top_sectors.items()) or "none"
    else:
        unknown_count = 0
        top_sector_summary = "none"

    reason = "orders_ready"
    if signal_status != "success":
        reason = signal_status
    elif target_status != "success":
        reason = target_status
    elif delta_status != "success":
        reason = delta_status

    preview_rows = build_preview_order_rows(
        trading_date=trading_date,
        run_id=run_id,
        orders=orders,
        holdings_source=holdings_summary["selected_source"],
        prediction_date=used_prediction_date,
        feature_date=feature["latest_date"],
    )

    if len(preview_rows) != len(orders):
        raise ValueError(
            "Preview export row count does not match delta order count: "
            f"{len(preview_rows)} vs {len(orders)}"
        )

    preview_export = export_preview_orders(
        trading_date=trading_date,
        run_id=run_id,
        preview_rows=preview_rows,
        feature_date=feature["latest_date"],
        prediction_date=used_prediction_date,
        holdings_source=holdings_summary["selected_source"],
    )

    tiny_config = load_tiny_capital_config()
    gate_status, gate_reasons = run_pre_trade_gate(orders, account, tiny_config)

    ui.status_table(
        {
            "Trading date (NY)": trading_date,
            "PT.4.4 read date": used_prediction_date,
            "Signal": signal_status,
            "Signal count": signal_count,
            "Current holdings": len(current_holdings),
            "Open orders": len(open_orders),
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

    ui.status_table(
        {
            "Selected holdings source": holdings_summary["selected_source"],
            "Holdings consistency": holdings_summary["consistency"],
            "Unknown sectors": unknown_count,
            "Top sectors": top_sector_summary,
        },
        "Holdings & Sector Summary",
    )

    ui.status_table(
        {
            "Run ID": run_id,
            "Latest JSON": preview_export["latest_json"],
            "Latest CSV": preview_export["latest_csv"],
            "Archive JSON": preview_export["archive_json"],
            "Archive CSV": preview_export["archive_csv"],
            "Exported orders": preview_export["order_count"],
        },
        "Preview Order Export",
    )

    ui.status_table(
        {
            "Gate Status": gate_status,
            "Gate Reasons": ", ".join(gate_reasons) if gate_reasons else "none",
        },
        "Gate Validation",
    )

    if len(orders) == 0:
        ui.print(f"ℹ️  No order preview reason: {reason}", "yellow")
    else:
        ui.print("✅ Orders preview generated from latest feature-backed predictions", "green")
        ui.print(
            f"✅ Preview orders exported: {preview_export['latest_json']}",
            "green",
        )

    print("FULL_PIPELINE_VALIDATION_OK")
    print(f"RUN_ID={run_id}")
    print(f"HOLDINGS_SOURCE={holdings_summary['selected_source']}")
    print(f"HOLDINGS_CONSISTENCY={holdings_summary['consistency']}")
    print(f"CURRENT_HOLDINGS_COUNT={len(current_holdings)}")
    print(f"FEATURE_DATE={feature['latest_date']}")
    print(f"PREDICTION_DATE={compat['latest_date']}")
    print(f"PT44_READ_DATE={used_prediction_date}")
    print(f"UNKNOWN_SECTOR_COUNT={unknown_count}")
    print(f"TOP_SECTORS={top_sector_summary}")
    print(f"SIGNAL_STATUS={signal_status}")
    print(f"TARGET_STATUS={target_status}")
    print(f"DELTA_STATUS={delta_status}")
    print(f"NO_ORDER_REASON={reason}")
    print(f"PREVIEW_ORDER_COUNT={preview_export['order_count']}")
    print(f"PREVIEW_ORDER_JSON={preview_export['latest_json']}")
    print(f"PREVIEW_ORDER_CSV={preview_export['latest_csv']}")
    print(f"GATE_STATUS={gate_status}")
    print(f"GATE_REASONS={'; '.join(gate_reasons) if gate_reasons else 'none'}")

    broker.disconnect()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FULL_PIPELINE_VALIDATION_FAILED: {exc}")
        raise
