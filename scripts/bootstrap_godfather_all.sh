#!/bin/bash
cd ${GODFATHER_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}
python3 scripts/godfather_service_manager.py sync
python3 scripts/godfather_service_manager.py bootstrap
