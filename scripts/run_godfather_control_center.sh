#!/bin/bash
# Godfather Control Center - local Streamlit dashboard

set -euo pipefail

exec python3 -m streamlit run \
  ${GODFATHER_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}/control_center/app.py \
  --server.headless true \
  --server.address 127.0.0.1 \
  --server.port 8501
