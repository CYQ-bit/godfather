#!/bin/bash
# Godfather V9.0 - PT.4.4e Daily Scheduler
# Single entry for pre-market predictions -> PT.4.4 unified execution

set -euo pipefail

QUANT_LAB_DIR="${GODFATHER_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
LOG_DIR="$QUANT_LAB_DIR/logs"
LOCK_DIR="$LOG_DIR/pt44e_daily.lock"
RUN_STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/pt44e_daily_${RUN_STAMP}.log"
LATEST_LOG_LINK="$LOG_DIR/pt44e_daily_latest.log"

mkdir -p "$LOG_DIR"
touch "$LOG_FILE"
ln -sfn "$(basename "$LOG_FILE")" "$LATEST_LOG_LINK"

log() {
    printf '%s\n' "$1" | tee -a "$LOG_FILE"
}

cleanup() {
    rm -rf "$LOCK_DIR"
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
    log "⏸️  Another PT.4.4e daily scheduler instance is already running"
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

PRED_STATUS="not_started"
VALIDATION_STATUS="not_started"
PT44_STATUS="not_started"

log "========================================"
log "Godfather V9.0 - PT.4.4e Daily Scheduler"
log "Started: $(date)"
log "Run log: $LOG_FILE"
log "========================================"
log ""

log "[Step 1/5] NY time check"
log "========================================"
load_ny_clock
log "Current time (NY): ${NY_DATE} ${NY_TIME} ${NY_TZ}"

if [ "$NY_WEEKDAY" -ge 5 ]; then
    log "⏸️  Skip: NY trading day check failed (weekend)"
    log "Final status: skipped"
    exit 0
fi

case "$NY_PHASE" in
    before_premarket)
        log "⏸️  Skip: Too early for pre-market prediction run"
        log "Final status: skipped"
        exit 0
        ;;
    after_trade_window)
        fail "Missed PT.4.4 launch window (after 10:30 ET)"
        ;;
    premarket)
        log "✅ NY pre-market window confirmed"
        ;;
    trade_window)
        log "⚠️  Already in PT.4.4 trade window; running full sequence immediately"
        ;;
esac

log ""
log "[Step 2/5] Generate fresh predictions"
log "========================================"
if python3 -u ml_lab/run_fresh_predictions.py 2>&1 | tee -a "$LOG_FILE"; then
    PRED_STATUS="success"
    log "✅ Fresh predictions generated successfully"
else
    PRED_STATUS="failed"
    fail "Fresh prediction generation failed"
fi

log ""
log "[Step 3/5] Validate fresh prediction + PT.4.4 read path"
log "========================================"
if python3 -u paper_trading/validate_pt44_prediction_pipeline.py 2>&1 | tee -a "$LOG_FILE"; then
    VALIDATION_STATUS="success"
    log "✅ Prediction validation passed"
else
    VALIDATION_STATUS="failed"
    fail "Prediction validation failed"
fi

log ""
log "[Step 4/5] Launch PT.4.4 unified"
log "========================================"
load_ny_clock

if [ "$NY_PHASE" = "premarket" ] && [ "$NY_WAIT_SECONDS" -gt 0 ]; then
    log "Waiting ${NY_WAIT_SECONDS}s for PT.4.4 launch window (10:00 ET)"
    sleep "$NY_WAIT_SECONDS"
    load_ny_clock
    log "Current time (NY) after wait: ${NY_DATE} ${NY_TIME} ${NY_TZ}"
fi

if [ "$NY_PHASE" = "after_trade_window" ]; then
    PT44_STATUS="failed"
    fail "Prediction finished too late; PT.4.4 launch window already closed"
fi

if [ "$NY_PHASE" != "trade_window" ]; then
    PT44_STATUS="failed"
    fail "NY time is not inside the PT.4.4 launch window"
fi

if python3 -u paper_trading/run_pt44_unified.py 2>&1 | tee -a "$LOG_FILE"; then
    PT44_STATUS="success"
else
    PT44_STATUS="failed"
    fail "PT.4.4 unified execution failed"
fi

log ""
log "[Step 5/5] Final status"
log "========================================"
log "Prediction: $PRED_STATUS"
log "Validation: $VALIDATION_STATUS"
log "PT.4.4 unified: $PT44_STATUS"
log "Finished: $(date)"
log "Latest log link: $LATEST_LOG_LINK"
log "========================================"

exit 0
