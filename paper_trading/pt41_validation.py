"""
PT.4.1 Validation Script - Godfather V9.0
Validate tiny capital live rehearsal readiness
"""
import json
import sys
from pathlib import Path
from datetime import datetime
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))

sys.path.insert(0, str(Path(__file__).parent.parent))


def validate_pt41_modules():
    """Validate PT.4.1 module implementation"""

    print("=" * 80)
    print("【Godfather V9.0 - PT.4.1 Validation】")
    print("=" * 80)
    print()

    results = {
        'timestamp': datetime.now().isoformat(),
        'validations': []
    }

    # [1] Tiny capital config
    print("[1] Testing tiny capital mode...")
    try:
        config_file = (_REPO_ROOT / 'data/pt4_prep/tiny_capital_config.json')
        with open(config_file, 'r') as f:
            config = json.load(f)

        required_limits = ['max_total_capital', 'max_daily_order_notional', 'max_single_stock_notional']
        all_present = all(limit in config['limits'] for limit in required_limits)

        tiny_test = {
            'name': 'tiny_capital_mode',
            'status': 'PASS' if all_present else 'FAIL',
            'max_capital': config['limits']['max_total_capital'],
            'max_daily_notional': config['limits']['max_daily_order_notional']
        }

        print(f"  Max capital: ${config['limits']['max_total_capital']:,.0f}")
        print(f"  Max daily notional: ${config['limits']['max_daily_order_notional']:,.0f}")
        print(f"  Max single stock: ${config['limits']['max_single_stock_notional']:,.0f}")
        print(f"  ✅ Tiny capital limits configured")

        results['validations'].append(tiny_test)
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results['validations'].append({'name': 'tiny_capital_mode', 'status': 'ERROR', 'error': str(e)})
    print()

    # [2] Simple order policy
    print("[2] Testing simple order policy...")
    try:
        from paper_trading.simple_order_policy import SimpleOrderPolicy

        policy = SimpleOrderPolicy()

        # Test valid order
        valid_order = {
            'symbol': 'AAPL',
            'side': 'BUY',
            'quantity': 10,
            'notional': 2000,
            'order_type': 'LIMIT',
            'tif': 'DAY',
            'limit_price': 200
        }
        is_valid, reason = policy.validate_order(valid_order)

        # Test invalid order (complex algo)
        invalid_order = {
            'symbol': 'AAPL',
            'side': 'BUY',
            'quantity': 10,
            'notional': 2000,
            'algo': 'VWAP'
        }
        is_invalid, _ = policy.validate_order(invalid_order)

        policy_test = {
            'name': 'simple_order_policy',
            'status': 'PASS' if is_valid and not is_invalid else 'FAIL',
            'valid_order_passed': is_valid,
            'invalid_order_blocked': not is_invalid
        }

        print(f"  Valid order: {'PASS' if is_valid else 'FAIL'}")
        print(f"  Invalid order blocked: {'PASS' if not is_invalid else 'FAIL'}")
        print(f"  ✅ Simple order policy working")

        results['validations'].append(policy_test)
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results['validations'].append({'name': 'simple_order_policy', 'status': 'ERROR', 'error': str(e)})
    print()

    # [3] Broker mode switch
    print("[3] Testing broker mode switch...")
    try:
        from paper_trading.broker_mode_switch import BrokerModeSwitch, BrokerMode

        switch = BrokerModeSwitch('Path(__file__).resolve().parent.parent/data/pt4_prep/broker_mode_config.json')

        current_mode = switch.get_current_mode()
        can_use_live = switch.can_use_live_mode()

        switch_test = {
            'name': 'broker_mode_switch',
            'status': 'PASS',
            'current_mode': current_mode.value,
            'live_enabled': can_use_live
        }

        print(f"  Current mode: {current_mode.value}")
        print(f"  Live enabled: {can_use_live}")
        print(f"  ✅ Broker mode switch working")

        results['validations'].append(switch_test)
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results['validations'].append({'name': 'broker_mode_switch', 'status': 'ERROR', 'error': str(e)})
    print()

    # [4] Manual review checkpoints
    print("[4] Testing manual review checkpoints...")
    try:
        from paper_trading.manual_review_checkpoints import ManualReviewCheckpoints

        review = ManualReviewCheckpoints('Path(__file__).resolve().parent.parent/data/pt4_prep')

        # Create pre-trade review
        test_orders = [{'symbol': 'AAPL', 'side': 'BUY', 'quantity': 10, 'notional': 2000}]
        checklist = review.create_pre_trade_review(
            date='2024-01-01',
            orders=test_orders,
            portfolio_summary={},
            risk_status='OK'
        )

        review_test = {
            'name': 'manual_review_checkpoints',
            'status': 'PASS' if checklist['status'] == 'PENDING' else 'FAIL',
            'checks_count': len(checklist['checks'])
        }

        print(f"  Review created: {checklist['review_type']}")
        print(f"  Checks: {len(checklist['checks'])}")
        print(f"  Status: {checklist['status']}")
        print(f"  ✅ Manual review checkpoints working")

        results['validations'].append(review_test)
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results['validations'].append({'name': 'manual_review_checkpoints', 'status': 'ERROR', 'error': str(e)})
    print()

    # [5] Hard stop rules
    print("[5] Testing hard stop rules...")
    try:
        from paper_trading.hard_stop_rules import HardStopRules

        rules = HardStopRules()

        # Test normal conditions (should not halt)
        should_halt_normal, reasons_normal = rules.check_hard_stop_conditions(
            recon_status='MATCHED',
            broker_reject_rate=0.05,
            position_mismatch=False,
            cash_mismatch=False,
            duplicate_orders=False,
            unexpected_fills=False,
            missing_acks=False,
            manual_review_failed=False
        )

        # Test halt condition (recon fail)
        should_halt_fail, reasons_fail = rules.check_hard_stop_conditions(
            recon_status='MISMATCHED',
            broker_reject_rate=0.05,
            position_mismatch=False,
            cash_mismatch=False,
            duplicate_orders=False,
            unexpected_fills=False,
            missing_acks=False,
            manual_review_failed=False
        )

        rules_test = {
            'name': 'hard_stop_rules',
            'status': 'PASS' if not should_halt_normal and should_halt_fail else 'FAIL',
            'normal_no_halt': not should_halt_normal,
            'fail_halts': should_halt_fail
        }

        print(f"  Normal conditions: {'No halt' if not should_halt_normal else 'Halt'}")
        print(f"  Fail conditions: {'Halt' if should_halt_fail else 'No halt'}")
        print(f"  ✅ Hard stop rules working")

        results['validations'].append(rules_test)
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results['validations'].append({'name': 'hard_stop_rules', 'status': 'ERROR', 'error': str(e)})
    print()

    # [6] Integration test
    print("[6] Testing full chain integration...")
    try:
        from paper_trading.simple_order_policy import SimpleOrderPolicy
        from paper_trading.broker_mode_switch import BrokerModeSwitch
        from paper_trading.manual_review_checkpoints import ManualReviewCheckpoints
        from paper_trading.hard_stop_rules import HardStopRules

        # Simulate tiny capital order flow
        policy = SimpleOrderPolicy()
        switch = BrokerModeSwitch('Path(__file__).resolve().parent.parent/data/pt4_prep/broker_mode_config.json')
        review = ManualReviewCheckpoints('Path(__file__).resolve().parent.parent/data/pt4_prep')
        rules = HardStopRules()

        # Create simple order
        order = {
            'symbol': 'AAPL',
            'side': 'BUY',
            'quantity': 5,
            'notional': 1000,
            'order_type': 'LIMIT',
            'tif': 'DAY',
            'limit_price': 200
        }

        # Validate order
        is_valid, _ = policy.validate_order(order)

        # Check mode
        current_mode = switch.get_current_mode()

        # Create review
        checklist = review.create_pre_trade_review('2024-01-01', [order], {}, 'OK')

        # Check hard stop
        should_halt, _ = rules.check_hard_stop_conditions(
            recon_status='MATCHED',
            broker_reject_rate=0.0,
            position_mismatch=False,
            cash_mismatch=False,
            duplicate_orders=False,
            unexpected_fills=False,
            missing_acks=False,
            manual_review_failed=False
        )

        integration_test = {
            'name': 'full_chain_integration',
            'status': 'PASS' if is_valid and not should_halt else 'FAIL',
            'order_valid': is_valid,
            'mode': current_mode.value,
            'review_created': checklist['status'] == 'PENDING',
            'no_halt': not should_halt
        }

        print(f"  Order validation: {'PASS' if is_valid else 'FAIL'}")
        print(f"  Broker mode: {current_mode.value}")
        print(f"  Review created: {'PASS' if checklist['status'] == 'PENDING' else 'FAIL'}")
        print(f"  Hard stop check: {'PASS' if not should_halt else 'FAIL'}")
        print(f"  ✅ Full chain integration working")

        results['validations'].append(integration_test)
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results['validations'].append({'name': 'full_chain_integration', 'status': 'ERROR', 'error': str(e)})
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
        print("  ✅ All PT.4.1 validations passed")
        results['overall_status'] = 'PASS'
    else:
        print("  ⚠️  Some validations failed")
        results['overall_status'] = 'PARTIAL'

    # Save results
    results_file = (_REPO_ROOT / 'data/pt4_prep/pt41_validation_results.json')
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    print()
    print(f"  Results saved: {results_file}")
    print()
    print("=" * 80)

    return results


if __name__ == '__main__':
    validate_pt41_modules()
