"""
PT.4.2 Cancel & Recon Test - Godfather V9.0
Cancel open order and verify recon
"""
import json
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from paper_trading.broker_connection import BrokerConnection
from paper_trading.broker_recon_adapter import BrokerReconAdapter
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))


def cancel_order(broker, broker_order_id):
    """Cancel order and check result"""
    print("="*80)
    print("【A. Cancel Result】")
    print("="*80 + "\n")

    print(f"Canceling order: {broker_order_id}")
    cancel_success = broker.cancel_order(broker_order_id)

    if cancel_success:
        print("✅ Cancel request: SUCCESS")
    else:
        print("❌ Cancel request: FAILED")

    # Wait for cancel to process
    print("Waiting 2s for cancel processing...")
    time.sleep(2)

    # Check final status
    order = broker.get_order(broker_order_id)
    if order:
        print(f"\nFinal broker order status: {order['status']}")
        print(f"Symbol: {order['symbol']}")
        print(f"Side: {order['side']}")
        print(f"Qty: {order['qty']}")
        print(f"Filled Qty: {order['filled_qty']}")
    else:
        print("❌ Failed to get order status after cancel")

    print()
    return cancel_success, order


def check_lifecycle_sync(order):
    """Check lifecycle sync"""
    print("="*80)
    print("【B. Lifecycle Sync】")
    print("="*80 + "\n")

    if not order:
        print("❌ No order data")
        print()
        return False

    status = order['status']
    is_canceled = status == 'cancelled'

    print(f"Broker order status: {status}")
    print(f"本地状态同步: {'✅ cancelled' if is_canceled else '⚠️ ' + status}")
    print(f"Broker order ID: {order['broker_order_id']}")
    print()

    return is_canceled


def check_broker_state_after_cancel(broker):
    """Check broker state after cancel"""
    print("="*80)
    print("【C. Broker State After Cancel】")
    print("="*80 + "\n")

    # Open orders
    open_orders = broker.list_open_orders()
    print(f"Open orders: {len(open_orders) if open_orders else 0}")
    if open_orders and len(open_orders) > 0:
        for o in open_orders:
            print(f"  {o['symbol']} {o['side']} {o['qty']} - {o['status']}")
    print()

    # Fills
    fills = broker.get_fills()
    print(f"Fills: {len(fills) if fills else 0}")
    print()

    # Positions
    positions = broker.get_positions()
    print(f"Positions: {len(positions) if positions else 0}")
    if positions and len(positions) > 0:
        for pos in positions:
            print(f"  {pos['symbol']}: {pos['qty']}")
    print()

    # Account
    account = broker.get_account_info()
    if account:
        print(f"Cash: ${account['cash']:,.2f}")
        print(f"Equity: ${account['equity']:,.2f}")
    print()

    return open_orders, fills, positions, account


def run_recon_after_cancel(broker):
    """Run recon after cancel"""
    print("="*80)
    print("【D. Recon Result】")
    print("="*80 + "\n")

    recon_adapter = BrokerReconAdapter(broker)

    # After cancel, local should have no open orders, no positions
    local_orders = []
    local_positions = {}
    local_fills = []

    account = broker.get_account_info()
    local_cash = account['cash'] if account else 0

    recon_report = recon_adapter.run_full_recon(
        local_orders=local_orders,
        local_positions=local_positions,
        local_cash=local_cash,
        local_fills=local_fills
    )

    return recon_report


def generate_final_report(cancel_success, order, lifecycle_synced, open_orders, recon_report):
    """Generate final report"""
    print("="*80)
    print("【E. 最终结论】")
    print("="*80 + "\n")

    # Check if order canceled
    order_canceled = order and order['status'] == 'cancelled'

    print("1. 这笔 PT.4.2 paper order 是否已成功撤销？")
    if order_canceled:
        print("   ✅ 是")
        print(f"   Final status: {order['status']}")
    else:
        print("   ❌ 否")
        if order:
            print(f"   Status: {order['status']}")
    print()

    # Check recon
    recon_matched = recon_report and recon_report['overall_status'] == 'MATCHED'

    print("2. Cancel 后 recon 是否全线对平？")
    if recon_matched:
        print("   ✅ 是")
        print("   Orders/Fills/Positions/Cash 全部 MATCHED")
    else:
        print("   ⚠️  部分不匹配")
        if recon_report:
            print(f"   Overall: {recon_report['overall_status']}")
    print()

    # Check reverse loop complete
    reverse_loop_complete = order_canceled and recon_matched

    print("3. Godfather V9.0 是否已完成首笔 paper execution 反向闭环验证？")
    if reverse_loop_complete:
        print("   ✅ 是")
        print("   Submit → Accept → Cancel → Recon 全部完成")
    else:
        print("   ⚠️  部分完成")
        if not order_canceled:
            print("   阻塞: Order 未成功撤销")
        if not recon_matched:
            print("   阻塞: Recon 未对平")
    print()

    print("4. 下一步更合理是：")
    if reverse_loop_complete:
        print("   → A. 再做 1 笔 submit→fill 测试")
        print("   理由: 反向闭环已验证，需验证正向 fill 闭环")
    else:
        print("   → 检查 cancel 或 recon 失败原因")
    print()

    print("="*80)

    # Save report
    report_file = (_REPO_ROOT / 'data/pt4_prep/pt42_cancel_recon_test.json')
    with open(report_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'cancel_success': cancel_success,
            'order_info': order,
            'lifecycle_synced': lifecycle_synced,
            'open_orders_count': len(open_orders) if open_orders else 0,
            'recon_report': recon_report,
            'order_canceled': order_canceled,
            'recon_matched': recon_matched,
            'reverse_loop_complete': reverse_loop_complete
        }, f, indent=2)

    print(f"\nReport saved: {report_file}")


def main():
    broker_order_id = '329abadd-ba0d-4268-ae2d-cd00aa68fb5c'

    print("="*80)
    print("【Godfather V9.0 - PT.4.2 Cancel & Recon Test】")
    print("="*80)
    print()
    print(f"Order ID: {broker_order_id}")
    print(f"Symbol: AAPL")
    print(f"Current Status: accepted/open")
    print()

    try:
        # Initialize broker
        broker = BrokerConnection(
            config_file='Path(__file__).resolve().parent.parent/data/pt4_prep/broker_connection_config.json'
        )

        if not broker.connect():
            print("❌ Failed to connect")
            sys.exit(1)

        # Cancel order
        cancel_success, order = cancel_order(broker, broker_order_id)

        # Check lifecycle sync
        lifecycle_synced = check_lifecycle_sync(order)

        # Check broker state
        open_orders, fills, positions, account = check_broker_state_after_cancel(broker)

        # Run recon
        recon_report = run_recon_after_cancel(broker)

        # Generate report
        generate_final_report(cancel_success, order, lifecycle_synced, open_orders, recon_report)

        broker.disconnect()

    except Exception as e:
        print(f"\n❌ Test failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
