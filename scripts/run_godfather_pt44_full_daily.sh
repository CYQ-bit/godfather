#!/bin/bash
# Godfather V9.0 - PT.4.4g Full Daily Scheduler
# Single entry for feature refresh -> fresh predictions -> PT.4.4 unified execution

set -euo pipefail

QUANT_LAB_DIR="${GODFATHER_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
LOG_DIR="$QUANT_LAB_DIR/logs"
LOCK_DIR="$LOG_DIR/pt44g_full_daily.lock"
RUN_STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/pt44g_full_daily_${RUN_STAMP}.log"
LATEST_LOG_LINK="$LOG_DIR/pt44g_full_daily_latest.log"

mkdir -p "$LOG_DIR"
touch "$LOG_FILE"
ln -sfn "$(basename "$LOG_FILE")" "$LATEST_LOG_LINK"

FORCE_MODE=0
if [ "${FORCE_RUN:-0}" = "1" ]; then
    FORCE_MODE=1
fi

for arg in "$@"; do
    case "$arg" in
        --force)
            FORCE_MODE=1
            ;;
        *)
            ;;
    esac
done

log() {
    printf '%s\n' "$1" | tee -a "$LOG_FILE"
}

cleanup() {
    rm -rf "$LOCK_DIR"
}

log_runtime_paths() {
    while IFS= read -r line; do
        log "$line"
    done < <(
        python3 - <<'PY'
from runtime_paths import get_runtime_path_report

for key, value in get_runtime_path_report().items():
    print(f"{key}={value}")
PY
    )
}

load_ny_clock() {
    local ny_output
    ny_output="$(python3 - <<'PY'
from datetime import datetime, time
from zoneinfo import ZoneInfo

ny = datetime.now(ZoneInfo("America/New_York"))
if ny.time() < time(9, 0):
    phase = "before_premarket"
elif ny.time() < time(10, 0):
    phase = "premarket"
elif ny.time() < time(10, 30):
    phase = "trade_window"
else:
    phase = "after_trade_window"

target = ny.replace(hour=10, minute=0, second=0, microsecond=0)
wait_seconds = max(0, int((target - ny).total_seconds()))

print(ny.strftime("%Y-%m-%d"))
print(ny.strftime("%H:%M:%S"))
print(ny.strftime("%Z"))
print(ny.weekday())
print(phase)
print(wait_seconds)
PY
)"

    local old_ifs="$IFS"
    IFS=$'\n'
    set -- $ny_output
    IFS="$old_ifs"

    NY_DATE="${1:-}"
    NY_TIME="${2:-}"
    NY_TZ="${3:-}"
    NY_WEEKDAY="${4:-}"
    NY_PHASE="${5:-}"
    NY_WAIT_SECONDS="${6:-0}"
}

fail() {
    local message="$1"
    local exit_code="${2:-1}"
    log "❌ ${message}"
    log "Log file: $LOG_FILE"
    exit "$exit_code"
}

trap cleanup EXIT

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    log "⏸️  Another PT.4.4g full daily scheduler instance is already running"
    log "Log file: $LOG_FILE"
    exit 0
fi

cd "$QUANT_LAB_DIR"

if [ -f ".env.godfather" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$QUANT_LAB_DIR/.env.godfather"
    set +a
fi

FEATURE_STATUS="not_started"
PRED_STATUS="not_started"
VALIDATION_STATUS="not_started"
PT44_STATUS="not_started"

log "========================================"
log "Godfather V9.0 - PT.4.4g Full Daily Scheduler"
log "Started: $(date)"
log "Run log: $LOG_FILE"
if [ "$FORCE_MODE" = "1" ]; then
    log "MANUAL_FORCE_MODE=1"
fi
log "========================================"
log ""

log "[Step 1/6] NY time check"
log "========================================"
load_ny_clock
log "Current time (NY): ${NY_DATE} ${NY_TIME} ${NY_TZ}"

if [ "$NY_WEEKDAY" -ge 5 ]; then
    if [ "$FORCE_MODE" = "1" ]; then
        log "⚠️  MANUAL_FORCE_MODE: bypassing weekend early skip"
    else
    log "⏸️  Skip: NY trading day check failed (weekend)"
    log "Final status: skipped"
    exit 0
    fi
fi

case "$NY_PHASE" in
    before_premarket)
        if [ "$FORCE_MODE" = "1" ]; then
            log "⚠️  MANUAL_FORCE_MODE: bypassing pre-market early skip"
        else
        log "⏸️  Skip: Too early for full pre-market scheduler"
        log "Final status: skipped"
        exit 0
        fi
        ;;
    after_trade_window)
        if [ "$FORCE_MODE" = "1" ]; then
            log "⚠️  MANUAL_FORCE_MODE: bypassing after-window early stop"
        else
        fail "Missed PT.4.4 launch window (after 10:30 ET)"
        fi
        ;;
    premarket)
        log "✅ NY pre-market window confirmed"
        ;;
    trade_window)
        log "⚠️  Already in PT.4.4 trade window; running full sequence immediately"
        ;;
