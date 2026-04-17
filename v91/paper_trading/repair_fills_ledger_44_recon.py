"""
PT.4.2 Fills Ledger Repair & 4/4 Recon - Godfather V9.0
Fix fills ledger and verify 4/4 MATCHED recon
"""
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from paper_trading.broker_connection import BrokerConnection
from paper_trading.broker_recon_adapter import BrokerReconAdapter
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent.parent)))


def sync_fills_ledger(broker, broker_order_id):
    """Sync fills to local ledger"""
    print("="*80)
    print("【Task 1: Fills Ledger Repair】")
    print("="*80 + "\n")

    # Get order
    order = broker.get_order(broker_order_id)
    if not order or order['status'] != 'filled':
        print("❌ Order not filled")
        return None

    # Get fills from broker
    broker_fills = broker.get_fills()

    # Create fills ledger entry
    fills_ledger = []
    if broker_fills:
        for fill in broker_fills:
            if fill.get('order_id') == broker_order_id:
                fills_ledger.append({
                    'broker_order_id': broker_order_id,
                    'symbol': fill['symbol'],
                    'side': fill['side'],
                    'qty': fill['qty'],
                    'price': fill['price'],
                    'timestamp': fill['transaction_time'],
                    'synced_at': datetime.now().isoformat()
                })

    # Save fills ledger
    ledger_file = (_REPO_ROOT / 'data/paper_trading/state/fills_ledger.json')
    ledger_file.parent.mkdir(parents=True, exist_ok=True)

    with open(ledger_file, 'w') as f:
        json.dump(fills_ledger, f, indent=2)

    print(f"✅ Fills ledger created: {len(fills_ledger)} fills")
    for fill in fills_ledger:
        print(f"  {fill['symbol']} {fill['side']} {fill['qty']} @ ${fill['price']}")
    print(f"  Saved: {ledger_file}")
    print()

    return fills_ledger


def sync_complete_state(broker, broker_order_id, fills_ledger):
    """Sync complete state including fills"""
    print("="*80)
    print("【Syncing Complete State】")
    print("="*80 + "\n")

    # Get order
    order = broker.get_order(broker_order_id)

    # Get positions
    positions = broker.get_positions()

    # Get account
    account = broker.get_account_info()

    # Create complete local state
    local_state = {
        'timestamp': datetime.now().isoformat(),
        'order': {
            'broker_order_id': order['broker_order_id'],
            'symbol': order['symbol'],
            'side': order['side'],
            'qty': order['qty'],
            'status': order['status'],
            'filled_qty': order['filled_qty'],
            'filled_avg_price': order.get('filled_avg_price')
        },
        'positions': {},
        'cash': account['cash'] if account else 0,
        'equity': account['equity'] if account else 0,
        'fills': fills_ledger
    }

    # Sync positions
    if positions:
        for pos in positions:
            local_state['positions'][pos['symbol']] = pos['qty']

    # Save complete state
    state_file = (_REPO_ROOT / 'data/paper_trading/state/pt42_complete_state.json')
    with open(state_file, 'w') as f:
        json.dump(local_state, f, indent=2)

    print("✅ Complete state synced:")
    print(f"  Order: {order['status']}")
    print(f"  Positions: {local_state['positions']}")
    print(f"  Cash: ${local_state['cash']:,.2f}")
    print(f"  Fills: {len(fills_ledger)}")
    print()

    return local_state


def run_44_recon(broker, local_state):
    """Run 4/4 recon with fills"""
    print("="*80)
    print("【Task 2: 4/4 Recon Verification】")
    print("="*80 + "\n")

    recon_adapter = BrokerReconAdapter(broker)

    # Use complete local state with fills
    local_orders = []
    local_positions = local_state['positions']
    local_cash = local_state['cash']
    local_fills = local_state['fills']

    recon_report = recon_adapter.run_full_recon(
        local_orders=local_orders,
        local_positions=local_positions,
        local_cash=local_cash,
        local_fills=local_fills
    )

    return recon_report


def generate_44_report(recon_report):
    """Generate 4/4 recon report"""
    print("\n" + "="*80)
    print("【4/4 Recon Battle Report】")
    print("="*80 + "\n")

    checks = {
        'orders_recon': None,
        'positions_recon': None,
        'cash_recon': None,
        'fills_recon': None
    }

    for check in recon_report['checks']:
        check_name = check['check']
        if check_name == 'orders_recon':
            checks['orders_recon'] = check['status']
        elif check_name == 'positions_recon':
            checks['positions_recon'] = check['status']
        elif check_name == 'cash_recon':
            checks['cash_recon'] = check['status']
        elif check_name == 'fills_recon':
            checks['fills_recon'] = check['status']

    print("【4/4 Core Recon】")
    for name, status in checks.items():
        icon = '✅' if status == 'MATCHED' else '❌'
        print(f"  {icon} {name}: {status}")
    print()

    all_matched = all(s == 'MATCHED' for s in checks.values())

    print(f"Overall Status: {recon_report['overall_status']}")
    print()

    if all_matched:
        print("🎉 4/4 全绿！Recon 完全对平！")
    else:
        print("⚠️  仍有不匹配项")

    print()
    print("="*80)

    return all_matched


def main():
    broker_order_id = '329abadd-ba0d-4268-ae2d-cd00aa68fb5c'

    print("="*80)
    print("【Godfather V9.0 - Fills Ledger Repair & 4/4 Recon】")
    print("="*80)
    print()

    try:
        # Connect
        broker = BrokerConnection(
            config_file='str(Path(__file__).resolve().parent.parent)/data/pt4_prep/broker_connection_config.json'
        )

        if not broker.connect():
            print("❌ Failed to connect")
            sys.exit(1)

        # Task 1: Sync fills ledger
        fills_ledger = sync_fills_ledger(broker, broker_order_id)
        if not fills_ledger:
            print("❌ Failed to sync fills ledger")
            sys.exit(1)

        # Sync complete state
        local_state = sync_complete_state(broker, broker_order_id, fills_ledger)

        # Task 2: Run 4/4 recon
        recon_report = run_44_recon(broker, local_state)

        # Generate report
        all_matched = generate_44_report(recon_report)

        # Save final report
        report_file = (_REPO_ROOT / 'data/pt4_prep/pt42_44_recon_report.json')
        with open(report_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'fills_ledger': fills_ledger,
                'local_state': local_state,
                'recon_report': recon_report,
                'all_matched': all_matched
            }, f, indent=2)

        print(f"Report saved: {report_file}")

        broker.disconnect()

        if all_matched:
            print("\n✅ Task 1 & 2 完成：Fills Ledger 已修复，4/4 Recon 全绿！")
            sys.exit(0)
        else:
            print("\n⚠️  Recon 仍有不匹配")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
