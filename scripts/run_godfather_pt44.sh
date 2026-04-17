#!/bin/bash
# Godfather V9.0 - PT.4.4 compatibility wrapper

set -euo pipefail

exec /bin/bash ${GODFATHER_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}/scripts/run_godfather_pt44_daily.sh "$@"
