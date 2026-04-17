"""
Order sizing helpers for PT.4.4 preview and delta generation.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, Iterable, Tuple

import pandas as pd

from runtime_paths import get_price_lake_dir


REPO_ROOT = Path(__file__).parent.parent
TINY_CAPITAL_CONFIG = REPO_ROOT / "data" / "pt4_prep" / "tiny_capital_config.json"


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_tiny_capital_config() -> dict:
    if not TINY_CAPITAL_CONFIG.exists():
        return {
            "mode": "standard",
            "enabled": False,
            "limits": {},
        }

    with TINY_CAPITAL_CONFIG.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_reference_prices(symbols: Iterable[str]) -> Dict[str, float]:
    price_dir = get_price_lake_dir()
    reference_prices: Dict[str, float] = {}

    for symbol in sorted(set(symbols)):
        price_file = price_dir / f"{symbol}.parquet"
        if not price_file.exists():
            continue

        price_df = pd.read_parquet(price_file, columns=["timestamp", "close"])
        price_df = price_df.dropna(subset=["close"]).sort_values("timestamp")
        if price_df.empty:
            continue

        reference_prices[symbol] = float(price_df.iloc[-1]["close"])

    return reference_prices


def classify_order_reason(current_shares: int, target_shares: int) -> str:
    if current_shares > 0 and target_shares == 0:
        return "hold_buffer_out"
    if current_shares == 0 and target_shares > 0:
        return "added"
    return "rebalance"


def build_delta_orders(
    *,
    target_weights: pd.DataFrame,
    current_holdings: Dict[str, float],
    current_cash: float,
    account_equity: float,
    tiny_config: dict | None = None,
) -> Tuple[list[dict], dict, dict]:
    if target_weights is None or len(target_weights) == 0:
        return [], {}, {}

    tiny_config = tiny_config or load_tiny_capital_config()
    limits = tiny_config.get("limits", {})
    tiny_enabled = bool(tiny_config.get("enabled", False))

    current_holdings = {
        str(symbol): int(_safe_float(qty))
        for symbol, qty in (current_holdings or {}).items()
        if abs(_safe_float(qty)) > 1e-9
    }

    target_weights = target_weights.copy()
    ranked_symbols = list(target_weights["stock_code"])
    all_symbols = list(dict.fromkeys(ranked_symbols + sorted(current_holdings)))

    reference_prices = load_reference_prices(all_symbols)
    missing_prices = [symbol for symbol in all_symbols if symbol not in reference_prices]
    if missing_prices:
        raise ValueError(f"Missing reference prices for: {', '.join(missing_prices[:10])}")

    account_equity = _safe_float(account_equity)
    current_cash = _safe_float(current_cash)

    max_total_capital = _safe_float(limits.get("max_total_capital"), account_equity) if tiny_enabled else account_equity
    max_daily_order_notional = _safe_float(limits.get("max_daily_order_notional"), current_cash) if tiny_enabled else current_cash
    max_single_stock_notional = _safe_float(limits.get("max_single_stock_notional"), float("inf")) if tiny_enabled else float("inf")
    max_single_stock_weight = _safe_float(limits.get("max_single_stock_weight"), 1.0) if tiny_enabled else 1.0

    effective_capital_base = min(account_equity, max_total_capital) if tiny_enabled else account_equity
    effective_buy_budget = min(current_cash, max_daily_order_notional, effective_capital_base) if tiny_enabled else min(current_cash, account_equity)

    target_weight_map = dict(zip(target_weights["stock_code"], target_weights["target_weight"]))

    target_share_map: Dict[str, int] = {}
    for symbol in ranked_symbols:
        weight = _safe_float(target_weight_map.get(symbol))
        reference_price = reference_prices[symbol]

        target_notional = effective_capital_base * weight
        if tiny_enabled:
            target_notional = min(target_notional, max_single_stock_notional)
            target_notional = min(target_notional, effective_capital_base * max_single_stock_weight)

        target_share_map[symbol] = int(math.floor(target_notional / reference_price))

    retained = []
    added = []
    dropped = []
    orders: list[dict] = []
    remaining_buy_budget = effective_buy_budget
    used_buy_budget = 0.0

    for symbol in ranked_symbols:
        target_shares = int(target_share_map.get(symbol, 0))
        current_shares = int(current_holdings.get(symbol, 0))
        reference_price = reference_prices[symbol]

        if current_shares > 0 and target_shares > 0:
            retained.append(symbol)
        if target_shares > 0 and current_shares == 0:
            added.append(symbol)

        desired_buy_shares = max(0, target_shares - current_shares)
        if desired_buy_shares <= 0:
            continue

        max_affordable_shares = int(math.floor(remaining_buy_budget / reference_price)) if reference_price > 0 else 0
        executable_buy_shares = min(desired_buy_shares, max_affordable_shares)
        if executable_buy_shares <= 0:
            continue

        buy_notional = executable_buy_shares * reference_price
        remaining_buy_budget -= buy_notional
        used_buy_budget += buy_notional

        orders.append(
            {
                "symbol": symbol,
                "side": "BUY",
                "quantity": executable_buy_shares,
                "qty": executable_buy_shares,
                "target_shares": target_shares,
                "current_shares": current_shares,
                "delta_shares": executable_buy_shares,
                "target_weight": float(target_weight_map.get(symbol, 0.0)),
                "reference_price": reference_price,
                "notional": buy_notional,
                "reason": classify_order_reason(current_shares, target_shares),
                "order_type": "MARKET",
                "tif": "DAY",
            }
        )

    extra_symbols = sorted(set(current_holdings) - set(ranked_symbols))
    for symbol in extra_symbols:
        current_shares = int(current_holdings.get(symbol, 0))
        reference_price = reference_prices[symbol]
        dropped.append(symbol)

        orders.append(
            {
                "symbol": symbol,
                "side": "SELL",
                "quantity": current_shares,
                "qty": current_shares,
                "target_shares": 0,
                "current_shares": current_shares,
                "delta_shares": -current_shares,
                "target_weight": 0.0,
                "reference_price": reference_price,
                "notional": current_shares * reference_price,
                "reason": classify_order_reason(current_shares, 0),
                "order_type": "MARKET",
                "tif": "DAY",
            }
        )

    delta_summary = {
        "retained": len(retained),
        "added": len(added),
        "dropped": len(dropped),
        "total_orders": len(orders),
        "buy_notional": round(used_buy_budget, 2),
        "sell_notional": round(sum(order["notional"] for order in orders if order["side"] == "SELL"), 2),
    }

    sizing_summary = {
        "tiny_mode_enabled": tiny_enabled,
        "account_equity": round(account_equity, 2),
        "current_cash": round(current_cash, 2),
        "effective_capital_base": round(effective_capital_base, 2),
        "max_total_capital": round(max_total_capital, 2),
        "max_daily_order_notional": round(max_daily_order_notional, 2),
        "max_single_stock_notional": None if math.isinf(max_single_stock_notional) else round(max_single_stock_notional, 2),
        "buy_budget": round(effective_buy_budget, 2),
        "buy_budget_used": round(used_buy_budget, 2),
        "buy_budget_remaining": round(max(remaining_buy_budget, 0.0), 2),
        "reference_price_source": "latest_close",
    }

    return orders, delta_summary, sizing_summary
