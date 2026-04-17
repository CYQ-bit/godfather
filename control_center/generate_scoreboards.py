#!/usr/bin/env python3
"""Godfather daily and 5-day scoreboard generator."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))


ROOT = Path("Path(__file__).resolve().parent.parent")
ROOT_V90 = Path("Path(__file__).resolve().parent.parent")
ROOT_V91 = Path("str(Path(__file__).resolve().parent.parent / 'v91')")
OUTPUT_ROOT = ROOT / "data" / "scoreboards"
DAILY_DIR = OUTPUT_ROOT / "daily"
FINAL_DIR = OUTPUT_ROOT / "final"

LOCAL_TZ = ZoneInfo("Asia/Shanghai")
NY_TZ = ZoneInfo("America/New_York")

DESKTOP_DATA_LAKE_MARKERS = (
    "${GODFATHER_DATA_LAKE_ROOT:-./data/data_lake}/prices",
    "${GODFATHER_DATA_LAKE_ROOT:-./data/data_lake}/universe/sp500_universe.csv",
)

INSTANCE_CONFIGS = {
    "V9.0": {
        "version": "V9.0",
        "root": ROOT_V90,
        "preview_json": ROOT_V90 / "data" / "paper_trading" / "latest_order_preview.json",
        "daily_run_log": ROOT_V90 / "data" / "paper_trading" / "state" / "daily_run_log.json",
        "broker_state": ROOT_V90 / "data" / "paper_trading" / "state" / "broker_state.json",
        "fills_ledger": ROOT_V90 / "data" / "paper_trading" / "state" / "fills_ledger.json",
        "state_complete": ROOT_V90 / "data" / "paper_trading" / "state" / "pt42_complete_state.json",
        "sync_validation": ROOT_V90 / "data" / "paper_trading" / "state" / "last_post_trade_sync_validation.json",
        "dashboard_summary": ROOT_V90 / "data" / "paper_trading" / "dashboard" / "dashboard_summary.json",
        "logs_dir": ROOT_V90 / "logs",
    },
    "V9.1": {
        "version": "V9.1",
        "root": ROOT_V91,
        "preview_json": ROOT_V91 / "data" / "paper_trading" / "latest_order_preview.json",
        "daily_run_log": ROOT_V91 / "data" / "paper_trading" / "state" / "daily_run_log.json",
        "broker_state": ROOT_V91 / "data" / "paper_trading" / "state" / "broker_state.json",
        "fills_ledger": ROOT_V91 / "data" / "paper_trading" / "state" / "fills_ledger.json",
        "state_complete": ROOT_V91 / "data" / "paper_trading" / "state" / "pt42_complete_state.json",
        "sync_validation": ROOT_V91 / "data" / "paper_trading" / "state" / "last_post_trade_sync_validation.json",
        "dashboard_summary": ROOT_V91 / "data" / "paper_trading" / "dashboard" / "dashboard_summary.json",
        "logs_dir": ROOT_V91 / "logs",
    },
}


@dataclass
class LogSummary:
    path: Path
    text: str
    kv: dict[str, str]
    started_at_local: datetime | None
    started_at_ny: datetime | None
    manual_force: bool
    status: str
    feature_status: str
    prediction_status: str
    validation_status: str
    pt44_status: str
    final_status: str
    failure_reason: str
    window_status: str
    window_reason: str
    trading_date: str
    run_id: str
    preview_run_id: str
    eligible_main: bool
    has_validation: bool


def version_slug(version_key: str) -> str:
    return {"V9.0": "v90", "V9.1": "v91"}.get(version_key, version_key.lower().replace(".", ""))


def now_ny() -> datetime:
    return datetime.now(tz=NY_TZ)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Godfather daily and 5-day scoreboards.")
    parser.add_argument("--date", help="Trading date in YYYY-MM-DD (NY date). Defaults to current NY date.")
    parser.add_argument("--force", action="store_true", help="Bypass after-close window guard.")
    parser.add_argument("--simulate-final", action="store_true", help="Pad missing prior days with latest available daily scores to validate 5-day aggregation.")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(errors="ignore")
    except Exception:
        return ""


def parse_any_timestamp(value: Any, fallback_tz: ZoneInfo = LOCAL_TZ) -> datetime | None:
    if value in {None, "", "n/a"}:
        return None
    raw = str(value).strip()
    try:
        normalized = raw.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=fallback_tz)
        return parsed
    except Exception:
        pass
    for fmt in ("%Y%m%d_%H%M%S", "%Y-%m-%d %H:%M:%S", "%b %d %H:%M:%S %Y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=fallback_tz)
        except Exception:
            continue
    return None


def format_ts(value: Any, tz: ZoneInfo = LOCAL_TZ) -> str:
    parsed = parse_any_timestamp(value)
    if parsed is None:
        return "n/a"
    return parsed.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S %Z")


def parse_key_values(text: str) -> dict[str, str]:
    results: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.isupper():
            results[key] = value.strip()
    return results


def timestamp_from_log_path(path: Path) -> datetime | None:
    match = re.search(r"_(\d{8}_\d{6})\.log$", path.name)
    if not match:
        return None
    return parse_any_timestamp(match.group(1), fallback_tz=LOCAL_TZ)


def find_stage_value(text: str, label: str) -> str | None:
    match = re.search(rf"^{re.escape(label)}:\s*(.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def detect_window_semantics(text: str) -> tuple[str | None, str | None]:
    normalized = text.lower()
    markers = [
        ("out_of_window", "Missed PT.4.4 launch window (after 10:30 ET)", "missed pt.4.4 launch window"),
        ("out_of_window", "Skip: Too early for full pre-market scheduler", "too early for full pre-market scheduler"),
        ("out_of_window", "Skip: Outside pre-market scheduler window", "outside pre-market scheduler window"),
        ("out_of_window", "Skip: Before pre-market scheduler window", "before pre-market scheduler window"),
    ]
    for status, label, needle in markers:
        if needle in normalized:
            return status, label
    if "outside window" in normalized or "before window" in normalized or "too early" in normalized:
        return "out_of_window", "Outside configured trading window"
    return None, None


def summarize_log(path: Path) -> LogSummary:
    text = read_text(path)
    kv = parse_key_values(text)
    started_local = timestamp_from_log_path(path)
    started_ny = started_local.astimezone(NY_TZ) if started_local else None
    manual_force = "MANUAL_FORCE_MODE=1" in text
    feature_status = find_stage_value(text, "Feature refresh") or "n/a"
    prediction_status = find_stage_value(text, "Prediction") or "n/a"
    validation_status = find_stage_value(text, "Validation") or "n/a"
    pt44_status = find_stage_value(text, "PT.4.4 unified") or "n/a"
    final_status = find_stage_value(text, "Final status") or "n/a"
    failure_lines = [line.strip() for line in text.splitlines() if line.strip().startswith("❌")]
    failure_reason = failure_lines[-1] if failure_lines else "n/a"
    window_status, window_reason = detect_window_semantics(text)
    run_id = kv.get("RUN_ID", "none")
    preview_run_id = run_id if run_id.startswith("pt44_preview_") or run_id.startswith("pt44v91_preview_") else "none"
    trading_date = kv.get("PT44_READ_DATE") or kv.get("FEATURE_DATE") or kv.get("PREDICTION_DATE")
    if not trading_date and started_ny:
        trading_date = started_ny.date().isoformat()
    trading_date = trading_date or "n/a"

    if window_status and not manual_force:
        status = window_status
    elif final_status != "n/a":
        status = final_status
    elif any(value == "failed" for value in (feature_status, prediction_status, validation_status, pt44_status)):
        status = "failed"
    elif pt44_status != "n/a":
        status = pt44_status
    elif failure_reason != "n/a":
        status = "failed"
    elif text.strip():
        status = "in_progress"
    else:
        status = "none"

    eligible_main = bool(text.strip()) and not manual_force and status not in {"out_of_window", "skipped", "none", "in_progress"}

    return LogSummary(
        path=path,
        text=text,
        kv=kv,
        started_at_local=started_local,
        started_at_ny=started_ny,
        manual_force=manual_force,
        status=status,
        feature_status=feature_status,
        prediction_status=prediction_status,
        validation_status=validation_status,
        pt44_status=pt44_status,
        final_status=final_status,
        failure_reason=failure_reason if failure_reason != "n/a" else (window_reason or "n/a"),
        window_status=window_status or "eligible",
        window_reason=window_reason or "n/a",
        trading_date=trading_date,
        run_id=run_id,
        preview_run_id=preview_run_id,
        eligible_main=eligible_main,
        has_validation=("FULL_PIPELINE_VALIDATION_OK" in text or "PREVIEW_ORDER_COUNT=" in text),
    )


def recent_log_paths(logs_dir: Path) -> list[Path]:
    if not logs_dir.exists():
        return []
    paths = sorted(logs_dir.glob("pt44g_full_daily_*.log"), reverse=True)
    return [path for path in paths if path.name != "pt44g_full_daily_latest.log"]


def load_logs_for_date(logs_dir: Path, target_date: str) -> list[LogSummary]:
    results: list[LogSummary] = []
    for path in recent_log_paths(logs_dir):
        summary = summarize_log(path)
        if summary.trading_date == target_date:
            results.append(summary)
    return results


def latest_non_manual(logs: list[LogSummary]) -> LogSummary | None:
    for item in logs:
        if not item.manual_force:
            return item
    return None


def latest_manual_force(logs: list[LogSummary]) -> LogSummary | None:
    for item in logs:
        if item.manual_force:
            return item
    return None


def latest_eligible_main(logs: list[LogSummary]) -> LogSummary | None:
    for item in logs:
        if item.eligible_main:
            return item
    return None


def count_submitted_orders(logs: list[LogSummary], target_date: str) -> int:
    total = 0
    for log in logs:
        if log.trading_date != target_date:
            continue
        total += len(re.findall(r"Order submitted:", log.text))
    return total


def count_fills_for_date(fills: list[dict[str, Any]], target_date: str) -> int:
    total = 0
    for fill in fills or []:
        parsed = parse_any_timestamp(fill.get("timestamp"))
        if parsed and parsed.astimezone(NY_TZ).date().isoformat() == target_date:
            total += 1
    return total


def normalize_positions(raw_positions: dict | None) -> dict[str, float]:
    normalized: dict[str, float] = {}
    if not isinstance(raw_positions, dict):
        return normalized
    for symbol, qty in raw_positions.items():
        try:
            value = float(qty)
        except Exception:
            continue
        if abs(value) <= 1e-9:
            continue
        normalized[str(symbol)] = value
    return dict(sorted(normalized.items()))


def compute_current_recon(sync_validation: dict | None, state_complete: dict | None, broker_state: dict | None, fills_ledger: list | None) -> dict[str, str]:
    validation = (sync_validation or {}).get("current_recon", {}) if isinstance(sync_validation, dict) else {}
    if validation:
        return {
            "overall": str(validation.get("overall", "UNKNOWN")).upper(),
            "orders": str(validation.get("orders_recon", validation.get("orders", "UNKNOWN"))).upper(),
            "positions": str(validation.get("positions_recon", validation.get("positions", "UNKNOWN"))).upper(),
            "cash": str(validation.get("cash_recon", validation.get("cash", "UNKNOWN"))).upper(),
            "fills": str(validation.get("fills_recon", validation.get("fills", "UNKNOWN"))).upper(),
        }

    local_positions = normalize_positions((state_complete or {}).get("positions", {}))
    broker_positions = normalize_positions((broker_state or {}).get("positions", {}))
    positions = "MATCHED" if local_positions == broker_positions else "MISMATCHED"

    try:
        local_cash = float((state_complete or {}).get("cash", "nan"))
        broker_cash = float((broker_state or {}).get("cash", "nan"))
        cash = "MATCHED" if math.isfinite(local_cash) and math.isfinite(broker_cash) and abs(local_cash - broker_cash) <= 0.01 else "MISMATCHED"
    except Exception:
        cash = "UNKNOWN"

    local_fills = len((fills_ledger or []) or ((state_complete or {}).get("fills") or []))
    broker_fills = (broker_state or {}).get("fills_count")
    fills = "MATCHED" if isinstance(broker_fills, int) and local_fills == broker_fills else "UNKNOWN"

    parts = {positions, cash, fills}
    if parts == {"MATCHED"}:
        overall = "MATCHED"
    elif "MISMATCHED" in parts:
        overall = "MISMATCHED"
    else:
        overall = "UNKNOWN"
    return {"overall": overall, "orders": "UNKNOWN", "positions": positions, "cash": cash, "fills": fills}


def lag_days(target_date: str, source_date: str) -> int | None:
    try:
        end = date.fromisoformat(target_date)
        start = date.fromisoformat(source_date)
        return (end - start).days
    except Exception:
        return None


def preview_buy_caps_ok(preview: dict[str, Any] | None) -> tuple[bool, float, float]:
    orders = (preview or {}).get("orders", []) if isinstance(preview, dict) else []
    buy_orders = [order for order in orders if str(order.get("side", "")).upper() == "BUY"]
    total_buy = sum(float(order.get("notional", 0.0) or 0.0) for order in buy_orders)
    max_name = max((float(order.get("notional", 0.0) or 0.0) for order in buy_orders), default=0.0)
    ok = total_buy <= 1000.0 + 1e-6 and max_name <= 200.0 + 1e-6
    return ok, total_buy, max_name


def normalize_issue_signature(value: str) -> str:
    lowered = str(value or "").strip().lower()
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered


def previous_business_days(end_date: str, count: int) -> list[str]:
    current = date.fromisoformat(end_date)
    dates: list[str] = []
    while len(dates) < count:
        if current.weekday() < 5:
            dates.append(current.isoformat())
        current -= timedelta(days=1)
    return list(reversed(dates))


def load_previous_daily_score(version_key: str, target_date: str) -> dict[str, Any] | None:
    prev = date.fromisoformat(target_date) - timedelta(days=1)
    for _ in range(7):
        path = DAILY_DIR / f"daily_score_{version_slug(version_key)}_{prev.isoformat()}.json"
        payload = read_json(path)
        if payload:
            return payload
        prev -= timedelta(days=1)
    return None


def score_instance(version_key: str, cfg: dict[str, Any], target_date: str) -> dict[str, Any]:
    preview = read_json(cfg["preview_json"]) or {}
    run_log = read_json(cfg["daily_run_log"]) or {}
    broker_state = read_json(cfg["broker_state"]) or {}
    fills_ledger = read_json(cfg["fills_ledger"]) or []
    state_complete = read_json(cfg["state_complete"]) or {}
    sync_validation = read_json(cfg["sync_validation"]) or {}
    dashboard_summary = read_json(cfg["dashboard_summary"]) or {}

    logs = load_logs_for_date(cfg["logs_dir"], target_date)
    latest_invocation = latest_non_manual(logs)
    latest_main = latest_eligible_main(logs)
    latest_manual = latest_manual_force(logs)

    preview_for_date = preview if preview.get("trading_date") == target_date else {}
    preview_orders = int(preview_for_date.get("order_count", 0) or 0)
    preview_signal = "success" if preview_orders or preview_for_date.get("run_id") else "none"

    fill_count = count_fills_for_date(fills_ledger, target_date)
    submit_count = count_submitted_orders(logs, target_date)
    current_recon = compute_current_recon(sync_validation, state_complete, broker_state, fills_ledger)
    auto_repair = str(sync_validation.get("auto_repair_success", "none")) if isinstance(sync_validation, dict) else "none"
    sync_ok = str(sync_validation.get("post_trade_sync_validation", "n/a")) if isinstance(sync_validation, dict) else "n/a"
    feature_date = str(preview_for_date.get("feature_date") or (latest_main.kv.get("FEATURE_DATE") if latest_main else "n/a") or "n/a")
    prediction_date = str(preview_for_date.get("prediction_date") or (latest_main.kv.get("PREDICTION_DATE") if latest_main else "n/a") or "n/a")
    no_order_reason = "n/a"
    gate_status = "n/a"
    gate_reason = "n/a"
    chain_source = latest_main or latest_manual
    if chain_source:
        no_order_reason = chain_source.kv.get("NO_ORDER_REASON", "n/a")
        gate_status = chain_source.kv.get("GATE_STATUS", "n/a")
        gate_reason = chain_source.kv.get("GATE_REASONS", "n/a")
    elif preview_for_date:
        no_order_reason = "orders_ready" if preview_orders else "n/a"
        gate_status = "PASS" if preview_orders else "unknown"
        gate_reason = "none" if preview_orders else "n/a"

    desktop_hit = any(any(marker in log.text for marker in DESKTOP_DATA_LAKE_MARKERS) for log in logs)
    unhandled_exception = any("Traceback" in log.text or "Unhandled" in log.text for log in logs)
    drift_unrepaired = current_recon["overall"] != "MATCHED" and latest_main is not None and latest_main.status == "failed"
    post_trade_unsynced = submit_count > 0 and current_recon["overall"] != "MATCHED"

    base_issue_signature = ""
    if desktop_hit:
        base_issue_signature = "desktop_path"
    elif drift_unrepaired:
        base_issue_signature = "drift_unrepaired"
    elif post_trade_unsynced:
        base_issue_signature = "post_trade_unsynced"
    elif unhandled_exception:
        base_issue_signature = "unhandled_exception"
    elif latest_main and latest_main.status == "failed":
        base_issue_signature = normalize_issue_signature(latest_main.failure_reason)

    previous_daily = load_previous_daily_score(version_key, target_date)
    repeated_failure = False
    if previous_daily and base_issue_signature:
        prev_signature = normalize_issue_signature(previous_daily.get("root_issue_signature", ""))
        repeated_failure = prev_signature == base_issue_signature and latest_main is not None and latest_main.status == "failed"

    veto_reasons: list[str] = []
    if desktop_hit:
        veto_reasons.append("命中旧 Desktop data path")
    if drift_unrepaired:
        veto_reasons.append("drift 未修复且主运行中止")
    if post_trade_unsynced:
        veto_reasons.append("submit 后本地账本未回写且当前仍 MISMATCHED")
    if unhandled_exception:
        veto_reasons.append("未处理异常导致主链崩溃")
    if repeated_failure:
        veto_reasons.append("同一工程故障连续重复触发")

    lag_feature = lag_days(target_date, feature_date)
    lag_prediction = lag_days(target_date, prediction_date)

    schedule_score = 0
    schedule_note = "未发现有效主运行"
    if latest_main and latest_main.status == "completed":
        schedule_score = 20
        schedule_note = "有效窗口内主运行完成"
    elif latest_main and latest_main.status == "failed":
        schedule_score = 4 if current_recon["overall"] == "MATCHED" else 0
        schedule_note = "有效主运行失败，但当前状态已修复" if current_recon["overall"] == "MATCHED" else "有效主运行失败"
    elif latest_invocation and latest_invocation.status == "out_of_window":
        schedule_score = 6 if run_log.get(target_date) else 0
        schedule_note = "最近一次调用超出窗口，未覆盖有效主运行结论"

    freshness_score = 0
    freshness_note = f"feature={feature_date}, prediction={prediction_date}"
    if lag_feature == 0 and lag_prediction == 0:
        freshness_score = 15
    elif (lag_feature in {0, 1}) and (lag_prediction in {0, 1}):
        freshness_score = 10
    elif (lag_feature is not None and lag_feature <= 2) and (lag_prediction is not None and lag_prediction <= 2):
        freshness_score = 5

    signal_success = False
    target_success = False
    delta_success = False
    gate_pass = False
    for log in [latest_main, latest_manual]:
        if log:
            signal_success = signal_success or log.kv.get("SIGNAL_STATUS") == "success"
            target_success = target_success or log.kv.get("TARGET_STATUS") == "success"
            delta_success = delta_success or log.kv.get("DELTA_STATUS") == "success"
            gate_pass = gate_pass or log.kv.get("GATE_STATUS") == "PASS"
    if preview_signal == "success":
        signal_success = signal_success or True
        target_success = target_success or True
        delta_success = delta_success or True
        gate_pass = gate_pass or (gate_status == "PASS")
    pretrade_score = sum(
        [
            5 if signal_success else 0,
            5 if target_success else 0,
            5 if delta_success else 0,
            5 if gate_pass else 0,
        ]
    )
    pretrade_note = f"signal={signal_success}, target={target_success}, delta={delta_success}, gate={gate_status}"

    execution_score = 0
    if submit_count > 0:
        execution_score += 8
    if fill_count > 0:
        execution_score += 6
    if current_recon["overall"] == "MATCHED":
        execution_score += 4
    if preview_orders > 0:
        execution_score += 2
    execution_note = f"submit={submit_count}, fills={fill_count}, preview={preview_orders}, recon={current_recon['overall']}"

    ledger_score = 0
    if current_recon["overall"] == "MATCHED":
        ledger_score += 8
    if current_recon["positions"] == "MATCHED":
        ledger_score += 2
    if current_recon["cash"] == "MATCHED":
        ledger_score += 2
    if current_recon["fills"] == "MATCHED":
        ledger_score += 2
    if sync_ok == "OK":
        ledger_score += 1
    ledger_note = f"overall={current_recon['overall']}, auto_repair={auto_repair}, sync_validation={sync_ok}"

    caps_ok, total_buy_notional, max_name_notional = preview_buy_caps_ok(preview_for_date)
    risk_score = 0
    if gate_status == "PASS":
        risk_score += 3
    if caps_ok and preview_orders > 0:
        risk_score += 3
    if not desktop_hit:
        risk_score += 2
    if current_recon["overall"] == "MATCHED":
        risk_score += 2
    risk_note = f"gate={gate_status}, preview_buy={total_buy_notional:.2f}, max_name={max_name_notional:.2f}, current_recon={current_recon['overall']}"

    categories = [
        {"name": "调度与主运行", "max": 20, "score": schedule_score, "note": schedule_note},
        {"name": "数据链新鲜度", "max": 15, "score": freshness_score, "note": freshness_note},
        {"name": "交易前链路完整度", "max": 20, "score": pretrade_score, "note": pretrade_note},
        {"name": "执行推进度", "max": 20, "score": execution_score, "note": execution_note},
        {"name": "账本一致性与修复能力", "max": 15, "score": ledger_score, "note": ledger_note},
        {"name": "交易质量与风控", "max": 10, "score": risk_score, "note": risk_note},
    ]
    raw_total = sum(item["score"] for item in categories)
    veto = bool(veto_reasons)
    total = 0 if veto else raw_total

    if veto:
        conclusion = f"{version_key} 当日触发一票否决：{' / '.join(veto_reasons)}。"
    elif latest_main and latest_main.status == "completed" and current_recon["overall"] == "MATCHED":
        conclusion = f"{version_key} 当日主运行完成，当前账本 MATCHED，整体可判为稳定收盘。"
    elif latest_main and latest_main.status == "failed" and current_recon["overall"] == "MATCHED":
        conclusion = f"{version_key} 当日主运行失败，但后续已恢复到 MATCHED，需继续观察主运行稳定性。"
    else:
        conclusion = f"{version_key} 当日无一票否决，但仍存在工程噪声，需继续跟踪。"

    run_entry = run_log.get(target_date, {}) if isinstance(run_log, dict) else {}
    metrics = {
        "date": target_date,
        "version": version_key,
        "total_score": total,
        "raw_total_score": raw_total,
        "veto": veto,
        "veto_reasons": veto_reasons,
        "main_scheduled_run": {
            "run_id": latest_main.run_id if latest_main else "none",
            "status": latest_main.status if latest_main else "none",
            "timestamp": format_ts(latest_main.started_at_local) if latest_main else "n/a",
            "failure_reason": latest_main.failure_reason if latest_main else "n/a",
        },
        "latest_invocation": {
            "run_id": latest_invocation.run_id if latest_invocation else "none",
            "status": latest_invocation.status if latest_invocation else "none",
            "timestamp": format_ts(latest_invocation.started_at_local) if latest_invocation else "n/a",
            "reason": latest_invocation.window_reason if latest_invocation and latest_invocation.window_status == "out_of_window" else (latest_invocation.failure_reason if latest_invocation else "n/a"),
        },
        "manual_force": {
            "status": latest_manual.status if latest_manual else "none",
            "timestamp": format_ts(latest_manual.started_at_local) if latest_manual else "n/a",
        },
        "preview_order_count": preview_orders,
        "submit_count": submit_count,
        "fill_count": fill_count,
        "recon_status": current_recon["overall"],
        "auto_repair_status": auto_repair,
        "post_trade_sync_validation": sync_ok,
        "feature_date": feature_date,
        "prediction_date": prediction_date,
        "no_order_reason": no_order_reason,
        "gate_status": gate_status,
        "gate_reason": gate_reason,
        "fills_total": len(fills_ledger or []),
        "positions_count": len(normalize_positions((broker_state or {}).get("positions", {}))),
        "open_orders": len((broker_state or {}).get("open_orders", []) or []),
        "cash": (broker_state or {}).get("cash"),
        "equity": (broker_state or {}).get("equity"),
        "no_manual_intervention": latest_manual is None,
        "root_issue_signature": base_issue_signature or "none",
        "categories": categories,
        "one_line_conclusion": conclusion,
        "dashboard_status": (dashboard_summary or {}).get("status", {}),
        "run_log_entry": run_entry,
    }
    return metrics


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def markdown_daily(payload: dict[str, Any]) -> str:
    lines = [
        f"# {payload['version']} Daily Scorecard",
        "",
        f"- 日期: `{payload['date']}`",
        f"- 总分: `{payload['total_score']}/100`",
        f"- 一票否决: `{'YES' if payload['veto'] else 'NO'}`",
        f"- Main Scheduled Run: `{payload['main_scheduled_run']['status']}`",
        f"- Preview 数量: `{payload['preview_order_count']}`",
        f"- Submit 数量: `{payload['submit_count']}`",
        f"- Fill 数量: `{payload['fill_count']}`",
        f"- Recon: `{payload['recon_status']}`",
        f"- Auto Repair: `{payload['auto_repair_status']}`",
        "",
        "| 项目 | 得分 | 说明 |",
        "| --- | ---: | --- |",
    ]
    for item in payload["categories"]:
        lines.append(f"| {item['name']} | {item['score']}/{item['max']} | {item['note']} |")
    lines.extend(
        [
            "",
            "## 关键事实",
            f"- Latest Invocation: `{payload['latest_invocation']['status']}` at `{payload['latest_invocation']['timestamp']}`",
            f"- Latest Eligible Main Run: `{payload['main_scheduled_run']['run_id']}` / `{payload['main_scheduled_run']['status']}`",
            f"- Feature / Prediction: `{payload['feature_date']} / {payload['prediction_date']}`",
            f"- Gate / No-order reason: `{payload['gate_status']} / {payload['no_order_reason']}`",
            f"- 一句话日结论: {payload['one_line_conclusion']}",
        ]
    )
    if payload["veto_reasons"]:
        lines.append(f"- 一票否决原因: {' / '.join(payload['veto_reasons'])}")
    return "\n".join(lines) + "\n"


def csv_daily_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in payload["categories"]:
        rows.append(
            {
                "date": payload["date"],
                "version": payload["version"],
                "category": item["name"],
                "score": item["score"],
                "max_score": item["max"],
                "note": item["note"],
                "total_score": payload["total_score"],
                "veto": payload["veto"],
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_daily_summary(target_date: str, v90: dict[str, Any], v91: dict[str, Any]) -> dict[str, Any]:
    if v90["veto"] and not v91["veto"]:
        winner = "V9.1"
    elif v91["veto"] and not v90["veto"]:
        winner = "V9.0"
    elif v90["total_score"] > v91["total_score"]:
        winner = "V9.0"
    elif v91["total_score"] > v90["total_score"]:
        winner = "V9.1"
    else:
        winner = "tie"
    summary = {
        "date": target_date,
        "winner": winner,
        "versions": {
            "V9.0": {
                "score": v90["total_score"],
                "main_run": v90["main_scheduled_run"]["status"],
                "preview_order_count": v90["preview_order_count"],
                "submit_count": v90["submit_count"],
                "fill_count": v90["fill_count"],
                "recon": v90["recon_status"],
                "auto_repair": v90["auto_repair_status"],
                "conclusion": v90["one_line_conclusion"],
            },
            "V9.1": {
                "score": v91["total_score"],
                "main_run": v91["main_scheduled_run"]["status"],
                "preview_order_count": v91["preview_order_count"],
                "submit_count": v91["submit_count"],
                "fill_count": v91["fill_count"],
                "recon": v91["recon_status"],
                "auto_repair": v91["auto_repair_status"],
                "conclusion": v91["one_line_conclusion"],
            },
        },
    }
    if winner == "tie":
        summary["headline"] = "两套系统当日评分持平，需继续观察连续样本。"
    else:
        summary["headline"] = f"{winner} 当日评分领先。"
    return summary


def markdown_daily_summary(summary: dict[str, Any]) -> str:
    lines = [
        f"# Daily Score Summary - {summary['date']}",
        "",
        f"- 当日领先版本: `{summary['winner']}`",
        f"- 摘要: {summary['headline']}",
        "",
        "| 版本 | 总分 | Main Run | Preview | Submit | Fill | Recon | Auto Repair |",
        "| --- | ---: | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for version in ("V9.0", "V9.1"):
        item = summary["versions"][version]
        lines.append(
            f"| {version} | {item['score']} | {item['main_run']} | {item['preview_order_count']} | {item['submit_count']} | {item['fill_count']} | {item['recon']} | {item['auto_repair']} |"
        )
    lines.append("")
    for version in ("V9.0", "V9.1"):
        lines.append(f"- {version}: {summary['versions'][version]['conclusion']}")
    return "\n".join(lines) + "\n"


def load_daily_payload(version_key: str, score_date: str) -> dict[str, Any] | None:
    return read_json(DAILY_DIR / f"daily_score_{version_slug(version_key)}_{score_date}.json")


def aggregate_five_day(target_date: str, simulate_final: bool) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    desired_dates = previous_business_days(target_date, 5)
    data: dict[str, list[dict[str, Any]]] = {"V9.0": [], "V9.1": []}
    simulated_dates: list[str] = []

    for version in ("V9.0", "V9.1"):
        available = []
        for day in desired_dates:
            payload = load_daily_payload(version, day)
            if payload:
                available.append(payload)
        if len(available) < 5 and not simulate_final:
            return None, None
        if len(available) < 5 and simulate_final:
            latest = available[-1] if available else None
            for day in desired_dates:
                payload = load_daily_payload(version, day)
                if payload:
                    data[version].append(payload)
                    continue
                if latest is None:
                    continue
                clone = json.loads(json.dumps(latest))
                clone["date"] = day
                clone["simulated_from"] = latest["date"]
                data[version].append(clone)
                simulated_dates.append(day)
        else:
            data[version] = [load_daily_payload(version, day) for day in desired_dates if load_daily_payload(version, day)]

    if any(len(items) < 5 for items in data.values()):
        return None, None

    rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "window_end": target_date,
        "dates": desired_dates,
        "simulated": bool(simulated_dates),
        "simulated_dates": sorted(set(simulated_dates)),
        "versions": {},
    }

    for version in ("V9.0", "V9.1"):
        payloads = data[version]
        total = sum(item["total_score"] for item in payloads)
        avg = round(total / len(payloads), 2)
        veto_count = sum(1 for item in payloads if item["veto"])
        matched_days = sum(1 for item in payloads if item["recon_status"] == "MATCHED")
        no_intervention_days = sum(1 for item in payloads if item.get("no_manual_intervention", False))
        execution_days = sum(1 for item in payloads if item["submit_count"] > 0)
        total_submits = sum(int(item["submit_count"]) for item in payloads)
        total_fills = sum(int(item["fill_count"]) for item in payloads)
        category_avg = {}
        for category_name in [item["name"] for item in payloads[0]["categories"]]:
            values = []
            for payload in payloads:
                for category in payload["categories"]:
                    if category["name"] == category_name:
                        values.append(category["score"])
                        break
            category_avg[category_name] = round(sum(values) / len(values), 2) if values else 0.0

        summary["versions"][version] = {
            "total_score": total,
            "average_score": avg,
            "category_average": category_avg,
            "execution_days": execution_days,
            "total_submits": total_submits,
            "total_fills": total_fills,
            "matched_days": matched_days,
            "no_manual_intervention_days": no_intervention_days,
            "veto_count": veto_count,
        }
        rows.append(
            {
                "version": version,
                "window_end": target_date,
                "total_score": total,
                "average_score": avg,
                "execution_days": execution_days,
                "total_submits": total_submits,
                "total_fills": total_fills,
                "matched_days": matched_days,
                "no_manual_intervention_days": no_intervention_days,
                "veto_count": veto_count,
            }
        )

    v90 = summary["versions"]["V9.0"]
    v91 = summary["versions"]["V9.1"]
    if v90["average_score"] > v91["average_score"]:
        winner = "V9.0"
    elif v91["average_score"] > v90["average_score"]:
        winner = "V9.1"
    else:
        winner = "tie"
    summary["winner"] = winner

    reasons: list[str] = []
    if winner != "tie":
        reasons.append(f"{winner} 五日平均分更高。")
    if v90["veto_count"] != v91["veto_count"]:
        lower = "V9.0" if v90["veto_count"] < v91["veto_count"] else "V9.1"
        reasons.append(f"{lower} 一票否决次数更少。")
    if v90["matched_days"] != v91["matched_days"]:
        better = "V9.0" if v90["matched_days"] > v91["matched_days"] else "V9.1"
        reasons.append(f"{better} broker/local MATCHED 天数更多。")
    if v90["execution_days"] != v91["execution_days"]:
        better = "V9.0" if v90["execution_days"] > v91["execution_days"] else "V9.1"
        reasons.append(f"{better} 真实执行推进天数更多。")
    if v90["no_manual_intervention_days"] != v91["no_manual_intervention_days"]:
        better = "V9.0" if v90["no_manual_intervention_days"] > v91["no_manual_intervention_days"] else "V9.1"
        reasons.append(f"{better} 无人工干预天数更多。")
    summary["core_reasons"] = reasons[:5] or ["两套系统五日表现接近，需继续扩大样本。"]
    return summary, {"rows": rows, "daily_payloads": data}


def markdown_five_day(summary: dict[str, Any]) -> str:
    lines = [
        "# 5-Day Core Scoreboard",
        "",
        f"- 统计窗口结束日: `{summary['window_end']}`",
        f"- 覆盖交易日: `{', '.join(summary['dates'])}`",
        f"- 是否模拟第 5 天: `{'YES' if summary['simulated'] else 'NO'}`",
        f"- 最终胜出版本: `{summary['winner']}`",
        "",
        "| 版本 | 总分 | 平均分 | 执行天数 | 总提交数 | 总成交数 | MATCHED 天数 | 无人工干预天数 | 一票否决次数 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for version in ("V9.0", "V9.1"):
        item = summary["versions"][version]
        lines.append(
            f"| {version} | {item['total_score']} | {item['average_score']} | {item['execution_days']} | {item['total_submits']} | {item['total_fills']} | {item['matched_days']} | {item['no_manual_intervention_days']} | {item['veto_count']} |"
        )
    lines.extend(
        [
            "",
            "## 各维度均分",
        ]
    )
    for version in ("V9.0", "V9.1"):
        lines.append(f"### {version}")
        for name, value in summary["versions"][version]["category_average"].items():
            lines.append(f"- {name}: `{value}`")
        lines.append("")
    lines.append("## 核心理由")
    for reason in summary["core_reasons"]:
        lines.append(f"- {reason}")
    if summary["simulated_dates"]:
        lines.append(f"- 模拟补齐日期: {', '.join(summary['simulated_dates'])}")
    return "\n".join(lines) + "\n"


def markdown_final_verdict(summary: dict[str, Any]) -> str:
    if summary["winner"] == "tie":
        headline = "五日核心结论：当前两套系统尚未拉开明显优势，建议继续观察。"
    else:
        headline = f"五日核心结论：{summary['winner']} 暂时胜出。"
    lines = [
        "# 5-Day Final Verdict",
        "",
        headline,
        "",
        f"- 胜出版本: `{summary['winner']}`",
        f"- 平均分: `V9.0={summary['versions']['V9.0']['average_score']}` / `V9.1={summary['versions']['V9.1']['average_score']}`",
        f"- MATCHED 天数: `V9.0={summary['versions']['V9.0']['matched_days']}` / `V9.1={summary['versions']['V9.1']['matched_days']}`",
        f"- 一票否决次数: `V9.0={summary['versions']['V9.0']['veto_count']}` / `V9.1={summary['versions']['V9.1']['veto_count']}`",
        "",
        "## 核心理由",
    ]
    for reason in summary["core_reasons"]:
        lines.append(f"- {reason}")
    return "\n".join(lines) + "\n"


def write_daily_outputs(payload: dict[str, Any]) -> None:
    version_key = version_slug(payload["version"])
    score_date = payload["date"]
    write_json(DAILY_DIR / f"daily_score_{version_key}_{score_date}.json", payload)
    write_csv(DAILY_DIR / f"daily_score_{version_key}_{score_date}.csv", csv_daily_rows(payload))
    (DAILY_DIR / f"daily_score_{version_key}_{score_date}.md").write_text(markdown_daily(payload))


def write_daily_summary_outputs(summary: dict[str, Any]) -> None:
    score_date = summary["date"]
    write_json(DAILY_DIR / f"daily_score_summary_{score_date}.json", summary)
    summary_rows = []
    for version in ("V9.0", "V9.1"):
        item = summary["versions"][version]
        summary_rows.append(
            {
                "date": score_date,
                "version": version,
                "score": item["score"],
                "main_run": item["main_run"],
                "preview_order_count": item["preview_order_count"],
                "submit_count": item["submit_count"],
                "fill_count": item["fill_count"],
                "recon": item["recon"],
                "auto_repair": item["auto_repair"],
                "winner": summary["winner"],
            }
        )
    write_csv(DAILY_DIR / f"daily_score_summary_{score_date}.csv", summary_rows)
    (DAILY_DIR / f"daily_score_summary_{score_date}.md").write_text(markdown_daily_summary(summary))


def write_final_outputs(summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    write_json(FINAL_DIR / "5day_core_scoreboard.json", summary)
    write_csv(FINAL_DIR / "5day_core_scoreboard.csv", rows)
    (FINAL_DIR / "5day_core_scoreboard.md").write_text(markdown_five_day(summary))
    (FINAL_DIR / "5day_final_verdict.md").write_text(markdown_final_verdict(summary))


def after_close_window() -> bool:
    current = now_ny()
    return current.time() >= time(16, 5)


def main() -> int:
    args = parse_args()
    target_date = args.date or now_ny().date().isoformat()

    if not args.force and not after_close_window():
        print(f"SKIP: not after NY close yet for {target_date}")
        return 0

    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    v90 = score_instance("V9.0", INSTANCE_CONFIGS["V9.0"], target_date)
    v91 = score_instance("V9.1", INSTANCE_CONFIGS["V9.1"], target_date)

    write_daily_outputs(v90)
    write_daily_outputs(v91)

    summary = build_daily_summary(target_date, v90, v91)
    write_daily_summary_outputs(summary)

    print(f"DAILY_SCORE_OK V9.0 {v90['total_score']} veto={v90['veto']}")
    print(f"DAILY_SCORE_OK V9.1 {v91['total_score']} veto={v91['veto']}")
    print(f"DAILY_SUMMARY_OK {summary['winner']}")

    final_summary, final_context = aggregate_five_day(target_date, simulate_final=args.simulate_final)
    if final_summary and final_context:
        write_final_outputs(final_summary, final_context["rows"])
        print(f"FIVEDAY_CORE_SCOREBOARD_OK simulated={final_summary['simulated']} winner={final_summary['winner']}")
    else:
        print("FIVEDAY_CORE_SCOREBOARD_SKIPPED insufficient_daily_scores")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
