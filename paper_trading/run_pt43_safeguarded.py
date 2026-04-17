"""
PT.4.3 Continuous Tiny Paper with Safeguards - Godfather V9.0
Time zone correction + Idempotency + Pre-market recon
"""
import json
import sys
from pathlib import Path
from datetime import datetime, time
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

from paper_trading.broker_connection import BrokerConnection
from paper_trading.broker_recon_adapter import BrokerReconAdapter
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))


def get_ny_time():
    """Get current time in America/New_York"""
    return datetime.now(ZoneInfo('America/New_York'))


def is_market_open():
    """Check if market is open"""
    ny_time = get_ny_time()

    # Check if weekday (Mon-Fri)
    if ny_time.weekday() >= 5:
        return False, "Weekend"

    # Market hours: 9:30 AM - 4:00 PM ET
    market_open = time(9, 30)
    market_close = time(16, 0)
    current_time = ny_time.time()

    if current_time < market_open:
        return False, f"Before market open (opens at 9:30 AM ET)"
    elif current_time >= market_close:
        return False, f"After market close (closed at 4:00 PM ET)"

    return True, "Market open"


def get_next_valid_run_time():
    """Calculate next valid run time"""
    ny_time = get_ny_time()

    # If weekend, next Monday 9:30 AM
    if ny_time.weekday() >= 5:
        days_until_monday = (7 - ny_time.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 1
        next_run = ny_time.replace(hour=9, minute=30, second=0, microsecond=0)
        next_run = next_run.replace(day=ny_time.day + days_until_monday)
        return next_run.isoformat()

    # If before market open, today 9:30 AM
    if ny_time.time() < time(9, 30):
        next_run = ny_time.replace(hour=9, minute=30, second=0, microsecond=0)
        return next_run.isoformat()

    # If after market close, next day 9:30 AM
    if ny_time.time() >= time(16, 0):
        next_run = ny_time.replace(hour=9, minute=30, second=0, microsecond=0)
        next_run = next_run.replace(day=ny_time.day + 1)
        return next_run.isoformat()

    # Currently in market hours
    return "Now"


def check_idempotency(trading_date):
    """Check if already ran today"""
    print("="*80)
    print("【Idempotency Check】")
    print("="*80 + "\n")

    run_log_file = (_REPO_ROOT / 'data/paper_trading/state/daily_run_log.json')

    if not run_log_file.exists():
        print("✅ No previous runs")
        return True, None

    with open(run_log_file, 'r') as f:
        run_log = json.load(f)

    if trading_date in run_log:
        print(f"❌ Already ran on {trading_date}")
        print(f"  Run ID: {run_log[trading_date].get('run_id')}")
        print(f"  Status: {run_log[trading_date].get('status')}")
        return False, run_log[trading_date]

    print(f"✅ No run for {trading_date}")
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


def pre_market_recon(broker):
    """Run pre-market reconciliation"""
    print("="*80)
    print("【Pre-Market Recon】")
    print("="*80 + "\n")

    # Pull broker state
    print("[1/4] Pulling broker account...")
    account = broker.get_account_info()
    if not account:
        print("❌ Failed to get account")
        return False, None
    print(f"  Cash: ${account['cash']:,.2f}")
    print(f"  Equity: ${account['equity']:,.2f}")

    print("\n[2/4] Pulling broker positions...")
    positions = broker.get_positions()
    print(f"  Positions: {len(positions) if positions else 0}")
    if positions:
        for pos in positions:
            print(f"    {pos['symbol']}: {pos['qty']}")

    print("\n[3/4] Pulling open orders...")
    open_orders = broker.list_open_orders()
    print(f"  Open orders: {len(open_orders) if open_orders else 0}")
    if open_orders and len(open_orders) > 0:
        print("  ⚠️  Warning: Open orders exist")
        for order in open_orders:
            print(f"    {order['symbol']} {order['side']} {order['qty']}")

    print("\n[4/4] Running recon...")

    # Load local state
    state_file = (_REPO_ROOT / 'data/paper_trading/state/pt42_complete_state.json')
    if not state_file.exists():
        print("  ⚠️  No local state, initializing...")
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
        print("\n✅ Pre-market recon: PASS")
    else:
        print(f"\n❌ Pre-market recon: {recon_report['overall_status']}")

    print()

    return recon_ok, recon_report


def main():
    """Main PT.4.3 entry with safeguards"""
    print("="*80)
    print("【Godfather V9.0 - PT.4.3 Continuous Tiny Paper (Safeguarded)】")
    print("="*80)
    print()

    # [1] Time zone correction
    ny_time = get_ny_time()
    print(f"Current time (NY): {ny_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Trading date: {ny_time.strftime('%Y-%m-%d')}")
    print()

    market_open, reason = is_market_open()
    print(f"Market status: {reason}")

    if not market_open:
        next_run = get_next_valid_run_time()
        print(f"Next valid run: {next_run}")
        print("\n⏸️  Skipping - market not open")
        sys.exit(0)

    print("✅ Market is open")
    print()

    trading_date = ny_time.strftime('%Y-%m-%d')

    # [2] Idempotency check
    can_run, prev_run = check_idempotency(trading_date)

    if not can_run:
        print("\n⏸️  Skipping - already ran today")
        sys.exit(0)

    # Connect to broker
    print("="*80)
    print("【Broker Connection】")
    print("="*80 + "\n")

    broker = BrokerConnection(
        config_file='Path(__file__).resolve().parent.parent/data/pt4_prep/broker_connection_config.json'
    )

    if not broker.connect():
        print("❌ Connection failed")
        sys.exit(1)

    print("✅ Connected")
    print()

    # [3] Pre-market recon
    recon_ok, recon_report = pre_market_recon(broker)

    if not recon_ok:
        print("❌ Pre-market recon failed - aborting")
        broker.disconnect()
        sys.exit(1)

    # Record run
    run_id = f"pt43_{trading_date}_{ny_time.strftime('%H%M%S')}"
    record_run(trading_date, run_id, 'completed')

    print("="*80)
    print("【Trading Phase】")
    print("="*80)
    print()
    print("ℹ️  No orders today (strategy integration pending)")
    print()

    broker.disconnect()

    print("="*80)
    print(f"✅ PT.4.3 Daily cycle completed: {run_id}")
    print("="*80)


if __name__ == '__main__':
    main()
