from __future__ import annotations

import json
import os
import re
import subprocess
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Godfather Control Center",
    page_icon="GF",
    layout="wide",
)

# ── Path resolution ───────────────────────────────────────────────────────────
# Set GODFATHER_ROOT env var to point at your V9.0 installation directory.
# Defaults to the parent of this file's directory (repo root).
ROOT_V90 = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))
ROOT_V91 = Path(os.environ.get("GODFATHER_V91_ROOT", str(ROOT_V90 / "v91")))

# ── Demo mode ─────────────────────────────────────────────────────────────────
# Set GODFATHER_DEMO=1 to run the dashboard with sample data (no broker needed).
DEMO_MODE = os.environ.get("GODFATHER_DEMO", "0") == "1"
LOCAL_TZ = ZoneInfo("Asia/Shanghai")

INSTANCES = {
    "V9.0": {
        "label": "Godfather V9.0",
        "root": ROOT_V90,
        "launchd_label": "com.cyq.godfather.pt44",
        "daily_log": ROOT_V90 / "logs" / "pt44g_full_daily_latest.log",
        "launchd_out": ROOT_V90 / "logs" / "launchd_pt44.out.log",
        "launchd_err": ROOT_V90 / "logs" / "launchd_pt44.err.log",
        "feature_file": ROOT_V90 / "data" / "feature_store" / "ml_alpha_matrix.parquet",
        "prediction_file": ROOT_V90 / "data" / "ml2_results" / "predictions_8window.parquet",
        "preview_json": ROOT_V90 / "data" / "paper_trading" / "latest_order_preview.json",
        "preview_csv": ROOT_V90 / "data" / "paper_trading" / "latest_order_preview.csv",
        "daily_run_log": ROOT_V90 / "data" / "paper_trading" / "state" / "daily_run_log.json",
        "state_complete": ROOT_V90 / "data" / "paper_trading" / "state" / "pt42_complete_state.json",
        "broker_state": ROOT_V90 / "data" / "paper_trading" / "state" / "broker_state.json",
        "fills_ledger": ROOT_V90 / "data" / "paper_trading" / "state" / "fills_ledger.json",
        "last_sync_report": ROOT_V90 / "data" / "paper_trading" / "state" / "last_broker_local_sync.json",
        "sync_validation": ROOT_V90 / "data" / "paper_trading" / "state" / "last_post_trade_sync_validation.json",
        "dashboard_summary": ROOT_V90 / "data" / "paper_trading" / "dashboard" / "dashboard_summary.json",
        "broker_config": ROOT_V90 / "data" / "pt4_prep" / "broker_connection_config.json",
        "env_file": ROOT_V90 / ".env.godfather",
    },
    "V9.1": {
        "label": "Godfather V9.1 Sandbox",
        "root": ROOT_V91,
        "launchd_label": "com.cyq.godfather.v91",
        "daily_log": ROOT_V91 / "logs" / "pt44g_full_daily_latest.log",
        "launchd_out": ROOT_V91 / "logs" / "launchd_v91.out.log",
        "launchd_err": ROOT_V91 / "logs" / "launchd_v91.err.log",
        "feature_file": ROOT_V91 / "data" / "feature_store" / "ml_alpha_matrix.parquet",
        "prediction_file": ROOT_V91 / "data" / "ml2_results" / "predictions_8window.parquet",
        "preview_json": ROOT_V91 / "data" / "paper_trading" / "latest_order_preview.json",
        "preview_csv": ROOT_V91 / "data" / "paper_trading" / "latest_order_preview.csv",
        "daily_run_log": ROOT_V91 / "data" / "paper_trading" / "state" / "daily_run_log.json",
        "state_complete": ROOT_V91 / "data" / "paper_trading" / "state" / "pt42_complete_state.json",
        "broker_state": ROOT_V91 / "data" / "paper_trading" / "state" / "broker_state.json",
        "fills_ledger": ROOT_V91 / "data" / "paper_trading" / "state" / "fills_ledger.json",
        "last_sync_report": ROOT_V91 / "data" / "paper_trading" / "state" / "last_broker_local_sync.json",
        "sync_validation": ROOT_V91 / "data" / "paper_trading" / "state" / "last_post_trade_sync_validation.json",
        "dashboard_summary": ROOT_V91 / "data" / "paper_trading" / "dashboard" / "dashboard_summary.json",
        "broker_config": ROOT_V91 / "data" / "pt4_prep" / "broker_connection_config.json",
        "env_file": ROOT_V91 / ".env.godfather_v91",
    },
}

STATUS_COLOR = {
    "good": "#198754",
    "warn": "#f59f00",
    "bad": "#d6336c",
    "neutral": "#495057",
}


def now_ny() -> datetime:
    return datetime.now(ZoneInfo("America/New_York"))


def mask_value(value: str | None, keep: int = 4) -> str:
    if not value:
        return "n/a"
    value = str(value)
    if len(value) <= keep * 2:
        return value[:2] + "***"
    return f"{value[:keep]}***{value[-keep:]}"


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def parse_key_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^([A-Z0-9_]+)=(.*)$", line.strip())
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values


def parse_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except Exception:
        return None


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(errors="ignore")
    except Exception:
        return ""


def file_mtime(path: Path) -> str:
    if not path.exists():
        return "n/a"
    return datetime.fromtimestamp(path.stat().st_mtime, ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")


def business_lag_days(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        start = pd.Timestamp(date_str).normalize()
        end = pd.Timestamp(now_ny().date())
        if end < start:
            return 0
        return max(len(pd.bdate_range(start, end)) - 1, 0)
    except Exception:
        return None


def stale_badge(date_str: str | None) -> tuple[str, str]:
    lag = business_lag_days(date_str)
    if lag is None:
        return "unknown", "neutral"
    if lag <= 0:
        return "fresh", "good"
    if lag == 1:
        return "warn", "warn"
    return f"stale ({lag}d)", "bad"


def market_status() -> tuple[str, str]:
    current = now_ny()
    if current.weekday() >= 5:
        return "Weekend", "neutral"
    if current.time() < datetime.strptime("09:30", "%H:%M").time():
        return "Before Open", "warn"
    if current.time() >= datetime.strptime("16:00", "%H:%M").time():
        return "After Close", "neutral"
    return "Market Open", "good"


def status_chip(label: str, value: str, tone: str) -> str:
    color = STATUS_COLOR.get(tone, STATUS_COLOR["neutral"])
    return (
        f"<div style='padding:8px 10px;border-radius:10px;border:1px solid {color};"
        f"background:{color}12;margin-bottom:8px;'>"
        f"<div style='font-size:12px;color:#666;'>{label}</div>"
        f"<div style='font-size:15px;font-weight:700;color:{color};'>{value}</div>"
        f"</div>"
    )


def is_empty_display_value(value: Any) -> bool:
    return value in {None, "", "n/a", "none"}


def humanize_status(value: Any) -> str:
    raw = str(value)
    lowered = raw.lower()
    mapping = {
        "idle/standby": "待机中",
        "out_of_window": "已跳过（超出交易窗口）",
        "active/running": "正在运行",
        "historical_failed_recovered": "历史主运行失败（当前已恢复）",
        "real_failed_current": "当前运行失败",
        "success": "成功",
        "completed": "已完成",
        "skipped": "已跳过",
        "current_recon_matched": "当前账本已对齐",
        "matched": "已对齐",
        "auto_repair_success": "自动修复成功",
        "post_trade_sync_validation_ok": "回写验证通过",
        "pass": "通过",
        "connected": "已连接",
        "configured": "已配置",
        "filled": "已成交",
        "entered": "已提交",
        "ack": "已确认",
        "ready": "就绪",
        "orders_ready": "预览已就绪",
        "manual_force_validation_completed": "手动验证已完成",
        "exported": "已导出",
        "observed": "已观察到",
        "blocked": "已阻止",
        "unknown": "未知",
        "not_reached": "未触达",
        "market_closed_skip": "已跳过（市场未开）",
        "idempotent_skip": "已跳过（当日已运行）",
        "in_progress": "进行中",
        "none": "暂无",
        "unavailable": "不可用",
        "not loaded": "未加载",
        "not_loaded": "未加载",
        "mismatched": "未对齐",
        "failed": "失败",
        "error": "错误",
        "warn": "警告",
        "waiting": "等待中",
        "pending": "等待确认",
    }
    return mapping.get(lowered, raw)


def humanize_market_status(value: str) -> str:
    return {
        "Weekend": "周末休市",
        "Before Open": "开盘前",
        "After Close": "收盘后",
        "Market Open": "交易中",
    }.get(value, value)


def display_text(value: Any, *, field: str = "generic", context: dict[str, Any] | None = None) -> str:
    context = context or {}
    if field == "status":
        return humanize_status(value)

    if field == "run_id":
        if is_empty_display_value(value):
            if context.get("failed_before_run_id"):
                return "未生成（失败发生在分配运行 ID 之前）"
            return "未生成"
        return str(value)

    if field == "pt44_status":
        if is_empty_display_value(value):
            return "未生成"
        return humanize_status(value)

    if field == "failure_reason":
        return "无" if is_empty_display_value(value) else str(value)

    if field in {"log_path", "preview_log_path", "manual_force_log", "fill_timestamp", "order_id", "source"}:
        return "暂无" if is_empty_display_value(value) else str(value)

    if field in {"feature_status", "prediction_status", "validation_status"}:
        return "未生成" if is_empty_display_value(value) else humanize_status(value)

    if field in {"historical_fill", "latest_fill", "holdings_text"}:
        return "暂无" if is_empty_display_value(value) else str(value)

    if field == "holdings_source":
        mapping = {"broker": "券商持仓", "local": "本地状态", "empty": "空仓"}
        if is_empty_display_value(value):
            return "暂无"
        return mapping.get(str(value), str(value))

    if field in {"no_order_reason", "gate_reason"}:
        if is_empty_display_value(value):
            return "无"
        mapping = {"orders_ready": "预览已就绪", "none": "无"}
        return mapping.get(str(value), str(value))

    if field == "timestamp":
        return "暂无" if is_empty_display_value(value) else str(value)

    if field == "market":
        return humanize_market_status(str(value))

    if field == "source":
        if is_empty_display_value(value):
            return "暂无"
        mapping = {
            "validation + sync state": "验证结果 + 同步状态",
            "sync state": "同步状态",
            "local snapshots": "本地快照",
            "fills_ledger": "成交账本",
            "pt42_complete_state": "本地状态",
            "none": "暂无",
        }
        return mapping.get(str(value), str(value))

    if field == "open_orders":
        return "暂无" if is_empty_display_value(value) else str(value)

    if is_empty_display_value(value):
        return "未生成"
    return str(value)


def launchd_snapshot(label: str) -> dict[str, str]:
    try:
        result = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
            capture_output=True,
            text=True,
            check=False,
        )
        text = result.stdout
    except Exception:
        return {"status": "unavailable", "tone": "bad", "raw_state": "unavailable"}

    if "could not find service" in text.lower() or result.returncode != 0:
        return {"status": "not loaded", "tone": "bad", "raw_state": "not_loaded"}

    state_match = re.search(r"state = ([^\n]+)", text)
    state = state_match.group(1).strip() if state_match else "loaded"
    active_count_match = re.search(r"active count = (\d+)", text)
    active_count = parse_int(active_count_match.group(1) if active_count_match else None) or 0
    runs_match = re.search(r"runs = (\d+)", text)
    runs = parse_int(runs_match.group(1) if runs_match else None) or 0
    exit_match = re.search(r"last exit code = ([^\n]+)", text)
    last_exit = exit_match.group(1).strip() if exit_match else "unknown"

    if state == "running" or active_count > 0:
        status = "active/running"
        tone = "good"
    else:
        status = "idle/standby"
        tone = "neutral"

    return {
        "status": status,
        "tone": tone,
        "raw_state": state,
        "active_count": str(active_count),
        "runs": str(runs),
        "last_exit": last_exit,
    }


def recent_log_paths(cfg: dict[str, Any], limit: int = 12) -> list[Path]:
    log_dir = cfg["root"] / "logs"
    if not log_dir.exists():
        return []

    # Prioritize latest.log symlink (points to most recent successful run)
    latest_log = log_dir / "pt44g_full_daily_latest.log"
    results = []
    if latest_log.exists():
        results.append(latest_log)

    candidates: list[Path] = []
    for pattern in ("pt44g_full_daily_*.log", "pt44e_daily_*.log"):
        candidates.extend(log_dir.glob(pattern))

    deduped: dict[str, Path] = {}
    for path in sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True):
        deduped.setdefault(str(path.resolve(strict=False)), path)

    # Add remaining logs after latest.log
    for path in deduped.values():
        if path not in results:
            results.append(path)

    return results[:limit]


