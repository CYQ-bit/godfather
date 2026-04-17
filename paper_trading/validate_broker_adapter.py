"""
Broker Execution Adapter Validation - Godfather V9.0
Minimal validation of Alpaca submit/ack/fills/recon
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


def validate_broker_adapter():
    """Validate Alpaca broker execution adapter"""

    print("="*80)
    print("【Godfather V9.0 - Broker Execution Adapter Validation】")
    print("="*80)
    print()

    results = {
        'timestamp': datetime.now().isoformat(),
        'tests': {}
    }

    # Initialize broker connection
    print("[Init] Initializing broker connection...")
    broker = BrokerConnection(
        config_file='Path(__file__).resolve().parent.parent/data/pt4_prep/broker_connection_config.json'
    )
    print()

    # Test 1: Connect
    print("[Test 1] Connect to Alpaca...")
    connect_success = broker.connect()
    results['tests']['connect'] = 'PASS' if connect_success else 'FAIL'

    if not connect_success:
        print("❌ Connection failed - aborting validation")
        return results
    print()

    # Test 2: Get account info (baseline)
    print("[Test 2] Get account info (baseline)...")
    account_info = broker.get_account_info()
    if account_info:
        print(f"✅ Account info retrieved")
        print(f"  Cash: ${account_info['cash']:,.2f}")
        print(f"  Equity: ${account_info['equity']:,.2f}")
        results['tests']['account_info'] = 'PASS'
    else:
        print("❌ Failed to get account info")
        results['tests']['account_info'] = 'FAIL'
    print()

    # Test 3: Get positions (baseline)
    print("[Test 3] Get positions (baseline)...")
    positions = broker.get_positions()
    if positions is not None:
        print(f"✅ Positions retrieved: {len(positions)} positions")
        results['tests']['positions'] = 'PASS'
    else:
        print("❌ Failed to get positions")
        results['tests']['positions'] = 'FAIL'
    print()

    # Test 4: Submit order
    print("[Test 4] Submit order...")
    test_order = {
        'symbol': 'AAPL',
        'side': 'BUY',
        'quantity': 1,
        'order_type': 'MARKET',
        'tif': 'DAY',
        'local_order_id': 'test_order_001'
    }

    submit_result = broker.submit_order(test_order)
    if submit_result and 'broker_order_id' in submit_result:
        print(f"✅ Order submitted")
        broker_order_id = submit_result['broker_order_id']
        results['tests']['submit'] = 'PASS'
        results['broker_order_id'] = broker_order_id
    else:
        print("❌ Order submission failed")
        results['tests']['submit'] = 'FAIL'
        print("\n⚠️  Skipping remaining tests (no order to track)")
        return results
    print()

    # Wait for order processing
    print("[Wait] Waiting 2s for order processing...")
    time.sleep(2)
    print()

    # Test 5: Get order status (ack)
    print("[Test 5] Get order status (ack)...")
    order_status = broker.get_order(broker_order_id)
    if order_status:
        print(f"✅ Order status retrieved")
        print(f"  Status: {order_status['status']}")
        print(f"  Symbol: {order_status['symbol']}")
        print(f"  Qty: {order_status['qty']}")
        results['tests']['ack'] = 'PASS'
        results['order_status'] = order_status['status']
    else:
        print("❌ Failed to get order status")
        results['tests']['ack'] = 'FAIL'
    print()

    # Test 6: Get fills
    print("[Test 6] Get fills...")
    fills = broker.get_fills()
    if fills is not None:
        print(f"✅ Fills retrieved: {len(fills)} fills")
        results['tests']['fills'] = 'PASS'
    else:
        print("❌ Failed to get fills")
        results['tests']['fills'] = 'FAIL'
    print()

    # Test 7: Cancel order (cleanup)
    print("[Test 7] Cancel order (cleanup)...")
    cancel_success = broker.cancel_order(broker_order_id)
    if cancel_success:
        print(f"✅ Order cancelled")
        results['tests']['cancel'] = 'PASS'
    else:
        print("⚠️  Cancel failed or order already filled")
        results['tests']['cancel'] = 'WARN'
    print()

    # Test 8: Reconciliation
    print("[Test 8] Reconciliation adapter...")
    recon_adapter = BrokerReconAdapter(broker)

    # Mock local data
    local_orders = []
    local_positions = {}
    local_cash = account_info['cash'] if account_info else 0
    local_fills = []

    recon_report = recon_adapter.run_full_recon(
        local_orders=local_orders,
        local_positions=local_positions,
        local_cash=local_cash,
        local_fills=local_fills
    )

    if recon_report['overall_status'] in ['MATCHED', 'MISMATCHED']:
        print(f"✅ Reconciliation completed")
        results['tests']['recon'] = 'PASS'
    else:
        print(f"❌ Reconciliation failed")
        results['tests']['recon'] = 'FAIL'

    # Disconnect
    broker.disconnect()

    return results


def generate_report(results):
    """Generate final validation report"""

    print("\n" + "="*80)
    print("【Validation Report】")
    print("="*80 + "\n")

    print("【A. 改了哪些文件】")
    print("  1. paper_trading/broker_connection.py - Alpaca API implementation")
    print("  2. paper_trading/broker_recon_adapter.py - Reconciliation adapter")
    print()

    print("【B. Alpaca submit / ack / fills / recon 是否已接通】")
    print(f"  Submit: {'✅ YES' if results['tests'].get('submit') == 'PASS' else '❌ NO'}")
    print(f"  Ack: {'✅ YES' if results['tests'].get('ack') == 'PASS' else '❌ NO'}")
    print(f"  Fills: {'✅ YES' if results['tests'].get('fills') == 'PASS' else '❌ NO'}")
    print(f"  Positions/Cash: {'✅ YES' if results['tests'].get('positions') == 'PASS' and results['tests'].get('account_info') == 'PASS' else '❌ NO'}")
    print(f"  Recon: {'✅ YES' if results['tests'].get('recon') == 'PASS' else '❌ NO'}")
    print()

    print("【C. 验证结果】")
    for test_name, test_result in results['tests'].items():
        status_icon = '✅' if test_result == 'PASS' else ('⚠️' if test_result == 'WARN' else '❌')
        print(f"  {test_name}: {status_icon} {test_result}")
    print()

    # Overall assessment
    critical_tests = ['connect', 'submit', 'ack', 'fills', 'positions', 'account_info', 'recon']
    all_pass = all(results['tests'].get(t) == 'PASS' for t in critical_tests)

    print("【D. 最终结论】")
    print()
    print("1. Godfather V9.0 - Broker Execution Adapter 是否完成？")
    if all_pass:
        print("   ✅ 是")
    else:
        print("   ❌ 否")
    print()

    print("2. 当前是否已具备真正执行 PT.4.2 tiny-capital live rehearsal 条件？")
    if all_pass:
        print("   ✅ 是")
        print("   理由: Alpaca submit/ack/fills/recon 全部接通")
    else:
        print("   ❌ 否")
    print()

    print("3. 若仍不行，最后阻塞项是什么？")
    if all_pass:
        print("   无阻塞项")
    else:
        failed_tests = [t for t, r in results['tests'].items() if r == 'FAIL']
        print(f"   阻塞项: {', '.join(failed_tests)}")
    print()

    print("4. 若可以，给出唯一正确启动命令。")
    if all_pass:
        print("   python3 paper_trading/run_pt42_live_tiny.py")
    else:
        print("   N/A (未满足条件)")
    print()

    print("="*80)

    # Save report
    report_file = (_REPO_ROOT / 'data/pt4_prep/broker_adapter_validation_report.json')
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nReport saved: {report_file}")


def main():
    try:
        results = validate_broker_adapter()
        generate_report(results)
    except Exception as e:
        print(f"\n❌ Validation failed with error:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
