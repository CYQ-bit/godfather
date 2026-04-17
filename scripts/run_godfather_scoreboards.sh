#!/bin/bash
# Godfather Scoreboard Automation

set -euo pipefail

QUANT_LAB_DIR="${GODFATHER_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
LOG_DIR="$QUANT_LAB_DIR/logs/scoreboards"
mkdir -p "$LOG_DIR"

RUN_STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/scoreboards_${RUN_STAMP}.log"
LATEST_LOG="$LOG_DIR/scoreboards_latest.log"

exec > >(tee "$LOG_FILE") 2>&1

echo "========================================"
echo "Godfather Scoreboard Automation"
echo "Started: $(date)"
echo "Run log: $LOG_FILE"
echo "========================================"

cd "$QUANT_LAB_DIR"

if [ -f ".env.godfather" ]; then
    . "$QUANT_LAB_DIR/.env.godfather"
fi

python3 "$QUANT_LAB_DIR/control_center/generate_scoreboards.py" "$@"

cp "$LOG_FILE" "$LATEST_LOG"

echo "========================================"
echo "Finished: $(date)"
echo "Latest log: $LATEST_LOG"
echo "========================================"
