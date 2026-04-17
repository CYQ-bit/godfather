"""
PT.4.2 Dry-run - Godfather V9.0
Demonstrate live tiny mode flow (without real broker)
"""
import json
import sys
from pathlib import Path
from datetime import datetime
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent.parent)))

sys.path.insert(0, str(Path(__file__).parent.parent))


def pt42_dry_run():
    """Demonstrate PT.4.2 live tiny mode flow"""

    print("=" * 80)
    print("【Godfather V9.0 - PT.4.2 Dry-run】")
    print("=" * 80)
    print()

    results = {
        'timestamp': datetime.now().isoformat(),
        'phase': 'PT.4.2',
        'mode': 'dry_run',
        'stages': []
    }

    # [1] Broker connection check
    print("[1] Checking broker connection...")
    try:
        from paper_trading.broker_connection import BrokerConnection

        broker = BrokerConnection('str(Path(__file__).resolve().parent.parent)/data/pt4_prep/broker_connection_config.json')

        connection_result = broker.connect()

        results['stages'].append({
            'stage': 'broker_connection',
            'status': 'CONNECTED' if connection_result else 'NOT_CONNECTED',
            'broker_status': broker.status.value
        })

        if connection_result:
            print(f"  ✅ Broker connected")
        else:
            print(f"  ⚠️  Broker not connected: {broker.status.value}")
            print(f"  Reason: Credentials not configured")

    except Exception as e:
        print(f"  ❌ Error: {e}")
        results['stages'].append({
            'stage': 'broker_connection',
            'status': 'ERROR',
            'error': str(e)
        })
    print()

    # [2] Live tiny mode executor
    print("[2] Testing live tiny mode executor...")
    try:
        from paper_trading.broker_connection import BrokerConnection
        from paper_trading.pre_trade_hard_gate import PreTradeHardGate
        from paper_trading.manual_review_checkpoints import ManualReviewCheckpoints
        from paper_trading.hard_stop_rules import HardStopRules
        from paper_trading.live_tiny_mode_executor import LiveTinyModeExecutor

        # Load tiny capital config
        with open('str(Path(__file__).resolve().parent.parent)/data/pt4_prep/tiny_capital_config.json', 'r') as f:
            tiny_config = json.load(f)

        # Initialize components
        broker = BrokerConnection('str(Path(__file__).resolve().parent.parent)/data/pt4_prep/broker_connection_config.json')
        gate = PreTradeHardGate('str(Path(__file__).resolve().parent.parent)/data/pt4_prep')
        review = ManualReviewCheckpoints('str(Path(__file__).resolve().parent.parent)/data/pt4_prep')
        hard_stop = HardStopRules()

        # Initialize executor
        executor = LiveTinyModeExecutor(
            broker_connection=broker,
            tiny_capital_config=tiny_config,
            pre_trade_gate=gate,
            manual_review=review,
            hard_stop_rules=hard_stop,
            output_dir='str(Path(__file__).resolve().parent.parent)/data/pt4_prep'
        )

        # Simulate tiny order
        test_orders = [
            {
                'symbol': 'AAPL',
                'side': 'BUY',
                'quantity': 5,
                'notional': 1000,
                'order_type': 'LIMIT',
                'tif': 'DAY',
                'limit_price': 200
            }
        ]

        # Execute dry-run
        run_report = executor.execute_live_tiny_run(
            date='2024-01-01',
            orders=test_orders,
            current_cash=5000,
            current_holdings={},
            portfolio_value=5000,
            market_data={'AAPL': {'close': 200}},
            tradable_symbols={'AAPL'}
        )

        results['stages'].append({
            'stage': 'live_tiny_executor',
            'status': run_report['final_status'],
            'stages_completed': len(run_report['stages'])
        })

        print(f"  Final status: {run_report['final_status']}")
        print(f"  Stages completed: {len(run_report['stages'])}")

    except Exception as e:
        print(f"  ❌ Error: {e}")
        results['stages'].append({
            'stage': 'live_tiny_executor',
            'status': 'ERROR',
            'error': str(e)
        })
    print()

    # Summary
    print("=" * 80)
    print("【PT.4.2 Dry-run Summary】")
    print("=" * 80)
    print()

    print("Key findings:")
    print()
    print("  1. Broker connection:")
    broker_stage = next((s for s in results['stages'] if s['stage'] == 'broker_connection'), None)
    if broker_stage:
        if broker_stage['status'] == 'CONNECTED':
            print(f"     ✅ Broker connected and ready")
        else:
            print(f"     ⚠️  Broker not connected: {broker_stage.get('broker_status', 'unknown')}")
            print(f"     Action required: Configure broker credentials")
    print()

    print("  2. Live tiny mode executor:")
    executor_stage = next((s for s in results['stages'] if s['stage'] == 'live_tiny_executor'), None)
    if executor_stage:
        print(f"     Status: {executor_stage['status']}")
        if executor_stage['status'] == 'BROKER_NOT_CONNECTED':
            print(f"     ⚠️  Cannot proceed without broker connection")
        elif executor_stage['status'] == 'AWAITING_REVIEW':
            print(f"     ⚠️  Manual review required before execution")
    print()

    print("  3. Next steps:")
    if broker_stage and broker_stage['status'] != 'CONNECTED':
        print(f"     → Configure real broker credentials")
        print(f"     → Update broker_connection_config.json")
        print(f"     → Set credentials_configured = true")
    else:
        print(f"     → Approve manual reviews")
        print(f"     → Execute live tiny orders")
        print(f"     → Monitor reconciliation")
    print()

    # Save results
    results_file = (_REPO_ROOT / 'data/pt4_prep/pt42_dry_run_results.json')
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"  Results saved: {results_file}")
    print()
    print("=" * 80)

    return results


if __name__ == '__main__':
    pt42_dry_run()
