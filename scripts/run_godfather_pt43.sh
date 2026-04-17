#!/bin/bash
# Godfather V9.0 - PT.4.3 Wrapper Script

set -e

# Working directory
QUANT_LAB_DIR="${GODFATHER_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$QUANT_LAB_DIR"

# Load environment variables if exists
if [ -f ".env.godfather" ]; then
    export $(cat .env.godfather | grep -v '^#' | xargs)
fi

# Create logs directory
mkdir -p logs

# Log file
LOG_FILE="logs/pt43_scheduler_$(date +%Y%m%d_%H%M%S).log"

echo "========================================" | tee -a "$LOG_FILE"
echo "Godfather V9.0 - PT.4.3 Wrapper" | tee -a "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Run scheduler guard
python3 paper_trading/run_pt43_scheduler_guard.py 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "Finished: $(date)" | tee -a "$LOG_FILE"
echo "Exit code: $EXIT_CODE" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

exit $EXIT_CODE
