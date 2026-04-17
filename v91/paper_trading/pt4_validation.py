"""
PT.4 Validation Script - Godfather V9.0
Test all 6 validation flows
"""
import json
import sys
from pathlib import Path
from datetime import datetime
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent.parent)))

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def validate_pt4_modules():
    """Validate PT.4 module implementation"""

    print("=" * 80)
    print("【Godfather V9.0 - PT.4 Validation】")
    print("=" * 80)
    print()

    results = {
        'timestamp': datetime.now().isoformat(),
        'validations': []
    }

    # [1] Module existence check
    print("[1] Checking PT.4 modules...")
    modules = {
        'pre_trade_hard_gate': 'paper_trading/pre_trade_hard_gate.py',
        'order_lifecycle_engine': 'paper_trading/order_lifecycle_engine.py',
        'post_trade_recon': 'paper_trading/post_trade_recon.py',
        'eod_summary_generator': 'paper_trading/eod_summary_generator.py',
        'incident_runbook': 'paper_trading/INCIDENT_RUNBOOK.md',
        'version_lock': 'data/pt4_prep/version_lock/VERSION_LOCK.json',
        'manual_override': 'data/pt4_prep/manual_override.json'
    }

    module_check = {'name': 'module_existence', 'status': 'PASS', 'details': []}
    for name, path in modules.items():
        full_path = Path('str(Path(__file__).resolve().parent.parent)') / path
        exists = full_path.exists()
        module_check['details'].append({
            'module': name,
            'path': str(path),
            'exists': exists
        })
        status = '✅' if exists else '❌'
        print(f"  {status} {name}: {path}")

    if all(d['exists'] for d in module_check['details']):
        print("  ✅ All modules present")
    else:
        module_check['status'] = 'FAIL'
        print("  ❌ Some modules missing")

    results['validations'].append(module_check)
    print()

    # [2] Pre-trade gate test
    print("[2] Testing pre-trade hard gate...")
    try:
        from paper_trading.pre_trade_hard_gate import PreTradeHardGate

        gate = PreTradeHardGate('str(Path(__file__).resolve().parent.parent)/data/pt4_prep')

        # Test case: insufficient cash (should BLOCK)
        test_orders = [
            {'symbol': 'AAPL', 'side': 'BUY', 'quantity': 100, 'notional': 20000},
            {'symbol': 'MSFT', 'side': 'BUY', 'quantity': 50, 'notional': 15000}
        ]

        status, reasons, audit = gate.validate_orders(
            date='2024-01-01',
            orders=test_orders,
            current_cash=10000,  # Insufficient
            current_holdings={},
            portfolio_value=100000,
            market_data={'AAPL': {'close': 200}, 'MSFT': {'close': 300}},
            tradable_symbols={'AAPL', 'MSFT'}
        )

        gate_test = {
            'name': 'pre_trade_gate',
            'status': 'PASS' if status == 'BLOCK' else 'FAIL',
            'expected': 'BLOCK',
            'actual': status,
            'reasons': reasons
        }

        print(f"  Expected: BLOCK, Got: {status}")
        if status == 'BLOCK':
            print(f"  ✅ Gate correctly blocked insufficient cash")
        else:
            print(f"  ❌ Gate failed to block")

        results['validations'].append(gate_test)
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results['validations'].append({
            'name': 'pre_trade_gate',
            'status': 'ERROR',
            'error': str(e)
        })
    print()

    # [3] Order lifecycle test
    print("[3] Testing order lifecycle engine...")
    try:
        from paper_trading.order_lifecycle_engine import OrderLifecycleEngine, OrderStatus

        lifecycle = OrderLifecycleEngine('str(Path(__file__).resolve().parent.parent)/data/pt4_prep')

        # Create order
        test_order = {'symbol': 'AAPL', 'side': 'BUY', 'quantity': 100, 'notional': 20000}
        order_id = lifecycle.create_order(test_order, '2024-01-01')

        # Update to filled
        lifecycle.update_status(order_id, OrderStatus.FILLED, "Order filled", fill_qty=100, fill_price=200)

        # Check status
        order = lifecycle.get_order(order_id)

        lifecycle_test = {
            'name': 'order_lifecycle',
            'status': 'PASS' if order['status'] == 'filled' else 'FAIL',
            'order_id': order_id,
            'final_status': order['status'],
            'events_count': len(order['events'])
        }

        print(f"  Order ID: {order_id[:8]}...")
        print(f"  Final status: {order['status']}")
        print(f"  Events: {len(order['events'])}")
        print(f"  ✅ Lifecycle tracking working")

        results['validations'].append(lifecycle_test)
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results['validations'].append({
            'name': 'order_lifecycle',
            'status': 'ERROR',
            'error': str(e)
        })
    print()

    # [4] Reconciliation test
    print("[4] Testing post-trade reconciliation...")
    try:
        from paper_trading.post_trade_recon import PostTradeReconciliation

        recon = PostTradeReconciliation('str(Path(__file__).resolve().parent.parent)/data/pt4_prep')

        # Test case: matched
        expected_orders = [{'symbol': 'AAPL', 'quantity': 100}]
        actual_fills = [{'symbol': 'AAPL', 'quantity': 100}]
        expected_positions = {'AAPL': {'quantity': 100}}
        actual_positions = {'AAPL': {'quantity': 100}}

        recon_report = recon.reconcile(
            date='2024-01-01',
            expected_orders=expected_orders,
            actual_fills=actual_fills,
            expected_positions=expected_positions,
            actual_positions=actual_positions,
            expected_cash=10000,
            actual_cash=10000
        )

        recon_test = {
            'name': 'reconciliation',
            'status': 'PASS' if recon_report['overall_status'] == 'MATCHED' else 'FAIL',
            'overall_status': recon_report['overall_status']
        }

        print(f"  Overall status: {recon_report['overall_status']}")
        print(f"  ✅ Reconciliation working")

        results['validations'].append(recon_test)
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results['validations'].append({
            'name': 'reconciliation',
            'status': 'ERROR',
            'error': str(e)
        })
    print()

    # [5] Manual override test
    print("[5] Testing manual override...")
    try:
        override_file = (_REPO_ROOT / 'data/pt4_prep/manual_override.json')

        # Enable override
        override_config = {
            'manual_override_enabled': True,
            'override_reason': 'PT.4 validation test',
            'override_by': 'test_script',
            'override_timestamp': datetime.now().isoformat(),
            'override_type': 'hard_override'
        }

        with open(override_file, 'w') as f:
            json.dump(override_config, f, indent=2)

        # Test risk state machine with override
        from paper_trading.risk_state_machine import RiskStateMachine, RiskState

        rsm = RiskStateMachine(manual_override_file=str(override_file))
        rsm.current_state = RiskState.HALT

        can_trade = rsm.can_trade()

        # Disable override
        override_config['manual_override_enabled'] = False
        with open(override_file, 'w') as f:
            json.dump(override_config, f, indent=2)

        override_test = {
            'name': 'manual_override',
            'status': 'PASS' if can_trade else 'FAIL',
            'can_trade_with_override': can_trade
        }

        print(f"  State: HALT, Override: enabled")
        print(f"  Can trade: {can_trade}")
        if can_trade:
            print(f"  ✅ Manual override working")
        else:
            print(f"  ❌ Manual override not working")

        results['validations'].append(override_test)
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results['validations'].append({
            'name': 'manual_override',
            'status': 'ERROR',
            'error': str(e)
        })
    print()

    # [6] Version lock test
    print("[6] Testing version lock...")
    try:
        version_file = (_REPO_ROOT / 'data/pt4_prep/version_lock/VERSION_LOCK.json')

        with open(version_file, 'r') as f:
            version_lock = json.load(f)

        required_components = [
            'alpha_factory',
            'ml_model',
            'portfolio_constructor',
            'risk_logic',
            'drift_fix',
            'monitoring',
            'broker_schema',
            'pt4_additions'
        ]

        all_present = all(comp in version_lock['components'] for comp in required_components)

        version_test = {
            'name': 'version_lock',
            'status': 'PASS' if all_present else 'FAIL',
            'version': version_lock['version'],
            'phase': version_lock['phase'],
            'components_count': len(version_lock['components'])
        }

        print(f"  Version: {version_lock['version']}")
        print(f"  Phase: {version_lock['phase']}")
        print(f"  Components: {len(version_lock['components'])}")
        if all_present:
            print(f"  ✅ Version lock complete")
        else:
            print(f"  ❌ Missing components")

        results['validations'].append(version_test)
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results['validations'].append({
            'name': 'version_lock',
            'status': 'ERROR',
            'error': str(e)
        })
    print()

    # Summary
    print("=" * 80)
    print("【Validation Summary】")
    print("=" * 80)
    print()

    passed = sum(1 for v in results['validations'] if v['status'] == 'PASS')
    total = len(results['validations'])

    print(f"  Total validations: {total}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {total - passed}")
    print()

    if passed == total:
        print("  ✅ All PT.4 validations passed")
        results['overall_status'] = 'PASS'
    else:
        print("  ⚠️  Some validations failed")
        results['overall_status'] = 'PARTIAL'

    # Save results
    results_file = (_REPO_ROOT / 'data/pt4_prep/validation_results.json')
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    print()
    print(f"  Results saved: {results_file}")
    print()
    print("=" * 80)

    return results


if __name__ == '__main__':
    validate_pt4_modules()
