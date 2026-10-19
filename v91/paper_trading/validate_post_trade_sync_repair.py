"""
Validate broker -> local drift repair and self-heal behavior for Godfather V9.1 Sandbox.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
import os

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent.parent)))

from paper_trading.broker_connection import BrokerConnection
from paper_trading.broker_local_sync import (
    STATE_FILE,
    FILLS_LEDGER_FILE,
    load_combined_local_state,
    sync_local_state_from_broker,
    run_broker_local_recon,
    critical_recon_ok,
)

VALIDATION_SUMMARY_FILE = (_REPO_ROOT / 'data/paper_trading/state/last_post_trade_sync_validation.json')


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with open(temp_path, "w") as handle:
        json.dump(payload, handle, indent=2)
    temp_path.replace(path)


def _summary(label: str, state: dict) -> None:
    print(f"{label}_CASH={state.get('cash')}")
    print(f"{label}_POSITIONS={len(state.get('positions', {}))}")
    print(f"{label}_FILLS={len(state.get('fills', []))}")


def _print_recon(label: str, recon_report: dict) -> None:
    checks = {check["check"]: check["status"] for check in recon_report.get("checks", [])}
    print(f"{label}_OVERALL={recon_report.get('overall_status')}")
    print(f"{label}_ORDERS={checks.get('orders_recon')}")
    print(f"{label}_POSITIONS={checks.get('positions_recon')}")
    print(f"{label}_CASH={checks.get('cash_recon')}")
    print(f"{label}_FILLS={checks.get('fills_recon')}")


def _recon_checks(recon_report: dict) -> dict:
    return {check["check"]: check["status"] for check in recon_report.get("checks", [])}


def main() -> int:
    print("POST_TRADE_SYNC_VALIDATION_START")

    broker = BrokerConnection(config_file="str(Path(__file__).resolve().parent.parent)/data/pt4_prep/broker_connection_config.json")
    if not broker.connect():
        print("BROKER_CONNECT=FAILED")
        return 1

    try:
        before_state = load_combined_local_state()
        before_recon = run_broker_local_recon(broker)
        _summary("BEFORE", before_state)
        _print_recon("BEFORE_RECON", before_recon)

        real_repair_report = sync_local_state_from_broker(broker, reason="manual_drift_repair_validation")
        repaired_state = load_combined_local_state()
        repaired_recon = run_broker_local_recon(broker)

        print(f"REAL_REPAIR_FILLS_ADDED={real_repair_report['fills_added']}")
        _summary("AFTER_REAL_REPAIR", repaired_state)
        _print_recon("AFTER_REAL_REPAIR_RECON", repaired_recon)

        tampered_state = deepcopy(repaired_state)
        tampered_positions = deepcopy(tampered_state.get("positions", {}))
        if tampered_positions:
            first_symbol = sorted(tampered_positions)[0]
            tampered_positions.pop(first_symbol, None)
        tampered_state["positions"] = tampered_positions
        tampered_state["cash"] = float(tampered_state.get("cash", 0.0)) + 123.45

        tampered_fills = deepcopy(repaired_state.get("fills", []))
        if len(tampered_fills) > 1:
            tampered_fills = tampered_fills[:-2]
        elif tampered_fills:
            tampered_fills = tampered_fills[:1]

        tampered_state["fills"] = tampered_fills
        _write_json(STATE_FILE, tampered_state)
        _write_json(FILLS_LEDGER_FILE, tampered_fills)

        tampered_recon = run_broker_local_recon(broker)
        _summary("SIMULATED_DRIFT", tampered_state)
        _print_recon("SIMULATED_DRIFT_RECON", tampered_recon)

        simulated_repair_report = sync_local_state_from_broker(broker, reason="simulated_drift_auto_repair")
        healed_state = load_combined_local_state()
        healed_recon = run_broker_local_recon(broker)

        print(f"SIMULATED_REPAIR_FILLS_ADDED={simulated_repair_report['fills_added']}")
        _summary("AFTER_SIMULATED_REPAIR", healed_state)
        _print_recon("AFTER_SIMULATED_REPAIR_RECON", healed_recon)

        success = (
            critical_recon_ok(repaired_recon)
            and critical_recon_ok(healed_recon)
            and healed_recon.get("overall_status") == "MATCHED"
        )

        auto_repair_value = "YES" if success else "NO"
        validation_value = "POST_TRADE_SYNC_VALIDATION_OK" if success else "POST_TRADE_SYNC_VALIDATION_FAILED"

        print(f"AUTO_REPAIR_SUCCESS={auto_repair_value}")
        print(validation_value)

        _write_json(
            VALIDATION_SUMMARY_FILE,
            {
                "timestamp": __import__("datetime").datetime.now().isoformat(),
                "auto_repair_success": auto_repair_value,
                "post_trade_sync_validation": "OK" if success else "FAILED",
                "current_recon": {
                    "overall": healed_recon.get("overall_status"),
                    **_recon_checks(healed_recon),
                },
                "real_repair_fills_added": real_repair_report["fills_added"],
                "simulated_repair_fills_added": simulated_repair_report["fills_added"],
                "before_recon": {
                    "overall": before_recon.get("overall_status"),
                    **_recon_checks(before_recon),
                },
                "simulated_drift_recon": {
                    "overall": tampered_recon.get("overall_status"),
                    **_recon_checks(tampered_recon),
                },
            },
        )
        return 0 if success else 1

    finally:
        # If any validation step exits early, try to keep local files aligned with broker truth.
        try:
            sync_local_state_from_broker(broker, reason="validation_final_resync")
        except Exception:
            pass
        broker.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
