"""
Broker -> local state sync helpers for Godfather V9.0 PT.4.4
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from paper_trading.broker_recon_adapter import BrokerReconAdapter


REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / "data/paper_trading/state"
STATE_FILE = STATE_DIR / "pt42_complete_state.json"
FILLS_LEDGER_FILE = STATE_DIR / "fills_ledger.json"
BROKER_STATE_FILE = STATE_DIR / "broker_state.json"
LAST_SYNC_REPORT_FILE = STATE_DIR / "last_broker_local_sync.json"


def _read_json(path: Path, default):
    if not path.exists():
        return deepcopy(default)

    with open(path, "r") as handle:
        return json.load(handle)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with open(temp_path, "w") as handle:
        json.dump(payload, handle, indent=2)
    temp_path.replace(path)


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _positions_to_dict(positions: List[Dict]) -> Dict[str, float]:
    normalized = {}
    for position in positions or []:
        symbol = str(position.get("symbol", "")).strip()
        qty = _safe_float(position.get("qty"))
        if symbol and abs(qty) > 1e-9:
            normalized[symbol] = qty
    return dict(sorted(normalized.items()))


def _position_costs(positions: List[Dict]) -> Dict[str, float]:
    costs = {}
    for position in positions or []:
        symbol = str(position.get("symbol", "")).strip()
        if symbol:
            costs[symbol] = _safe_float(position.get("avg_entry_price"))
    return dict(sorted(costs.items()))


def _normalize_existing_fill(fill: Dict) -> Dict:
    return {
        "broker_order_id": fill.get("broker_order_id") or fill.get("order_id"),
        "symbol": fill.get("symbol"),
        "side": str(fill.get("side", "")).lower(),
        "qty": _safe_float(fill.get("qty")),
        "price": _safe_float(fill.get("price")),
        "timestamp": fill.get("timestamp") or fill.get("transaction_time"),
        "synced_at": fill.get("synced_at"),
    }


def _normalize_broker_fill(fill: Dict, synced_at: str) -> Dict:
    return {
        "broker_order_id": fill.get("order_id"),
        "symbol": fill.get("symbol"),
        "side": str(fill.get("side", "")).lower(),
        "qty": _safe_float(fill.get("qty")),
        "price": _safe_float(fill.get("price")),
        "timestamp": fill.get("transaction_time"),
        "synced_at": synced_at,
    }


def _fill_key(fill: Dict) -> Tuple[str, str, str, str, str, str]:
    return (
        str(fill.get("broker_order_id") or ""),
        str(fill.get("symbol") or ""),
        str(fill.get("side") or ""),
        f"{_safe_float(fill.get('qty')):.8f}",
        f"{_safe_float(fill.get('price')):.8f}",
        str(fill.get("timestamp") or ""),
    )


def _merge_fills(existing_fills: List[Dict], broker_fills: List[Dict], synced_at: str) -> Tuple[List[Dict], int]:
    merged = {}

    for fill in existing_fills or []:
        normalized = _normalize_existing_fill(fill)
        key = _fill_key(normalized)
        merged[key] = normalized

    before_count = len(merged)

    for fill in broker_fills or []:
        normalized = _normalize_broker_fill(fill, synced_at=synced_at)
        key = _fill_key(normalized)
        merged[key] = normalized

    merged_list = sorted(
        merged.values(),
        key=lambda item: (str(item.get("timestamp") or ""), str(item.get("broker_order_id") or "")),
    )
    return merged_list, len(merged) - before_count


def load_combined_local_state() -> Dict:
    state = _read_json(STATE_FILE, {})
    fills_from_ledger = _read_json(FILLS_LEDGER_FILE, [])

    state.setdefault("positions", {})
    state.setdefault("cash", 0.0)
    state.setdefault("equity", 0.0)

    if fills_from_ledger:
        state["fills"] = fills_from_ledger
    else:
        state.setdefault("fills", [])

    return state


def fetch_broker_snapshot(broker) -> Dict:
    account = broker.get_account_info()
    if not account:
        raise RuntimeError("Failed to fetch broker account info")

    positions = broker.get_positions() or []
    fills = broker.get_fills() or []
    open_orders = broker.list_open_orders() or []

    return {
        "account": account,
        "positions": positions,
        "fills": fills,
        "open_orders": open_orders,
    }


def build_sync_report(before_state: Dict, snapshot: Dict, merged_fills: List[Dict], fills_added: int, reason: str) -> Dict:
    broker_positions = _positions_to_dict(snapshot["positions"])
    account = snapshot["account"]

    return {
        "timestamp": datetime.now().isoformat(),
        "reason": reason,
        "before": {
            "cash": _safe_float(before_state.get("cash")),
            "equity": _safe_float(before_state.get("equity")),
            "positions_count": len(before_state.get("positions", {})),
            "fills_count": len(before_state.get("fills", [])),
            "positions_sample": dict(list(sorted(before_state.get("positions", {}).items()))[:8]),
        },
        "broker": {
            "cash": _safe_float(account.get("cash")),
            "equity": _safe_float(account.get("equity")),
            "positions_count": len(broker_positions),
            "fills_count": len(snapshot["fills"]),
            "open_orders_count": len(snapshot["open_orders"]),
            "positions_sample": dict(list(broker_positions.items())[:8]),
        },
        "after": {
            "cash": _safe_float(account.get("cash")),
            "equity": _safe_float(account.get("equity")),
            "positions_count": len(broker_positions),
            "fills_count": len(merged_fills),
            "positions_sample": dict(list(broker_positions.items())[:8]),
        },
        "fills_added": fills_added,
    }


def sync_local_state_from_broker(broker, reason: str = "manual_repair") -> Dict:
    snapshot = fetch_broker_snapshot(broker)
    before_state = load_combined_local_state()
    synced_at = datetime.now().isoformat()

    merged_fills, fills_added = _merge_fills(before_state.get("fills", []), snapshot["fills"], synced_at=synced_at)
    broker_positions = _positions_to_dict(snapshot["positions"])
    broker_position_costs = _position_costs(snapshot["positions"])
    account = snapshot["account"]

    latest_fill = None
    if merged_fills:
        latest_fill = max(merged_fills, key=lambda item: str(item.get("timestamp") or ""))

    complete_state = {
        "timestamp": synced_at,
        "sync_reason": reason,
        "sync_source": "broker",
        "order": {
            "broker_order_id": latest_fill.get("broker_order_id"),
            "symbol": latest_fill.get("symbol"),
            "side": latest_fill.get("side"),
            "qty": str(latest_fill.get("qty")),
            "status": "filled",
            "filled_qty": str(latest_fill.get("qty")),
            "filled_avg_price": str(latest_fill.get("price")),
        } if latest_fill else before_state.get("order", {}),
        "positions": broker_positions,
        "cash": _safe_float(account.get("cash")),
        "equity": _safe_float(account.get("equity")),
        "fills": merged_fills,
    }

    broker_state = {
        "date": datetime.now().date().isoformat(),
        "timestamp": synced_at,
        "cash": _safe_float(account.get("cash")),
        "equity": _safe_float(account.get("equity")),
        "portfolio_value": _safe_float(account.get("portfolio_value")),
        "positions": broker_positions,
        "position_costs": broker_position_costs,
        "open_orders": snapshot["open_orders"],
        "fills_count": len(snapshot["fills"]),
        "realized_pnl": _safe_float(before_state.get("realized_pnl")),
        "total_transaction_costs": _safe_float(before_state.get("total_transaction_costs")),
    }

    report = build_sync_report(
        before_state=before_state,
        snapshot=snapshot,
        merged_fills=merged_fills,
        fills_added=fills_added,
        reason=reason,
    )

    _write_json(FILLS_LEDGER_FILE, merged_fills)
    _write_json(STATE_FILE, complete_state)
    _write_json(BROKER_STATE_FILE, broker_state)
    _write_json(LAST_SYNC_REPORT_FILE, report)

    return report


def run_broker_local_recon(broker) -> Dict:
    local_state = load_combined_local_state()
    recon_adapter = BrokerReconAdapter(broker)
    return recon_adapter.run_full_recon(
        local_orders=[],
        local_positions=local_state.get("positions", {}),
        local_cash=_safe_float(local_state.get("cash")),
        local_fills=local_state.get("fills", []),
    )


def critical_recon_ok(recon_report: Dict) -> bool:
    checks = {
        check.get("check"): check.get("status")
        for check in recon_report.get("checks", [])
    }
    return (
        checks.get("positions_recon") == "MATCHED"
        and checks.get("cash_recon") == "MATCHED"
        and checks.get("fills_recon") == "MATCHED"
        and checks.get("orders_recon") != "ERROR"
    )