def build_log_sources(
    cfg: dict[str, Any],
    daily_log_text: str,
    launchd_out_text: str,
    launchd_err_text: str,
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_source(name: str, path: Path, text: str | None = None) -> None:
        key = str(path.resolve(strict=False))
        if key in seen:
            return
        seen.add(key)
        payload = text if text is not None else read_text(path)
        sources.append(
            {
                "name": name,
                "path": path,
                "text": payload,
                "kv": parse_key_values(payload),
            }
        )

    add_source("Full Daily Latest", cfg["daily_log"], daily_log_text)
    add_source("Launchd STDOUT", cfg["launchd_out"], launchd_out_text)
    add_source("Launchd STDERR", cfg["launchd_err"], launchd_err_text)

    for path in recent_log_paths(cfg):
        add_source(path.name, path)

    return sources


def first_kv_value(sources: list[dict[str, Any]], *keys: str) -> str | None:
    for source in sources:
        for key in keys:
            value = source["kv"].get(key)
            if value not in {None, ""}:
                return value
    return None


def preview_implies_pipeline_success(preview_payload: dict[str, Any]) -> bool:
    return bool(preview_payload.get("run_id")) and "orders" in preview_payload


def preview_export_epoch(preview_payload: dict[str, Any]) -> float | None:
    exported_at = preview_payload.get("exported_at")
    if not exported_at:
        return None
    try:
        return datetime.fromisoformat(str(exported_at).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def infer_no_order_reason(sources: list[dict[str, Any]], preview_payload: dict[str, Any]) -> str:
    value = first_kv_value(sources, "NO_ORDER_REASON")
    if value:
        return value
    if preview_payload.get("order_count", 0):
        return "orders_ready"
    for source in sources:
        match = re.search(r"No order preview reason:\s*(.+)", source["text"])
        if match:
            return match.group(1).strip()
        if "Market not open - skipping" in source["text"]:
            return "market_closed"
    return "n/a"


def infer_gate_status(sources: list[dict[str, Any]], preview_payload: dict[str, Any], no_order_reason: str) -> str:
    value = first_kv_value(sources, "GATE_STATUS")
    if value:
        return value
    blocked_epochs: list[float] = []
    for source in sources:
        if "Gate BLOCKED" in source["text"]:
            try:
                blocked_epochs.append(source["path"].stat().st_mtime)
            except Exception:
                blocked_epochs.append(0.0)
    preview_epoch = preview_export_epoch(preview_payload)
    if preview_payload.get("order_count", 0) and no_order_reason == "orders_ready":
        if not blocked_epochs:
            return "PASS"
        if preview_epoch is not None and preview_epoch >= max(blocked_epochs):
            return "PASS"
    for source in sources:
        if "Gate BLOCKED" in source["text"]:
            return "BLOCK"
        if re.search(r"Gate Status[:=]\s*PASS", source["text"], flags=re.IGNORECASE):
            return "PASS"
    return "unknown"


def infer_gate_reason(sources: list[dict[str, Any]], gate_status: str, no_order_reason: str) -> str:
    value = first_kv_value(sources, "GATE_REASONS")
    if value:
        return value
    if str(gate_status).upper() == "PASS":
        return "none"
    for source in sources:
        match = re.search(r"Gate BLOCKED:\s*(.+)", source["text"])
        if match:
            return match.group(1).strip()
    if no_order_reason != "n/a":
        return no_order_reason
    return "n/a"


def infer_submit_status(
    sources: list[dict[str, Any]],
    gate_status: str,
    no_order_reason: str,
) -> tuple[str, str]:
    for source in sources:
        text = source["text"]
        if "Submitting " in text:
            return "entered", "good"
    if str(gate_status).upper() == "PASS" and no_order_reason == "orders_ready":
        return "ready", "warn"
    for source in sources:
        text = source["text"]
        if "Gate BLOCKED" in text:
            return "blocked", "bad"
        if "Market not open - skipping" in text:
            return "skipped", "warn"
    if str(gate_status).upper() == "BLOCK":
        return "blocked", "bad"
    if no_order_reason not in {"n/a", "none", "unknown"}:
        return "skipped", "warn"
    return "unknown", "neutral"


def infer_ack_status(sources: list[dict[str, Any]], submit_status: str) -> tuple[str, str]:
    for source in sources:
        text = source["text"]
        if "Broker order ID:" in text or "Order submitted:" in text:
            return "ack", "good"
    if submit_status == "entered":
        return "pending", "warn"
    if submit_status in {"ready", "blocked", "skipped"}:
        return "not_reached", "neutral"
    return "unknown", "neutral"


def tail_lines(path: Path, n: int) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", errors="ignore") as handle:
        return list(deque(handle, maxlen=n))


def latest_run_entry(run_log: dict | None) -> dict | None:
    if not isinstance(run_log, dict) or not run_log:
        return None
    items = sorted(
        run_log.items(),
        key=lambda item: item[1].get("timestamp", item[0]),
    )
    return items[-1][1] if items else None


def is_preview_run_id(run_id: str | None) -> bool:
    value = str(run_id or "")
    return value.startswith("pt44_preview_") or value.startswith("pt44v91_preview_")


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


def format_timestamp(value: Any) -> str:
    parsed = parse_any_timestamp(value)
    if parsed is None:
        return "n/a"
    return parsed.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")


def timestamp_from_log_path(path: Path) -> datetime | None:
    match = re.search(r"_(\d{8}_\d{6})\.log$", path.name)
    if not match:
        return None
    return parse_any_timestamp(match.group(1))


def find_stage_value(text: str, label: str) -> str | None:
    match = re.search(rf"^{re.escape(label)}:\s*(.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def detect_window_semantics(text: str) -> tuple[str | None, str | None]:
    normalized = text.lower()
    markers = [
        ("Missed PT.4.4 launch window (after 10:30 ET)", "missed pt.4.4 launch window"),
        ("Skip: Too early for full pre-market scheduler", "too early for full pre-market scheduler"),
        ("Skip: Outside pre-market scheduler window", "outside pre-market scheduler window"),
        ("Skip: Before pre-market scheduler window", "before pre-market scheduler window"),
    ]
    for label, needle in markers:
        if needle in normalized:
            return "out_of_window", label
    if "outside window" in normalized or "before window" in normalized or "too early" in normalized:
        return "out_of_window", "Outside configured trading window"
    return None, None


def summarize_full_daily_log(path: Path) -> dict[str, Any]:
    text = read_text(path)
    kv = parse_key_values(text)
    started_at = timestamp_from_log_path(path) or parse_any_timestamp(file_mtime(path))
    manual_force = "MANUAL_FORCE_MODE=1" in text
    feature_status = find_stage_value(text, "Feature refresh")
    prediction_status = find_stage_value(text, "Prediction")
    validation_status = find_stage_value(text, "Validation")
    pt44_status = find_stage_value(text, "PT.4.4 unified")
    final_status = find_stage_value(text, "Final status")
    # Prefer Final Summary table run_id (real run) over first RUN_ID= kv (may be preview)
    # Final Summary uses ║ (double vertical), preview table uses │ (single vertical)
    import re as _re
    _final_run_match = _re.search(r"║\s*Run\s+ID\s*║\s*(pt44[\w-]+)\s*║", text)
    run_id = (_final_run_match.group(1) if _final_run_match else None) or kv.get("RUN_ID")
    preview_run_id = run_id if is_preview_run_id(run_id) else None
    failure_lines = [line.strip() for line in text.splitlines() if line.strip().startswith("❌")]
    failure_reason = failure_lines[-1] if failure_lines else None
    window_status, window_reason = detect_window_semantics(text)

    if window_status and not manual_force:
        overall_status = window_status
    elif final_status:
        overall_status = final_status
    elif any(status == "failed" for status in (feature_status, prediction_status, validation_status, pt44_status)):
        overall_status = "failed"
    elif pt44_status:
        overall_status = pt44_status
    elif failure_reason:
        overall_status = "failed"
    elif text.strip():
        overall_status = "in_progress"
    else:
        overall_status = "none"

    # A run is eligible as main if:
    # 1. Not empty
    # 2. Not manual_force UNLESS it completed PT.4.4 execution (has run_id and pt44_status in success states)
    # 3. Not out_of_window/skipped/none/in_progress
    manual_force_but_completed = manual_force and run_id and pt44_status in {"success", "manual_force_validation_completed"}
    eligible_main = (
        bool(text.strip())
        and (not manual_force or manual_force_but_completed)
        and overall_status not in {"out_of_window", "skipped", "none", "in_progress"}
    )

    return {
        "path": path,
        "text": text,
        "kv": kv,
        "started_at": started_at,
        "started_display": format_timestamp(started_at),
        "manual_force": manual_force,
        "has_validation": "FULL_PIPELINE_VALIDATION_OK" in text or "PREVIEW_ORDER_COUNT=" in text,
        "run_id": run_id,
        "preview_run_id": preview_run_id,
        "feature_status": feature_status or "n/a",
        "prediction_status": prediction_status or "n/a",
        "validation_status": validation_status or "n/a",
        "pt44_status": pt44_status or "n/a",
        "final_status": final_status or "n/a",
        "status": overall_status,
        "failure_reason": failure_reason or window_reason or "n/a",
        "window_status": window_status or "eligible",
        "window_reason": window_reason or "n/a",
        "eligible_main": eligible_main,
        "trading_date": kv.get("PT44_READ_DATE") or kv.get("FEATURE_DATE") or kv.get("PREDICTION_DATE") or "n/a",
        "no_order_reason": kv.get("NO_ORDER_REASON", "n/a"),
        "gate_status": kv.get("GATE_STATUS", "n/a"),
        "gate_reasons": kv.get("GATE_REASONS", "n/a"),
    }


def latest_log_summary(
    cfg: dict[str, Any],
    *,
    manual_force: bool | None = None,
    has_validation: bool | None = None,
    eligible_main: bool | None = None,
) -> dict[str, Any] | None:
    for path in recent_log_paths(cfg, limit=40):
        summary = summarize_full_daily_log(path)
        if manual_force is not None and summary["manual_force"] != manual_force:
            continue
        if has_validation is not None and summary["has_validation"] != has_validation:
            continue
        if eligible_main is not None and summary["eligible_main"] != eligible_main:
            continue
        return summary
    return None


def preview_log_summary(cfg: dict[str, Any], preview_payload: dict[str, Any]) -> dict[str, Any] | None:
    preview_run_id = preview_payload.get("run_id")
    logs = [summarize_full_daily_log(path) for path in recent_log_paths(cfg, limit=40)]
    if preview_run_id:
        for summary in logs:
            if summary["preview_run_id"] == preview_run_id or preview_run_id in summary["text"]:
                return summary
    for summary in logs:
        if summary["has_validation"]:
            return summary
    return None


def current_main_run_id(latest_entry: dict | None, main_log: dict[str, Any] | None) -> str:
    if main_log and main_log.get("run_id") and not is_preview_run_id(main_log.get("run_id")):
        return str(main_log.get("run_id"))
    if not latest_entry or not main_log or main_log.get("manual_force"):
        return "none"

    entry_timestamp = parse_any_timestamp(latest_entry.get("timestamp"))
    main_started = main_log.get("started_at")
    if entry_timestamp and main_started and abs((entry_timestamp - main_started).total_seconds()) <= 90 * 60:
        run_id = latest_entry.get("run_id")
        if is_preview_run_id(run_id):
            return "none"
        return run_id or "none"
    return "none"


def stage_value_from_log(log_summary: dict[str, Any] | None, key: str, reached: bool) -> str:
    if not log_summary:
        return "none"
    value = log_summary["kv"].get(key)
    if value:
        return value
    return "not_reached" if not reached else "unknown"


def parse_main_pipeline(log_summary: dict[str, Any] | None) -> dict[str, str]:
    if not log_summary:
        return {
            "signal": "none",
            "target": "none",
            "delta": "none",
            "gate": "none",
            "submit": "none",
            "ack": "none",
            "fill": "none",
            "recon": "none",
            "no_order_reason": "n/a",
            "gate_reason": "n/a",
        }

    text = log_summary["text"]
    validation_reached = "[Step 4/6]" in text or "PT.4.4 Read Validation" in text
    unified_reached = "[Step 5/6]" in text

    signal = stage_value_from_log(log_summary, "SIGNAL_STATUS", validation_reached)
    target = stage_value_from_log(log_summary, "TARGET_STATUS", validation_reached)
    delta = stage_value_from_log(log_summary, "DELTA_STATUS", validation_reached)
    gate = stage_value_from_log(log_summary, "GATE_STATUS", validation_reached)
    no_order_reason = log_summary["kv"].get("NO_ORDER_REASON", "n/a" if not validation_reached else "unknown")
    gate_reason = log_summary["kv"].get("GATE_REASONS")
    if not gate_reason:
        if gate == "PASS":
            gate_reason = "none"
        elif gate in {"none", "not_reached"}:
            gate_reason = "n/a"
        else:
            gate_reason = "unknown"

    if not unified_reached:
        submit = "not_reached"
    elif "Submitting " in text:
        submit = "entered"
    elif "Already ran today:" in text:
        submit = "idempotent_skip"
    elif "Market not open - skipping" in text:
        submit = "market_closed_skip"
    elif "Gate BLOCKED" in text or gate == "BLOCK":
        submit = "blocked"
    else:
        submit = "unknown"

    if "Broker order ID:" in text or "Order submitted:" in text:
        ack = "ack"
    elif submit == "entered":
        ack = "pending"
    elif submit in {"not_reached", "idempotent_skip", "market_closed_skip", "blocked", "unknown"}:
        ack = "not_reached"
    else:
        ack = "unknown"

    fill = "not_reached"
    fill_patterns = ("Fill received", "status: filled", "status=filled", " open order ", "cancelled")
    if any(pattern.lower() in text.lower() for pattern in fill_patterns):
        fill = "observed"

    recon = "not_reached"
    if "post_trade_recon" in text.lower() or "recon result" in text.lower():
        recon = "observed"

    return {
        "signal": signal,
        "target": target,
        "delta": delta,
        "gate": gate,
        "submit": submit,
        "ack": ack,
        "fill": fill,
        "recon": recon,
        "no_order_reason": no_order_reason,
        "gate_reason": gate_reason,
    }


def parse_preview_pipeline(preview_payload: dict[str, Any], validation_log: dict[str, Any] | None) -> dict[str, str]:
    if validation_log:
        signal = validation_log["kv"].get("SIGNAL_STATUS", "unknown")
        target = validation_log["kv"].get("TARGET_STATUS", "unknown")
        delta = validation_log["kv"].get("DELTA_STATUS", "unknown")
        gate = validation_log["kv"].get("GATE_STATUS", "unknown")
        no_order_reason = validation_log["kv"].get("NO_ORDER_REASON", "n/a")
        gate_reason = validation_log["kv"].get("GATE_REASONS", "none" if gate == "PASS" else "n/a")
    elif preview_payload.get("run_id"):
        signal = "success"
        target = "success"
        delta = "success"
        gate = "unknown"
        no_order_reason = "orders_ready" if preview_payload.get("order_count", 0) else "n/a"
        gate_reason = "n/a"
    else:
        signal = target = delta = gate = "none"
        no_order_reason = gate_reason = "n/a"

    preview_state = "none"
    if preview_payload.get("run_id"):
        preview_state = "orders_ready" if preview_payload.get("order_count", 0) else "exported"

    return {
        "signal": signal,
        "target": target,
        "delta": delta,
        "gate": gate,
        "preview_state": preview_state,
        "no_order_reason": no_order_reason,
        "gate_reason": gate_reason,
    }


def latest_fill_record(fills_ledger: list | None, state_complete: dict | None) -> dict[str, str]:
    fills = fills_ledger if isinstance(fills_ledger, list) and fills_ledger else []
    if not fills and isinstance(state_complete, dict):
        fills = state_complete.get("fills", []) or []

    if fills:
        fill = fills[-1]
        symbol = fill.get("symbol", "N/A")
        side = str(fill.get("side", "N/A")).upper()
        qty = fill.get("qty", fill.get("quantity", "N/A"))
        timestamp = format_timestamp(fill.get("timestamp"))
        order_id = fill.get("broker_order_id", "n/a")
        return {
            "summary": f"{symbol} {side} {qty}",
            "timestamp": timestamp,
            "order_id": str(order_id),
            "source": "fills_ledger" if isinstance(fills_ledger, list) and fills_ledger else "pt42_complete_state",
        }

    if isinstance(state_complete, dict) and isinstance(state_complete.get("order"), dict):
        order = state_complete["order"]
        symbol = order.get("symbol", "N/A")
        side = str(order.get("side", "N/A")).upper()
        qty = order.get("filled_qty", order.get("qty", "N/A"))
        timestamp = format_timestamp(state_complete.get("timestamp"))
        return {
            "summary": f"{symbol} {side} {qty}",
            "timestamp": timestamp,
            "order_id": str(order.get("broker_order_id", "n/a")),
            "source": "pt42_complete_state",
        }

    return {
        "summary": "none",
        "timestamp": "n/a",
        "order_id": "n/a",
        "source": "none",
    }


def extract_open_orders(log_text: str) -> str:
    for line in reversed(log_text.splitlines()):
        if "open orders" in line.lower():
            match = re.search(r"(\d+)", line)
            if match:
                return match.group(1)
    return "n/a"


def extract_account_mask(log_text: str, broker_config: dict | None) -> str:
    match = re.search(r"Account:\s+([A-Z0-9*]+)", log_text)
    if match:
        return match.group(1)
    if isinstance(broker_config, dict):
        return mask_value(broker_config.get("account_id"))
    return "n/a"


def latest_fill_summary(fills_ledger: list | None, state_complete: dict | None) -> str:
    fills = fills_ledger if isinstance(fills_ledger, list) and fills_ledger else []
    if not fills and isinstance(state_complete, dict):
        fills = state_complete.get("fills", []) or []
    if not fills:
        return "none"
    fill = fills[-1]
    symbol = fill.get("symbol", "N/A")
    side = fill.get("side", "N/A").upper()
    qty = fill.get("qty", fill.get("quantity", "N/A"))
    status = fill.get("status", "unknown")
    return f"{symbol} {side} {qty} ({status})"


def holdings_summary(state_complete: dict | None, broker_state: dict | None) -> tuple[str, int]:
    positions = {}
    if isinstance(state_complete, dict):
        positions = state_complete.get("positions", {}) or {}
    if not positions and isinstance(broker_state, dict):
        positions = broker_state.get("positions", {}) or {}
    non_zero = {k: v for k, v in positions.items() if abs(float(v)) > 1e-9}
    if not non_zero:
        return "none", 0
    sample = ", ".join(f"{symbol}:{qty}" for symbol, qty in list(sorted(non_zero.items()))[:8])
    return sample, len(non_zero)


def safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def normalize_positions(raw_positions: dict | None) -> dict[str, float]:
    normalized: dict[str, float] = {}
    if not isinstance(raw_positions, dict):
        return normalized
    for symbol, qty in raw_positions.items():
        qty_float = safe_float(qty)
        if qty_float is None or abs(qty_float) <= 1e-9:
            continue
        normalized[str(symbol)] = qty_float
    return dict(sorted(normalized.items()))


def positions_match(local_positions: dict | None, broker_positions: dict | None) -> bool:
    return normalize_positions(local_positions) == normalize_positions(broker_positions)


def current_reconciled_panel(
    *,
    state_complete: dict | None,
    broker_state: dict | None,
    fills_ledger: list | None,
    sync_report: dict | None,
    sync_validation: dict | None,
    main_started_at: datetime | None,
) -> dict[str, Any]:
    local_positions = normalize_positions((state_complete or {}).get("positions", {}))
    broker_positions = normalize_positions((broker_state or {}).get("positions", {}))
    local_cash = safe_float((state_complete or {}).get("cash"))
    broker_cash = safe_float((broker_state or {}).get("cash"))
    local_fills_count = len(fills_ledger or (state_complete or {}).get("fills", []) or [])
    broker_fills_count = None
    if isinstance(broker_state, dict):
        broker_fills_count = int(broker_state.get("fills_count", 0))
    elif isinstance(sync_report, dict):
        broker_fills_count = int(sync_report.get("after", {}).get("fills_count", 0))

    validation_recon = {}
    if isinstance(sync_validation, dict):
        validation_recon = sync_validation.get("current_recon", {}) or {}

    orders_status = str(validation_recon.get("orders_recon") or validation_recon.get("orders") or "").upper()
    if not orders_status:
        open_orders = (broker_state or {}).get("open_orders", []) if isinstance(broker_state, dict) else []
        orders_status = "MATCHED" if isinstance(open_orders, list) and len(open_orders) == 0 else "UNKNOWN"

    positions_status = str(validation_recon.get("positions_recon") or validation_recon.get("positions") or "").upper()
    if not positions_status:
        positions_status = "MATCHED" if positions_match(local_positions, broker_positions) else "MISMATCHED"

    cash_status = str(validation_recon.get("cash_recon") or validation_recon.get("cash") or "").upper()
    if not cash_status:
        if local_cash is not None and broker_cash is not None:
            cash_status = "MATCHED" if abs(local_cash - broker_cash) <= 0.01 else "MISMATCHED"
        else:
            cash_status = "UNKNOWN"

    fills_status = str(validation_recon.get("fills_recon") or validation_recon.get("fills") or "").upper()
    if not fills_status:
        if broker_fills_count is not None:
            fills_status = "MATCHED" if local_fills_count == broker_fills_count else "MISMATCHED"
        else:
            fills_status = "UNKNOWN"

    overall_status = str(validation_recon.get("overall") or "").upper()
    if not overall_status:
        if {orders_status, positions_status, cash_status, fills_status} == {"MATCHED"}:
            overall_status = "MATCHED"
        elif "MISMATCHED" in {orders_status, positions_status, cash_status, fills_status}:
            overall_status = "MISMATCHED"
        else:
            overall_status = "UNKNOWN"

    timestamp_raw = None
    for candidate in (
        (sync_validation or {}).get("timestamp") if isinstance(sync_validation, dict) else None,
        (sync_report or {}).get("timestamp") if isinstance(sync_report, dict) else None,
        (state_complete or {}).get("timestamp") if isinstance(state_complete, dict) else None,
        (broker_state or {}).get("timestamp") if isinstance(broker_state, dict) else None,
    ):
        if candidate:
            timestamp_raw = candidate
            break

    timestamp_dt = parse_any_timestamp(timestamp_raw)
    newer_than_main = bool(timestamp_dt and main_started_at and timestamp_dt > main_started_at)

    auto_repair = str((sync_validation or {}).get("auto_repair_success", "none")) if isinstance(sync_validation, dict) else "none"
    validation_status = str((sync_validation or {}).get("post_trade_sync_validation", "n/a")) if isinstance(sync_validation, dict) else "n/a"

    current_overall_display = "CURRENT_RECON_MATCHED" if overall_status == "MATCHED" else overall_status
    auto_repair_display = "AUTO_REPAIR_SUCCESS" if auto_repair == "YES" else ("AUTO_REPAIR_FAILED" if auto_repair == "NO" else "none")
    validation_display = (
        "POST_TRADE_SYNC_VALIDATION_OK"
        if validation_status == "OK"
        else ("POST_TRADE_SYNC_VALIDATION_FAILED" if validation_status == "FAILED" else "n/a")
    )

    return {
        "overall": overall_status,
        "overall_display": current_overall_display,
        "orders": orders_status or "UNKNOWN",
        "positions": positions_status or "UNKNOWN",
        "cash": cash_status or "UNKNOWN",
        "fills": fills_status or "UNKNOWN",
        "timestamp": format_timestamp(timestamp_raw),
        "timestamp_raw": timestamp_raw or "n/a",
        "newer_than_main": newer_than_main,
        "newer_than_main_display": "newer than main run" if newer_than_main else "same/older than main run",
        "auto_repair": auto_repair,
        "auto_repair_display": auto_repair_display,
        "post_trade_sync_validation": validation_status,
        "post_trade_sync_validation_display": validation_display,
        "source": "validation + sync state" if isinstance(sync_validation, dict) else ("sync state" if isinstance(sync_report, dict) else "local snapshots"),
    }


def build_snapshot(name: str, cfg: dict[str, Any]) -> dict[str, Any]:
    daily_log_text = read_text(cfg["daily_log"])
    launchd_out_text = read_text(cfg["launchd_out"])
    launchd_err_text = read_text(cfg["launchd_err"])
    preview = read_json(cfg["preview_json"]) or {}
    run_log = read_json(cfg["daily_run_log"])
    state_complete = read_json(cfg["state_complete"])
    broker_state = read_json(cfg["broker_state"])
    fills_ledger = read_json(cfg["fills_ledger"])
    sync_report = read_json(cfg["last_sync_report"])
    sync_validation = read_json(cfg["sync_validation"])
    dashboard_summary = read_json(cfg["dashboard_summary"])
    broker_config = read_json(cfg["broker_config"])
    launchd = launchd_snapshot(cfg["launchd_label"])
    latest_run = latest_run_entry(run_log)
    log_sources = build_log_sources(cfg, daily_log_text, launchd_out_text, launchd_err_text)
    kv = log_sources[0]["kv"] if log_sources else {}

    invocation_log = latest_log_summary(cfg, manual_force=False)
    main_log = latest_log_summary(cfg, eligible_main=True)
    manual_force_log = latest_log_summary(cfg, manual_force=True)
    preview_log = preview_log_summary(cfg, preview)

    # Section 5 data chain dates MUST come from main_log (current valid main run)
    # NOT from log_sources (which may include latest skipped/out_of_window runs)
    if main_log:
        feature_date = main_log["kv"].get("FEATURE_DATE") or preview.get("feature_date")
        prediction_date = main_log["kv"].get("PREDICTION_DATE") or preview.get("prediction_date")
        read_date = main_log["kv"].get("PT44_READ_DATE") or preview.get("prediction_date")
    else:
        # Fallback to log_sources only if no main_log exists
        feature_date = first_kv_value(log_sources, "FEATURE_DATE") or preview.get("feature_date")
        prediction_date = first_kv_value(log_sources, "PREDICTION_DATE") or preview.get("prediction_date")
        read_date = first_kv_value(log_sources, "PT44_READ_DATE") or preview.get("prediction_date")

    main_run_id = main_log["run_id"] if main_log and main_log.get("run_id") and not is_preview_run_id(main_log.get("run_id")) else "n/a"
    completed_run = {
        "run_id": (latest_run or {}).get("run_id", "n/a") if latest_run else "n/a",
        "status": (latest_run or {}).get("status", "n/a") if latest_run else "n/a",
        "timestamp": format_timestamp((latest_run or {}).get("timestamp")) if latest_run else "n/a",
        "timestamp_raw": (latest_run or {}).get("timestamp", "n/a") if latest_run else "n/a",
    }
    main_run_raw_status = main_log["status"] if main_log else "none"
    main_run_status = main_run_raw_status
    main_run_timestamp = main_log["started_display"] if main_log else "n/a"
    main_run_started_at = main_log["started_at"] if main_log else None

    preview_pipeline = parse_preview_pipeline(preview, preview_log)
    main_pipeline = parse_main_pipeline(main_log)

    preview_run = {
        "run_id": preview.get("run_id", "none"),
        "status": preview_pipeline["preview_state"],
        "timestamp": format_timestamp(preview.get("exported_at")),
        "order_count": str(preview.get("order_count", 0)),
        "holdings_source": preview.get("holdings_source", "n/a"),
        "feature_date": preview.get("feature_date", feature_date or "n/a"),
        "prediction_date": preview.get("prediction_date", prediction_date or "n/a"),
        "signal_status": preview_pipeline["signal"],
        "target_status": preview_pipeline["target"],
        "delta_status": preview_pipeline["delta"],
        "gate_status": preview_pipeline["gate"],
        "no_order_reason": preview_pipeline["no_order_reason"],
        "gate_reason": preview_pipeline["gate_reason"],
        "log_path": str(preview_log["path"]) if preview_log else "n/a",
    }

    latest_invocation = {
        "run_id": invocation_log.get("run_id") or "n/a" if invocation_log else "n/a",
        "status": invocation_log["status"] if invocation_log else "none",
        "timestamp": invocation_log["started_display"] if invocation_log else "n/a",
        "log_path": str(invocation_log["path"]) if invocation_log else "n/a",
        "window_status": invocation_log.get("window_status", "n/a") if invocation_log else "n/a",
        "reason": (
            invocation_log.get("window_reason", "n/a")
            if invocation_log and invocation_log.get("window_status") == "out_of_window"
            else (invocation_log.get("failure_reason", "n/a") if invocation_log else "n/a")
        ),
        "feature_status": invocation_log.get("feature_status", "n/a") if invocation_log else "n/a",
        "prediction_status": invocation_log.get("prediction_status", "n/a") if invocation_log else "n/a",
        "validation_status": invocation_log.get("validation_status", "n/a") if invocation_log else "n/a",
        "pt44_status": invocation_log.get("pt44_status", "n/a") if invocation_log else "n/a",
    }

    manual_force_context = {
        "run_id": manual_force_log["preview_run_id"] or "none" if manual_force_log else "none",
        "status": manual_force_log["status"] if manual_force_log else "none",
        "timestamp": manual_force_log["started_display"] if manual_force_log else "n/a",
        "feature_status": manual_force_log["feature_status"] if manual_force_log else "n/a",
        "prediction_status": manual_force_log["prediction_status"] if manual_force_log else "n/a",
        "validation_status": manual_force_log["validation_status"] if manual_force_log else "n/a",
        "pt44_status": manual_force_log["pt44_status"] if manual_force_log else "n/a",
        "log_path": str(manual_force_log["path"]) if manual_force_log else "n/a",
    }

    main_run = {
        "run_id": main_run_id,
        "status": main_run_status,
        "timestamp": main_run_timestamp,
        "timestamp_raw": main_run_started_at.isoformat() if main_run_started_at else "n/a",
        "log_path": str(main_log["path"]) if main_log else "n/a",
        "feature_status": main_log["feature_status"] if main_log else "n/a",
        "prediction_status": main_log["prediction_status"] if main_log else "n/a",
        "validation_status": main_log["validation_status"] if main_log else "n/a",
        "pt44_status": main_log["pt44_status"] if main_log else "n/a",
        "failure_reason": main_log["failure_reason"] if main_log else "n/a",
    }

    cash = None
    equity = None
    if isinstance(state_complete, dict):
        cash = safe_float(state_complete.get("cash"))
        equity = safe_float(state_complete.get("equity"))
    if cash is None and isinstance(broker_state, dict):
        cash = safe_float(broker_state.get("cash"))
    holdings_text, holdings_count = holdings_summary(state_complete, broker_state)

    historical_fill = latest_fill_record(fills_ledger, state_complete)
    fill_text = historical_fill["summary"]

    recon_value = "unknown"
    recon_tone = "neutral"
    if isinstance(dashboard_summary, dict):
        status_block = dashboard_summary.get("status", {})
        recon_value = status_block.get("reconciliation", recon_value)
        if recon_value in {"MATCHED", "OK", "PASS"}:
            recon_tone = "good"
        elif recon_value not in {"unknown", "n/a"}:
            recon_tone = "warn"

    feature_stale_text, feature_stale_tone = stale_badge(feature_date)
    pred_stale_text, pred_stale_tone = stale_badge(prediction_date)
    reconciled_state = current_reconciled_panel(
        state_complete=state_complete,
        broker_state=broker_state,
        fills_ledger=fills_ledger,
        sync_report=sync_report,
        sync_validation=sync_validation,
        main_started_at=main_run_started_at,
    )

    recovery_confirmed = (
        reconciled_state["overall"] == "MATCHED"
        and (
            reconciled_state["auto_repair"] == "YES"
            or reconciled_state["post_trade_sync_validation"] == "OK"
        )
    )
    if main_run_raw_status == "failed":
        main_run_status = "historical_failed_recovered" if recovery_confirmed else "real_failed_current"
    main_run["status"] = main_run_status
    main_run["raw_status"] = main_run_raw_status
    main_run["recovery_confirmed"] = recovery_confirmed

    return {
        "name": name,
        "cfg": cfg,
        "launchd": launchd,
        "daily_log_text": daily_log_text,
        "launchd_out_text": launchd_out_text,
        "launchd_err_text": launchd_err_text,
        "log_sources": log_sources,
        "kv": kv,
        "preview": preview,
        "run_log": run_log,
        "state_complete": state_complete,
        "broker_state": broker_state,
        "fills_ledger": fills_ledger,
        "sync_report": sync_report,
        "sync_validation": sync_validation,
        "dashboard_summary": dashboard_summary,
        "broker_config": broker_config,
        "feature_date": feature_date or "n/a",
        "prediction_date": prediction_date or "n/a",
        "read_date": read_date or "n/a",
        "feature_mtime": file_mtime(cfg["feature_file"]),
        "prediction_mtime": file_mtime(cfg["prediction_file"]),
        "feature_stale_text": feature_stale_text,
        "feature_stale_tone": feature_stale_tone,
        "pred_stale_text": pred_stale_text,
        "pred_stale_tone": pred_stale_tone,
        "recon_status": recon_value,
        "recon_tone": recon_tone,
        "broker_connection": "connected" if any("Connected to Alpaca" in source["text"] for source in log_sources) else "configured",
        "account_mask": extract_account_mask("\n".join(source["text"] for source in log_sources), broker_config),
        "cash": cash,
        "equity": equity,
        "holdings_text": holdings_text,
        "holdings_count": holdings_count,
        "latest_fill": fill_text,
        "historical_fill": historical_fill,
        "open_orders": extract_open_orders(daily_log_text),
        "invocation_log": invocation_log,
        "main_log": main_log,
        "preview_log": preview_log,
        "manual_force_log": manual_force_log,
        "latest_invocation": latest_invocation,
        "main_run": main_run,
        "completed_run": completed_run,
        "reconciled_state": reconciled_state,
        "preview_run": preview_run,
        "manual_force": manual_force_context,
        "main_pipeline": main_pipeline,
    }


def tone_for_status(value: str) -> str:
    lowered = str(value).lower()
    if lowered in {
        "success",
        "pass",
        "matched",
        "connected",
        "filled",
        "entered",
        "ack",
        "validation_ok",
        "active/running",
        "ready",
        "completed",
        "manual_force_validation_completed",
        "orders_ready",
        "exported",
        "observed",
    }:
        return "good"
    if lowered in {"blocked", "failed", "error", "mismatched", "not_loaded", "not loaded", "unavailable", "real_failed_current"}:
        return "bad"
    if lowered in {
        "skipped",
        "out_of_window",
        "historical_failed_recovered",
        "waiting",
        "configured",
        "pending",
        "warn",
        "unknown",
        "n/a",
        "not_reached",
        "idempotent_skip",
        "market_closed_skip",
        "in_progress",
        "idle/standby",
    }:
        # skipped/out_of_window are neutral (not current failures)
        # Only pending/warn/historical_failed_recovered are actual warnings
        return "warn" if lowered in {"pending", "warn", "historical_failed_recovered"} else "neutral"
    if lowered == "none":
        return "neutral"
    return "neutral"


def preview_dataframe(preview_payload: dict | None) -> pd.DataFrame:
    if not isinstance(preview_payload, dict):
        return pd.DataFrame()
    orders = preview_payload.get("orders", []) or []
    frame = pd.DataFrame(orders)
    if frame.empty:
        return frame
    wanted = ["symbol", "side", "qty", "target_weight", "reference_price", "notional", "reason"]
    existing = [column for column in wanted if column in frame.columns]
    return frame[existing]


def render_top_summary(snapshots: dict[str, dict[str, Any]]) -> None:
    market_text, market_tone = market_status()
    left, right = st.columns([1, 1])
    with left:
        st.markdown(
            status_chip(
                "纽约时间",
                now_ny().strftime("%Y-%m-%d %H:%M:%S %Z"),
                "neutral",
            ),
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(status_chip("市场状态", display_text(market_text, field="market"), market_tone), unsafe_allow_html=True)

    cols = st.columns(len(snapshots))
    for column, (name, snapshot) in zip(cols, snapshots.items()):
        with column:
            st.markdown(
                status_chip(
                    f"{name} 调度",
                    display_text(snapshot["launchd"]["status"], field="status"),
                    snapshot["launchd"]["tone"],
                ),
                unsafe_allow_html=True,
            )


def render_system_overview(snapshot: dict[str, Any]) -> None:
    st.subheader("1. 系统总览")
    latest_invocation = snapshot["latest_invocation"]
    main_run = snapshot["main_run"]
    preview_run = snapshot["preview_run"]
    items = [
        ("纽约时间", now_ny().strftime("%H:%M:%S %Z"), "neutral"),
        ("市场状态", display_text(market_status()[0], field="market"), market_status()[1]),
        ("调度状态", display_text(snapshot["launchd"]["status"], field="status"), snapshot["launchd"]["tone"]),
        ("最近一次调用", display_text(latest_invocation["status"], field="status"), tone_for_status(latest_invocation["status"])),
        (
            "最近一次有效主运行",
            display_text(
                main_run["run_id"],
                field="run_id",
                context={"failed_before_run_id": main_run.get("raw_status") == "failed"},
            ),
            tone_for_status(main_run["status"]),
        ),
        ("主运行状态", display_text(main_run["status"], field="status"), tone_for_status(main_run["status"])),
        (
            "最近预览结果",
            display_text(preview_run["status"], field="status"),
            tone_for_status(preview_run["status"]),
        ),
    ]
    cols = st.columns(len(items))
    for column, (label, value, tone) in zip(cols, items):
        with column:
            st.markdown(status_chip(label, str(value), tone), unsafe_allow_html=True)
    st.caption(
        f"最近一次调用时间：{display_text(latest_invocation['timestamp'], field='timestamp')} | "
        f"最近一次有效主运行时间：{display_text(main_run['timestamp'], field='timestamp')} | "
        f"最近预览时间：{display_text(preview_run['timestamp'], field='timestamp')}"
    )


def render_latest_invocation(snapshot: dict[str, Any]) -> None:
    st.subheader("2. 最近一次调用")
    latest_invocation = snapshot["latest_invocation"]
    cols = st.columns(4)
    items = [
        ("调用状态", display_text(latest_invocation["status"], field="status"), tone_for_status(latest_invocation["status"])),
        ("窗口判断", display_text(latest_invocation["window_status"], field="status"), tone_for_status(latest_invocation["window_status"])),
        ("PT44 状态", display_text(latest_invocation["pt44_status"], field="pt44_status"), tone_for_status(latest_invocation["pt44_status"])),
        ("调用时间", display_text(latest_invocation["timestamp"], field="timestamp"), "neutral"),
    ]
    for column, (label, value, tone) in zip(cols, items):
        with column:
            st.markdown(status_chip(label, str(value), tone), unsafe_allow_html=True)

    st.caption(f"调用日志：{display_text(latest_invocation['log_path'], field='log_path')}")
    st.caption(f"调用原因：{display_text(latest_invocation['reason'], field='failure_reason')}")
    st.caption(
        "这里显示最近一次被调起的运行；即使因超出交易窗口而跳过，也会记录在这里。"
    )
    if latest_invocation["status"] != "none":
        st.caption(
            f"raw status = {latest_invocation['status']} | raw window = {latest_invocation['window_status']}"
        )


def render_main_scheduled_run(snapshot: dict[str, Any]) -> None:
    st.subheader("3. 最近一次有效主运行")
    main_run = snapshot["main_run"]
    completed_run = snapshot["completed_run"]
    failed_before_run_id = main_run.get("raw_status") == "failed" and is_empty_display_value(main_run.get("run_id"))
    cols = st.columns(4)
    items = [
        (
            "运行 ID",
            display_text(
                main_run["run_id"],
                field="run_id",
                context={"failed_before_run_id": main_run.get("raw_status") == "failed"},
            ),
            tone_for_status(main_run["status"]),
        ),
        ("运行状态", display_text(main_run["status"], field="status"), tone_for_status(main_run["status"])),
        ("PT44 状态", display_text(main_run["pt44_status"], field="pt44_status"), tone_for_status(main_run["pt44_status"])),
        (
            "最近一次成功完成的运行",
            display_text(completed_run["run_id"], field="run_id"),
            tone_for_status(completed_run["status"]),
        ),
    ]
    for column, (label, value, tone) in zip(cols, items):
        with column:
            st.markdown(status_chip(label, str(value), tone), unsafe_allow_html=True)

    details_left, details_right = st.columns(2)
    details_left.caption(f"运行时间：{display_text(main_run['timestamp'], field='timestamp')}")
    details_left.caption(f"日志：{display_text(main_run['log_path'], field='log_path')}")
    details_left.caption("这里显示最近一次发生在有效交易窗口内的正式主运行。")
    if failed_before_run_id and not is_empty_display_value(completed_run.get("run_id")):
        details_left.info("最近一次有效主运行在分配运行 ID 前失败；最近一次成功完成的运行见右侧。")
    if main_run.get("raw_status") not in {None, "", "n/a"} and main_run.get("raw_status") != main_run.get("status"):
        details_left.caption(f"raw status = {main_run['raw_status']}")
    details_right.caption(
        "特征 / 预测 / 验证："
        f"{display_text(main_run['feature_status'], field='feature_status')} / "
        f"{display_text(main_run['prediction_status'], field='prediction_status')} / "
        f"{display_text(main_run['validation_status'], field='validation_status')}"
    )
    details_right.caption(f"失败原因：{display_text(main_run['failure_reason'], field='failure_reason')}")
    details_right.caption(
        f"最近一次成功完成的运行时间：{display_text(completed_run['timestamp'], field='timestamp')} | "
        f"状态：{display_text(completed_run['status'], field='status')}"
    )


def render_current_reconciled_state(snapshot: dict[str, Any]) -> None:
    st.subheader("4. 当前账本一致性 / 自动修复结果")
    current_state = snapshot["reconciled_state"]
    main_run = snapshot["main_run"]

    cols = st.columns(4)
    items = [
        ("当前整体状态", display_text(current_state["overall_display"], field="status"), tone_for_status(current_state["overall"])),
        ("订单对账", display_text(current_state["orders"], field="status"), tone_for_status(current_state["orders"])),
        ("持仓对账", display_text(current_state["positions"], field="status"), tone_for_status(current_state["positions"])),
        ("现金对账", display_text(current_state["cash"], field="status"), tone_for_status(current_state["cash"])),
        ("成交对账", display_text(current_state["fills"], field="status"), tone_for_status(current_state["fills"])),
        ("自动修复", display_text(current_state["auto_repair_display"], field="status"), tone_for_status("success" if current_state["auto_repair"] == "YES" else current_state["auto_repair"])),
        (
            "回写验证",
            display_text(current_state["post_trade_sync_validation_display"], field="status"),
            tone_for_status("success" if current_state["post_trade_sync_validation"] == "OK" else current_state["post_trade_sync_validation"]),
        ),
        ("相对主运行更新时间", "晚于主运行" if current_state["newer_than_main"] else "不晚于主运行", "good" if current_state["newer_than_main"] else "neutral"),
    ]
    for idx, (label, value, tone) in enumerate(items):
        with cols[idx % 4]:
            st.markdown(status_chip(label, str(value), tone), unsafe_allow_html=True)

    st.caption(
        f"当前对齐时间：{display_text(current_state['timestamp'], field='timestamp')} | "
        f"来源：{display_text(current_state['source'], field='source')} | "
        f"{'晚于主运行' if current_state['newer_than_main'] else '不晚于主运行'}"
    )
    raw_main_status = str(main_run.get("raw_status", main_run["status"])).lower()
    if (
        raw_main_status == "failed"
        and current_state["overall"] == "MATCHED"
        and current_state["newer_than_main"]
    ):
        st.success("历史主运行曾失败，但当前状态已恢复。")
    elif raw_main_status == "failed" and current_state["overall"] != "MATCHED":
        st.error("历史主运行曾失败，当前状态尚未恢复。")
    elif current_state["overall"] == "MATCHED":
        st.success("当前券商与本地账本已对齐。")
    else:
        st.warning("当前券商与本地账本仍需进一步核对。")
    st.caption(
        "此区域显示当前券商与本地账本的一致性状态，以及最近一次自动修复/回写验证结果。"
    )
    st.caption(
        "raw overall = "
        f"{current_state['overall']} | raw auto repair = {current_state['auto_repair']} | "
        f"raw sync validation = {current_state['post_trade_sync_validation']}"
    )


def render_data_pipeline(snapshot: dict[str, Any]) -> None:
    st.subheader("5. 数据链状态")
    cols = st.columns(5)
    data_items = [
        ("特征日期", display_text(snapshot["feature_date"]), snapshot["feature_stale_tone"]),
        ("预测日期", display_text(snapshot["prediction_date"]), snapshot["pred_stale_tone"]),
        ("PT44 读取日期", display_text(snapshot["read_date"]), tone_for_status("success" if snapshot["read_date"] != "n/a" else "unknown")),
        ("特征新鲜度", snapshot["feature_stale_text"], snapshot["feature_stale_tone"]),
        ("预测新鲜度", snapshot["pred_stale_text"], snapshot["pred_stale_tone"]),
    ]
    for column, (label, value, tone) in zip(cols, data_items):
        with column:
            st.markdown(status_chip(label, str(value), tone), unsafe_allow_html=True)

    meta_col1, meta_col2 = st.columns(2)
    meta_col1.caption(f"特征文件更新时间：{display_text(snapshot['feature_mtime'], field='timestamp')}")
    meta_col2.caption(f"预测文件更新时间：{display_text(snapshot['prediction_mtime'], field='timestamp')}")


def render_trading_pipeline(snapshot: dict[str, Any]) -> None:
    st.subheader("6. 交易链状态")
    pipeline = snapshot["main_pipeline"]
    cols = st.columns(4)
    stages = [
        ("Signal", pipeline["signal"]),
        ("Target", pipeline["target"]),
        ("Delta", pipeline["delta"]),
        ("Gate", pipeline["gate"]),
        ("Submit", pipeline["submit"]),
        ("Ack", pipeline["ack"]),
        ("Fill", pipeline["fill"]),
        ("Recon", pipeline["recon"]),
    ]
    for idx, (label, value) in enumerate(stages):
        with cols[idx % 4]:
            st.markdown(status_chip(label, display_text(value, field="status"), tone_for_status(value)), unsafe_allow_html=True)

    info_cols = st.columns(2)
    info_cols[0].caption(f"主运行无单原因：{display_text(pipeline['no_order_reason'], field='no_order_reason')}")
    info_cols[1].caption(f"主运行 gate 原因：{display_text(pipeline['gate_reason'], field='gate_reason')}")
    st.caption(
        "这里仅显示最近一次非 force 的正式主运行结果。预览结果与历史成交会在下方单独展示。"
    )


def render_preview_validation(snapshot: dict[str, Any]) -> None:
    st.subheader("7. 预览 / 验证")
    preview_run = snapshot["preview_run"]
    cols = st.columns(4)
    items = [
        ("预览运行 ID", display_text(preview_run["run_id"], field="run_id"), tone_for_status(preview_run["status"])),
        ("预览状态", display_text(preview_run["status"], field="status"), tone_for_status(preview_run["status"])),
        ("预览订单数", preview_run["order_count"], "neutral"),
        ("持仓来源", display_text(preview_run["holdings_source"], field="holdings_source"), "neutral"),
    ]
    for column, (label, value, tone) in zip(cols, items):
        with column:
            st.markdown(status_chip(label, str(value), tone), unsafe_allow_html=True)

    pipeline_cols = st.columns(4)
    preview_pipeline_items = [
        ("预览 Signal", preview_run["signal_status"]),
        ("预览 Target", preview_run["target_status"]),
        ("预览 Delta", preview_run["delta_status"]),
        ("预览 Gate", preview_run["gate_status"]),
    ]
    for column, (label, value) in zip(pipeline_cols, preview_pipeline_items):
        with column:
            st.markdown(status_chip(label, display_text(value, field="status"), tone_for_status(value)), unsafe_allow_html=True)

    caption_left, caption_right = st.columns(2)
    caption_left.caption(
        f"时间：{display_text(preview_run['timestamp'], field='timestamp')} | "
        f"特征 / 预测：{display_text(preview_run['feature_date'])} / {display_text(preview_run['prediction_date'])}"
    )
    caption_left.caption(f"预览 / 验证日志：{display_text(preview_run['log_path'], field='preview_log_path')}")
    caption_right.caption(f"无单原因：{display_text(preview_run['no_order_reason'], field='no_order_reason')}")
    caption_right.caption(f"Gate 原因：{display_text(preview_run['gate_reason'], field='gate_reason')}")


def render_manual_force(snapshot: dict[str, Any]) -> None:
    st.subheader("8. 手动强制验证")
    manual_force = snapshot["manual_force"]
    cols = st.columns(4)
    items = [
        ("手动验证运行", display_text(manual_force["run_id"], field="run_id"), tone_for_status(manual_force["status"])),
        ("状态", display_text(manual_force["status"], field="status"), tone_for_status(manual_force["status"])),
        ("验证结果", display_text(manual_force["validation_status"], field="validation_status"), tone_for_status(manual_force["validation_status"])),
        ("PT44 状态", display_text(manual_force["pt44_status"], field="pt44_status"), tone_for_status(manual_force["pt44_status"])),
    ]
    for column, (label, value, tone) in zip(cols, items):
        with column:
            st.markdown(status_chip(label, str(value), tone), unsafe_allow_html=True)

    st.caption(
        f"时间：{display_text(manual_force['timestamp'], field='timestamp')} | "
        f"特征 / 预测：{display_text(manual_force['feature_status'], field='feature_status')} / {display_text(manual_force['prediction_status'], field='prediction_status')}"
    )
    st.caption(f"手动验证日志：{display_text(manual_force['log_path'], field='manual_force_log')}")


def render_historical_execution(snapshot: dict[str, Any]) -> None:
    st.subheader("9. 历史执行记录")
    historical_fill = snapshot["historical_fill"]
    cols = st.columns(4)
    items = [
        ("最近历史成交", display_text(historical_fill["summary"], field="historical_fill"), tone_for_status("filled" if historical_fill["summary"] != "none" else "none")),
        ("成交时间", display_text(historical_fill["timestamp"], field="fill_timestamp"), "neutral"),
        ("订单 ID", display_text(historical_fill["order_id"], field="order_id"), "neutral"),
        ("来源", display_text(historical_fill["source"], field="source"), "neutral"),
    ]
    for column, (label, value, tone) in zip(cols, items):
        with column:
            st.markdown(status_chip(label, str(value), tone), unsafe_allow_html=True)
    st.caption("这里展示历史成交证据，不代表当前主运行已经进入成交阶段。")


def render_account_panel(snapshot: dict[str, Any]) -> None:
    st.subheader("10. 账户与持仓")
    col1, col2, col3 = st.columns(3)
    col1.markdown(status_chip("券商连接", display_text(snapshot["broker_connection"], field="status"), tone_for_status(snapshot["broker_connection"])), unsafe_allow_html=True)
    col2.markdown(status_chip("券商账户", snapshot["account_mask"], "neutral"), unsafe_allow_html=True)
    col3.markdown(status_chip("未完成订单", display_text(snapshot["open_orders"], field="open_orders"), "neutral"), unsafe_allow_html=True)

    metrics = st.columns(4)
    metrics[0].metric("现金", "暂无" if snapshot["cash"] is None else f"${snapshot['cash']:,.2f}")
    metrics[1].metric("权益", "暂无" if snapshot["equity"] is None else f"${snapshot['equity']:,.2f}")
    metrics[2].metric("持仓数", snapshot["holdings_count"])
    metrics[3].metric("最近历史成交", display_text(snapshot["latest_fill"], field="latest_fill"))
    st.caption(f"持仓摘要：{display_text(snapshot['holdings_text'], field='holdings_text')}")


def render_preview_panel(snapshot: dict[str, Any]) -> None:
    st.subheader("11. 预览订单明细")
    preview_payload = snapshot["preview"]
    preview_df = preview_dataframe(preview_payload)
    if preview_df.empty:
        st.info("暂未生成预览订单。")
        return
    st.caption(
        f"预览文件：{snapshot['cfg']['preview_json']} | "
        f"运行 ID：{display_text(preview_payload.get('run_id', 'n/a'), field='run_id')} | "
        f"订单数：{preview_payload.get('order_count', len(preview_df))}"
    )
    st.dataframe(preview_df, width="stretch", hide_index=True)


def render_logs_panel(snapshot: dict[str, Any], instance_name: str) -> None:
    st.subheader("12. 日志面板")
    latest_invocation = snapshot["latest_invocation"]
    main_run = snapshot["main_run"]
    completed_run = snapshot["completed_run"]
    manual_force = snapshot["manual_force"]
    current_state = snapshot["reconciled_state"]

    st.caption("默认先看摘要；下方原始日志已折叠，仅用于追溯。")
    summary_cols = st.columns(2)
    with summary_cols[0]:
        st.info(
            "最近一次调用摘要："
            f"{display_text(latest_invocation['status'], field='status')}；"
            f"原因：{display_text(latest_invocation['reason'], field='failure_reason')}"
        )
        if main_run.get("status") == "historical_failed_recovered":
            main_summary = (
                "最近一次有效主运行摘要：历史主运行曾失败，"
                f"原因是{display_text(main_run['failure_reason'], field='failure_reason')}；当前已恢复。"
            )
        else:
            main_summary = (
                "最近一次有效主运行摘要："
                f"{display_text(main_run['status'], field='status')}；"
                f"原因：{display_text(main_run['failure_reason'], field='failure_reason')}"
            )
        st.info(main_summary)
    with summary_cols[1]:
        st.info(
            "手动验证摘要："
            f"{display_text(manual_force['status'], field='status')}。"
        )
        st.info(
            "当前账本摘要："
            f"{display_text(current_state['overall_display'], field='status')}；"
            f"自动修复：{display_text(current_state['auto_repair_display'], field='status')}；"
            f"回写验证：{display_text(current_state['post_trade_sync_validation_display'], field='status')}。"
        )
    if main_run.get("raw_status") == "failed" and is_empty_display_value(main_run.get("run_id")) and not is_empty_display_value(completed_run.get("run_id")):
        st.caption("最近一次有效主运行在分配运行 ID 前失败；最近一次成功完成的运行请查看上方主运行区块。")
    st.caption("下方为原始日志原文；其中的红叉和技术状态属于历史记录，不代表当前主判断卡片仍处于故障。")

    recent_lines = st.slider(
        "显示最近 N 行",
        min_value=20,
        max_value=400,
        value=80,
        step=20,
        key=f"{instance_name}_recent_lines",
    )
    only_new = st.checkbox(
        f"仅显示本次打开页面后的新增内容（{instance_name}）",
        value=False,
        key=f"{instance_name}_only_new",
    )

    log_sources: list[tuple[str, Path | None]] = [
        ("最近一次调用日志", Path(snapshot["latest_invocation"]["log_path"]) if snapshot["latest_invocation"]["log_path"] != "n/a" else snapshot["cfg"]["daily_log"]),
        ("最近一次有效主运行日志", Path(snapshot["main_run"]["log_path"]) if snapshot["main_run"]["log_path"] != "n/a" else None),
        ("预览 / 验证日志", Path(snapshot["preview_run"]["log_path"]) if snapshot["preview_run"]["log_path"] != "n/a" else snapshot["cfg"]["preview_json"]),
        ("手动验证日志", Path(snapshot["manual_force"]["log_path"]) if snapshot["manual_force"]["log_path"] != "n/a" else None),
        ("Launchd STDOUT 尾部", snapshot["cfg"]["launchd_out"]),
        ("Launchd STDERR 尾部", snapshot["cfg"]["launchd_err"]),
    ]

    for label, path in log_sources:
        with st.expander(f"{label}: {path}", expanded=False):
            if path is None:
                st.code("暂无日志内容。", language="text")
                continue
            if path.suffix in {".json", ".csv"}:
                content = read_text(path).strip() or "暂无日志内容。"
                st.code(content, language="text")
                continue
            lines = tail_lines(path, recent_lines if not only_new else 1000)
            if only_new:
                baseline_key = f"log_baseline::{instance_name}::{label}"
                if baseline_key not in st.session_state or len(lines) < st.session_state[baseline_key]:
                    st.session_state[baseline_key] = len(lines)
                lines = lines[st.session_state[baseline_key]:]
            content = "".join(lines).strip() or "暂无日志内容。"
            st.code(content, language="text")


def render_instance_tab(snapshot: dict[str, Any], instance_name: str) -> None:
    render_system_overview(snapshot)
    st.divider()
    render_latest_invocation(snapshot)
    st.divider()
    render_main_scheduled_run(snapshot)
    st.divider()
    render_current_reconciled_state(snapshot)
    st.divider()
    render_data_pipeline(snapshot)
    st.divider()
    render_trading_pipeline(snapshot)
    st.divider()
    render_preview_validation(snapshot)
    st.divider()
    render_manual_force(snapshot)
    st.divider()
    render_historical_execution(snapshot)
    st.divider()
    render_account_panel(snapshot)
    st.divider()
    render_preview_panel(snapshot)
    st.divider()
    render_logs_panel(snapshot, instance_name)


st.title("Godfather Control Center")
st.caption("本地只读控制中心，统一展示 V9.0 与 V9.1 Sandbox 的运行、账本、预览与日志状态。页面每 10 秒自动刷新。")

if DEMO_MODE:
    st.info("🎭 Demo Mode — displaying sample data. Set GODFATHER_DEMO=0 and configure GODFATHER_ROOT to use live data.", icon="ℹ️")


def build_demo_snapshot(name: str) -> dict[str, Any]:
    """Return a realistic-looking snapshot with sample data for demo/preview purposes."""
    today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    return {
        "name": name,
        "cfg": INSTANCES[name],
        "launchd": {"status": "idle/standby", "tone": "neutral", "raw_state": "waiting", "active_count": "0", "runs": "42", "last_exit": "0"},
        "daily_log_text": f"[DEMO] Godfather {name} — sample log output\nFeature refresh: success\nPrediction: success\nValidation: success\nPT.4.4 unified: success\nFinished: {today}",
        "launchd_out_text": "",
        "launchd_err_text": "",
        "log_sources": [],
        "kv": {},
        "preview": {"run_id": f"pt44_preview_{today.replace('-','')}_demo", "order_count": 5, "exported_at": today + "T09:45:00", "feature_date": today, "prediction_date": today, "holdings_source": "broker"},
        "run_log": None,
        "state_complete": {"cash": 9850.25, "equity": 10234.50, "holdings": {"AAPL": {"qty": 10, "avg_price": 185.0}, "MSFT": {"qty": 5, "avg_price": 415.0}}},
        "broker_state": {"cash": 9850.25},
        "fills_ledger": None,
        "sync_report": None,
        "sync_validation": None,
        "dashboard_summary": {"status": {"reconciliation": "MATCHED"}},
        "broker_config": {"api_key": "DEMO_KEY_XXXX", "base_url": "https://paper-api.alpaca.markets"},
        "feature_date": today,
        "prediction_date": today,
        "read_date": today,
        "feature_mtime": today + " 08:30:00 EST",
        "prediction_mtime": today + " 08:45:00 EST",
        "feature_stale_text": "fresh",
        "feature_stale_tone": "good",
        "pred_stale_text": "fresh",
        "pred_stale_tone": "good",
        "recon_status": "MATCHED",
        "recon_tone": "good",
        "broker_connection": "configured",
        "account_mask": "DEMO***XXXX",
        "cash": 9850.25,
        "equity": 10234.50,
        "holdings_text": "AAPL ×10 | MSFT ×5",
        "holdings_count": 2,
        "latest_fill": "AAPL ×10 @ $185.00 (demo)",
        "historical_fill": {"summary": "AAPL ×10 @ $185.00 (demo)", "timestamp": today},
        "open_orders": "none",
        "invocation_log": None,
        "main_log": None,
        "preview_log": None,
        "manual_force_log": None,
        "latest_invocation": {"run_id": "demo_run_001", "status": "success", "timestamp": today + " 10:05:00 EST", "log_path": "n/a", "window_status": "eligible", "reason": "n/a", "feature_status": "success", "prediction_status": "success", "validation_status": "success", "pt44_status": "success"},
        "main_run": {"run_id": "demo_run_001", "status": "success", "timestamp": today + " 10:05:00 EST", "timestamp_raw": today + "T10:05:00", "log_path": "n/a", "feature_status": "success", "prediction_status": "success", "validation_status": "success", "pt44_status": "success", "failure_reason": "n/a", "raw_status": "success", "recovery_confirmed": False},
        "completed_run": {"run_id": "demo_run_001", "status": "success", "timestamp": today + " 10:05:00 EST", "timestamp_raw": today + "T10:05:00"},
        "reconciled_state": {"overall": "MATCHED", "auto_repair": "NO", "post_trade_sync_validation": "OK", "holdings_match": "YES", "cash_match": "YES", "open_orders": "none"},
        "preview_run": {"run_id": f"pt44_preview_{today.replace('-','')}_demo", "status": "exported", "timestamp": today + " 09:45:00 EST", "order_count": "5", "holdings_source": "broker", "feature_date": today, "prediction_date": today, "signal_status": "success", "target_status": "success", "delta_status": "success", "gate_status": "PASS", "no_order_reason": "orders_ready", "gate_reason": "none", "log_path": "n/a"},
        "manual_force": {"run_id": "none", "status": "none", "timestamp": "n/a", "feature_status": "n/a", "prediction_status": "n/a", "validation_status": "n/a", "pt44_status": "n/a", "log_path": "n/a"},
        "main_pipeline": {"signal": "success", "target": "success", "delta": "success", "gate": "PASS", "submit": "entered", "ack": "ack", "fill": "filled", "recon": "matched", "no_order_reason": "orders_ready", "gate_reason": "none"},
        "root": INSTANCES[name]["root"],
    }


@st.fragment(run_every="10s")
def render_dashboard() -> None:
    if DEMO_MODE:
        snapshots = {name: build_demo_snapshot(name) for name in INSTANCES}
    else:
        snapshots = {name: build_snapshot(name, cfg) for name, cfg in INSTANCES.items()}
    render_top_summary(snapshots)
    tab_v90, tab_v91 = st.tabs(["V9.0", "V9.1"])
    with tab_v90:
        render_instance_tab(snapshots["V9.0"], "V9.0")
    with tab_v91:
        render_instance_tab(snapshots["V9.1"], "V9.1")


def render_v10_ai_engine_status(snapshot: dict[str, Any]) -> None:
    """V10 AI Engine 状态"""
    st.subheader("🤖 V10 AI Engine Status")
    
    root = snapshot["root"]
    regime_file = root / "data/ai_engine/daily_regime_state.json"
    conf_file = root / "data/ai_engine/latest_confidence_snapshot.json"
    si_dir = root / "data/external/short_interest"
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Regime Engine**")
        if regime_file.exists():
            regime = json.loads(regime_file.read_text())
            st.metric("State", regime["state_name"])
            st.metric("Budget Multiplier", f"{regime['budget_multiplier']:.2f}")
            st.metric("Hold Buffer", f"{regime['hold_buffer']:.0%}")
        else:
            st.warning("Regime data not found")
    
    with col2:
        st.markdown("**Confidence Engine**")
        if conf_file.exists():
            conf = json.loads(conf_file.read_text())
            st.metric("Avg Confidence", f"{conf['avg_confidence']:.3f}")
            st.metric("High Conf", conf["high_conf_count"])
            st.metric("Low Conf", conf["low_conf_count"])
        else:
            st.warning("Confidence data not found")
    
    with col3:
        st.markdown("**Short Interest Data**")
        if si_dir.exists():
            files = list(si_dir.glob("*.parquet"))
            if files:
                latest = max(files, key=lambda f: f.stat().st_mtime)
                df = pd.read_parquet(latest)
                st.metric("Coverage", len(df))
                st.metric("Last Update", latest.stem.split("_")[-1])
                st.success("Data OK")
            else:
                st.warning("No data files")
        else:
            st.warning("Data dir not found")


def render_shortfall_status(snapshot: dict[str, Any]) -> None:
    """V9.9 Shortfall & Turnover Status"""
    st.subheader("📉 Implementation Shortfall & Turnover")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Execution Cost Model**")
        st.metric("Estimated Cost", "10.5 bps")
        st.metric("Min Alpha Threshold", "25 bps")
        st.metric("Target Turnover", "40%")
    
    with col2:
        st.markdown("**Filtering Summary**")
        st.metric("Filtered Small Deltas", "N/A")
        st.metric("Filtered Negative Net", "N/A")
        st.metric("Expected Shortfall Reduction", "200+ bps")


def render_shortfall_calibration(snapshot: dict[str, Any]) -> None:
    """V9.9a Shortfall Calibration Status"""
    st.subheader("🎯 Shortfall Model Calibration")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Thresholds**")
        st.metric("Min Delta USD", "$75")
        st.metric("State 0 (Low)", "20 bps")
        st.metric("State 1 (Normal)", "35 bps")
        st.metric("State 2 (High)", "55 bps")
    
    with col2:
        st.markdown("**Cost Breakdown**")
        st.metric("Commission", "~10 bps")
        st.metric("Spread", "~3 bps")
        st.metric("Overnight Gap", "~8 bps")
        st.metric("Delay Buffer", "15 bps")
    
    with col3:
        st.markdown("**Filtering Stats**")
        st.metric("Filtered Small", "N/A")
        st.metric("Filtered Negative", "N/A")
        st.metric("Avg Cost", "~36 bps")


render_dashboard()
