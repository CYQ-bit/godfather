"""
PT.4.3 Safeguarded with Rich UI & Telegram - Godfather V9.0
Enhanced version with command center UI and daily reports
"""
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

from paper_trading.broker_connection import BrokerConnection
from paper_trading.broker_recon_adapter import BrokerReconAdapter
from paper_trading.ui_console import UIConsole
from paper_trading.telegram_reporter import TelegramReporter
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))


def get_ny_time():
    """Get current time in America/New_York"""
    return datetime.now(ZoneInfo('America/New_York'))


def is_market_open():
    """Check if market is open"""
    ny_time = get_ny_time()

    if ny_time.weekday() >= 5:
        return False, "Weekend"

    from datetime import time
    market_open = time(9, 30)
    market_close = time(16, 0)
    current_time = ny_time.time()

    if current_time < market_open:
        return False, f"Before market open"
    elif current_time >= market_close:
        return False, f"After market close"

    return True, "Market open"


def check_idempotency(trading_date):
    """Check if already ran today"""
    run_log_file = (_REPO_ROOT / 'data/paper_trading/state/daily_run_log.json')

    if not run_log_file.exists():
        return True, None

    with open(run_log_file, 'r') as f:
        run_log = json.load(f)

    if trading_date in run_log:
        return False, run_log[trading_date]

    return True, None


def record_run(trading_date, run_id, status):
    """Record today's run"""
    run_log_file = (_REPO_ROOT / 'data/paper_trading/state/daily_run_log.json')
    run_log_file.parent.mkdir(parents=True, exist_ok=True)

    run_log = {}
    if run_log_file.exists():
        with open(run_log_file, 'r') as f:
            run_log = json.load(f)

    run_log[trading_date] = {
        'run_id': run_id,
        'status': status,
        'timestamp': datetime.now().isoformat()
    }

    with open(run_log_file, 'w') as f:
        json.dump(run_log, f, indent=2)


def pre_market_recon(broker, ui):
    """Run pre-market reconciliation"""
    ui.section("Pre-Market Recon")

    # Pull broker state
    account = broker.get_account_info()
    if not account:
        ui.alert_panel("Failed to get account", "error")
        return False, None

    positions = broker.get_positions()
    open_orders = broker.list_open_orders()

    ui.status_table({
        'Cash': f"${account['cash']:,.2f}",
        'Equity': f"${account['equity']:,.2f}",
        'Positions': len(positions) if positions else 0,
        'Open Orders': len(open_orders) if open_orders else 0
    }, "Broker State")

    # Load local state
    state_file = (_REPO_ROOT / 'data/paper_trading/state/pt42_complete_state.json')
    if not state_file.exists():
        local_positions = {}
        local_cash = account['cash']
        local_fills = []
    else:
        with open(state_file, 'r') as f:
            local_state = json.load(f)
        local_positions = local_state.get('positions', {})
        local_cash = local_state.get('cash', 0)
        local_fills = local_state.get('fills', [])

    recon_adapter = BrokerReconAdapter(broker)
    recon_report = recon_adapter.run_full_recon(
        local_orders=[],
        local_positions=local_positions,
        local_cash=local_cash,
        local_fills=local_fills
    )

    recon_ok = recon_report['overall_status'] == 'MATCHED'

    if recon_ok:
        ui.alert_panel("Pre-market recon: PASS", "success")
    else:
        ui.alert_panel(f"Pre-market recon: {recon_report['overall_status']}", "error")

    return recon_ok, recon_report, account


def main():
    """Main PT.4.3 entry with Rich UI"""
    ui = UIConsole()
    telegram = TelegramReporter()

    ui.banner()

    # Time zone check
    ui.section("Time Zone & Market Status")
    ny_time = get_ny_time()
    trading_date = ny_time.strftime('%Y-%m-%d')

    ui.status_table({
        'Current Time (NY)': ny_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
        'Trading Date': trading_date
    })

    market_open, reason = is_market_open()
    ui.print(f"Market status: {reason}", "cyan")

    if not market_open:
        ui.alert_panel("Market not open - skipping", "warning")
        sys.exit(0)

    # Idempotency check
    ui.section("Idempotency Check")
    can_run, prev_run = check_idempotency(trading_date)

    if not can_run:
        ui.alert_panel(f"Already ran today: {prev_run.get('run_id')}", "warning")
        sys.exit(0)

    ui.alert_panel("No previous run today", "success")

    # Connect to broker
    ui.section("Broker Connection")
    broker = BrokerConnection(
        config_file='Path(__file__).resolve().parent.parent/data/pt4_prep/broker_connection_config.json'
    )

    if not broker.connect():
        ui.alert_panel("Connection failed", "error")
        sys.exit(1)

    ui.alert_panel("Connected to Alpaca", "success")

    # Pre-market recon
    recon_ok, recon_report, account = pre_market_recon(broker, ui)

    if not recon_ok:
        ui.alert_panel("Pre-market recon failed - aborting", "error")
        broker.disconnect()
        sys.exit(1)

    # Record run
    run_id = f"pt43_{trading_date}_{ny_time.strftime('%H%M%S')}"
    record_run(trading_date, run_id, 'completed')

    # Trading phase
    ui.section("Trading Phase")
    ui.print("ℹ️  No orders today (strategy integration pending)", "dim")

    broker.disconnect()

    # Final summary
    ui.final_summary(
        run_id=run_id,
        status='COMPLETED',
        recon=recon_report
    )

    # Send Telegram report
    telegram.send_daily_report(
        run_id=run_id,
        status='COMPLETED',
        recon_report=recon_report,
        account_info=account,
        orders_count=0
    )

    ui.alert_panel(f"Daily cycle completed: {run_id}", "success")


if __name__ == '__main__':
    main()