esac

log ""
log "[Resolver] V9.0 data paths"
log "========================================"
log_runtime_paths

log ""
log "[Step 2/6] Refresh feature matrix"
log "========================================"
if python3 -u alpha_factory/run_feature_refresh.py 2>&1 | tee -a "$LOG_FILE"; then
    FEATURE_STATUS="success"
    log "✅ Feature refresh completed successfully"
else
    FEATURE_STATUS="failed"
    fail "Feature refresh failed"
fi

log ""
log "[Step 3/6] Generate fresh predictions"
log "========================================"
if python3 -u ml_lab/run_fresh_predictions.py 2>&1 | tee -a "$LOG_FILE"; then
    PRED_STATUS="success"
    log "✅ Fresh predictions generated successfully"
else
    PRED_STATUS="failed"
    fail "Fresh prediction generation failed"
fi

log ""
log "[Step 4/6] Validate feature / prediction / PT.4.4 read path"
log "========================================"
if python3 -u paper_trading/validate_pt44_full_daily_pipeline.py 2>&1 | tee -a "$LOG_FILE"; then
    VALIDATION_STATUS="success"
    log "✅ Full pipeline validation passed"
else
    VALIDATION_STATUS="failed"
    fail "Full pipeline validation failed"
fi

log ""
log "[Step 5/6] Launch PT.4.4 unified"
log "========================================"
load_ny_clock

if [ "$FORCE_MODE" = "0" ] && [ "$NY_PHASE" = "premarket" ] && [ "$NY_WAIT_SECONDS" -gt 0 ]; then
    log "Waiting ${NY_WAIT_SECONDS}s for PT.4.4 launch window (10:00 ET)"
    sleep "$NY_WAIT_SECONDS"
    sleep 3  # 3-second buffer to avoid 09:59:59 boundary
    load_ny_clock
    log "Current time (NY) after wait: ${NY_DATE} ${NY_TIME} ${NY_TZ}"
fi

if [ "$FORCE_MODE" = "1" ]; then
    log "⚠️  MANUAL_FORCE_MODE: running PT.4.4 unified immediately outside normal scheduler window if needed"
else
if [ "$NY_PHASE" = "after_trade_window" ]; then
    PT44_STATUS="failed"
    fail "Feature refresh + prediction finished too late; PT.4.4 launch window already closed"
fi

if [ "$NY_PHASE" != "trade_window" ]; then
    PT44_STATUS="failed"
    fail "NY time is not inside the PT.4.4 launch window"
fi
fi

if python3 -u paper_trading/run_pt44_unified.py 2>&1 | tee -a "$LOG_FILE"; then
    if [ "$FORCE_MODE" = "1" ] && [ "$NY_PHASE" != "trade_window" ]; then
        PT44_STATUS="manual_force_validation_completed"
        log "ℹ️  MANUAL_FORCE_MODE: PT.4.4 unified returned outside market window; downstream signal/target/delta reason is in Step 4 validation"
    else
        PT44_STATUS="success"
    fi
else
    PT44_STATUS="failed"
    fail "PT.4.4 unified execution failed"
fi

log ""
log "[Step 6/6] Final status"
log "========================================"
log "Feature refresh: $FEATURE_STATUS"
log "Prediction: $PRED_STATUS"
log "Validation: $VALIDATION_STATUS"
log "PT.4.4 unified: $PT44_STATUS"
log "Finished: $(date)"
log "Latest log link: $LATEST_LOG_LINK"
log "========================================"

exit 0
