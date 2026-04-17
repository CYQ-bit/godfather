"""
Preview order export helpers for Godfather V9.0 PT.4.4 validation flows.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

import pandas as pd


REPO_ROOT = Path(__file__).parent.parent
PREVIEW_ROOT = REPO_ROOT / "data" / "paper_trading"
PREVIEW_ARCHIVE_DIR = PREVIEW_ROOT / "order_previews"
LATEST_PREVIEW_JSON = PREVIEW_ROOT / "latest_order_preview.json"
LATEST_PREVIEW_CSV = PREVIEW_ROOT / "latest_order_preview.csv"
PREVIEW_COLUMNS = [
    "trading_date",
    "run_id",
    "symbol",
    "side",
    "qty",
    "target_shares",
    "current_shares",
    "delta_shares",
    "target_weight",
    "reference_price",
    "notional",
    "reason",
    "holdings_source",
    "prediction_date",
    "feature_date",
    "regime_state",
    "confidence_bucket",
    "confidence_score",
    "weight_multiplier",
    "expected_alpha",
    "commission_bps",
    "spread_bps",
    "overnight_gap_bps",
    "delay_buffer_bps",
    "impact_bps",
    "estimated_cost_bps",
    "expected_alpha_net",
    "threshold_used_bps",
    "turnover_penalty",
    "filtered_reason",
    "main_score",
    "overlay_score",
    "overlay_confidence",
    "overlay_filter_flag",
]

def build_preview_order_rows(
    *,
    trading_date: str,
    run_id: str,
    orders: Iterable[dict],
    holdings_source: str,
    prediction_date: str,
    feature_date: str,
    regime_state: str = "unknown",
    confidence_data: dict = None,
    dual_model_data: dict = None,
) -> List[dict]:
    preview_rows: List[dict] = []
    confidence_data = confidence_data or {}
    dual_model_data = dual_model_data or {}
    for order in orders:
        symbol = str(order["symbol"])
        conf_info = confidence_data.get(symbol, {})
        dual_info = dual_model_data.get(symbol, {})
        preview_rows.append(
            {
                "trading_date": trading_date,
                "run_id": run_id,
                "symbol": symbol,
                "side": str(order["side"]),
                "qty": int(order["quantity"]),
                "target_shares": int(order.get("target_shares", 0)),
                "current_shares": int(order.get("current_shares", 0)),
                "delta_shares": int(order.get("delta_shares", 0)),
                "target_weight": float(order.get("target_weight", 0.0)),
                "reference_price": float(order.get("reference_price", 0.0)),
                "notional": float(order.get("notional", 0.0)),
                "reason": str(order.get("reason", "rebalance")),
                "holdings_source": holdings_source,
                "prediction_date": prediction_date,
                "feature_date": feature_date,
                "regime_state": regime_state,
                "confidence_bucket": conf_info.get("confidence_bucket", "unknown"),
                "confidence_score": float(conf_info.get("confidence_score", 0.0)),
                "weight_multiplier": float(conf_info.get("weight_multiplier", 1.0)),
                "main_score": float(dual_info.get("main_score", 0.0)),
                "overlay_score": float(dual_info.get("overlay_score", 0.0)),
                "overlay_confidence": str(dual_info.get("overlay_confidence", "unknown")),
                "overlay_filter_flag": str(dual_info.get("overlay_filter_flag", "ok")),
            }
        )

    return preview_rows


def export_preview_orders(
    *,
    trading_date: str,
    run_id: str,
    preview_rows: Iterable[dict],
    feature_date: str,
    prediction_date: str,
    holdings_source: str,
) -> dict:
    PREVIEW_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    rows = list(preview_rows)
    frame = pd.DataFrame(rows, columns=PREVIEW_COLUMNS)

    archive_json = PREVIEW_ARCHIVE_DIR / f"{trading_date}_{run_id}.json"
    archive_csv = PREVIEW_ARCHIVE_DIR / f"{trading_date}_{run_id}.csv"

    payload = {
        "trading_date": trading_date,
        "run_id": run_id,
        "feature_date": feature_date,
        "prediction_date": prediction_date,
        "holdings_source": holdings_source,
        "order_count": len(rows),
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "orders": rows,
    }

    with archive_json.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    frame.to_csv(archive_csv, index=False)

    with LATEST_PREVIEW_JSON.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    frame.to_csv(LATEST_PREVIEW_CSV, index=False)

    return {
        "latest_json": str(LATEST_PREVIEW_JSON),
        "latest_csv": str(LATEST_PREVIEW_CSV),
        "archive_json": str(archive_json),
        "archive_csv": str(archive_csv),
        "order_count": len(rows),
    }
