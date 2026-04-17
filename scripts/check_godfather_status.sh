#!/bin/bash
cd ${GODFATHER_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}
python3 scripts/godfather_service_manager.py status
echo ""
echo "Dashboard HTTP Check:"
curl -s -o /dev/null -w "Port 8501: %{http_code}\n" http://localhost:8501 || echo "Port 8501: DOWN"
