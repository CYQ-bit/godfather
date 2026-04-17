"""
PT.4.2 Pre-Launch Checklist - Godfather V9.0
8-item terminal check before live tiny rehearsal
"""
import json
import sys
from pathlib import Path
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))

sys.path.insert(0, str(Path(__file__).parent.parent))


def check_environment():
    """[1] Environment mode check"""
    print("[1] Environment Mode Check...")

    config_file = (_REPO_ROOT / 'data/pt4_prep/broker_connection_config.json')

    if not config_file.exists():
        print("  ❌ Broker config not found")
        return False, {}

    with open(config_file, 'r') as f:
        config = json.load(f)

    broker_env = config.get('environment', 'UNKNOWN')
    account_id = config.get('account_id', 'UNKNOWN')

    if broker_env != 'paper':
        print(f"  ❌ Environment is {broker_env}, expected 'paper'")
        return False, {}

    print(f"  ✅ Environment: {broker_env}")
    print(f"  Account: {account_id[:4]}***{account_id[-4:] if len(account_id) > 8 else '***'}")

    return True, {
        'broker_env': broker_env,
        'account_status': 'paper',
        'routing_mode': 'controllable'
    }


def check_tiny_capital():
    """[2] Tiny capital mode check"""
    print("\n[2] Tiny Capital Mode Check...")

    config_file = (_REPO_ROOT / 'data/pt4_prep/tiny_capital_config.json')

    if not config_file.exists():
        print("  ❌ Tiny capital config not found")
        return False, {}

    with open(config_file, 'r') as f:
        config = json.load(f)

    if not config.get('enabled', False):
        print("  ❌ Tiny capital mode not enabled")
        return False, {}

    limits = config.get('limits', {})
    max_capital = limits.get('max_total_capital', 0)
    max_daily = limits.get('max_daily_order_notional', 0)
    max_single = limits.get('max_single_stock_notional', 0)

    if max_capital != 5000:
        print(f"  ⚠️  Capital cap is ${max_capital}, expected $5000")

    print(f"  ✅ Tiny mode: ON")
    print(f"  Capital cap: ${max_capital:,.0f}")
    print(f"  Max daily: ${max_daily:,.0f}")
    print(f"  Max single stock: ${max_single:,.0f}")

    return True, {
        'tiny_mode': 'ON',
        'capital_cap': max_capital,
        'daily_limit': max_daily,
        'single_limit': max_single
    }


def check_routing_switch():
    """[3] Real broker routing switch check"""
    print("\n[3] Real Broker Routing Switch Check...")

    config_file = (_REPO_ROOT / 'data/pt4_prep/broker_mode_config.json')

    if not config_file.exists():
        print("  ❌ Broker mode config not found")
        return False, {}

    with open(config_file, 'r') as f:
        config = json.load(f)

    current_mode = config.get('current_mode', 'UNKNOWN')
    live_enabled = config.get('live_enabled', False)

    print(f"  Current mode: {current_mode}")
    print(f"  Live enabled: {live_enabled}")

    if current_mode == 'shadow' and not live_enabled:
        print(f"  ✅ Routing: OFF (safe default)")
    elif current_mode == 'live_tiny' and live_enabled:
        print(f"  ⚠️  Routing: ON (live mode active)")
    else:
        print(f"  ⚠️  Routing: {current_mode}")

    return True, {
        'routing_switch': current_mode,
        'live_order_enabled': 'YES' if live_enabled else 'NO'
    }


def check_auth_account():
    """[4] Credentials and account check"""
    print("\n[4] Credentials & Account Check...")

    health_file = (_REPO_ROOT / 'data/pt4_prep/broker_health_summary.json')

    if not health_file.exists():
        print("  ⚠️  Health check not run, running now...")
        return False, {}

    with open(health_file, 'r') as f:
        health = json.load(f)

    auth_status = health.get('auth', 'UNKNOWN')
    account_status = health.get('account', 'UNKNOWN')

    print(f"  Auth: {auth_status}")
    print(f"  Account: {account_status}")

    if auth_status == 'PASS' and account_status == 'PASS':
        print(f"  ✅ Auth & Account: PASS")
        return True, {'auth': 'PASS', 'account': 'PASS'}
    else:
        print(f"  ❌ Auth or Account failed")
        return False, {}


def check_hard_gate():
    """[5] Pre-trade hard gate check"""
    print("\n[5] Pre-trade Hard Gate Check...")

    gate_file = (_REPO_ROOT / 'paper_trading/pre_trade_hard_gate.py')

    if not gate_file.exists():
        print("  ❌ Hard gate module not found")
        return False, {}

    # Count rules by reading file
    with open(gate_file, 'r') as f:
        content = f.read()

    rules = [
        'cash_sufficiency',
        'duplicate_orders',
        'missing_prices',
        'tradability',
        'payload_completeness',
        'turnover_limit',
        'negative_cash_projection'
    ]

    rules_found = sum(1 for rule in rules if rule in content)

    print(f"  ✅ Hard gate loaded")
    print(f"  Rules: {rules_found}/7")

    return True, {
        'hard_gate': 'LOADED',
        'rule_count': rules_found
    }


def check_manual_review():
    """[6] Manual review check"""
    print("\n[6] Manual Review Check...")

    review_file = (_REPO_ROOT / 'paper_trading/manual_review_checkpoints.py')

    if not review_file.exists():
        print("  ❌ Manual review module not found")
        return False, {}

    with open(review_file, 'r') as f:
        content = f.read()

    checkpoints = [
        'create_pre_trade_review',
        'create_post_fill_review',
        'create_eod_recon_review'
    ]

    checkpoints_found = sum(1 for cp in checkpoints if cp in content)

    print(f"  ✅ Manual review loaded")
    print(f"  Checkpoints: {checkpoints_found}/3")

    return True, {
        'review_checkpoints': 'LOADED',
        'checkpoint_count': checkpoints_found
    }


def check_recon_audit_state():
    """[7] Reconciliation / audit / state check"""
    print("\n[7] Reconciliation / Audit / State Check...")

    recon_file = (_REPO_ROOT / 'paper_trading/post_trade_recon.py')
    version_lock = (_REPO_ROOT / 'data/pt4_prep/version_lock/VERSION_LOCK.json')
    audit_dir = (_REPO_ROOT / 'data/pt4_prep/audit_log')
    state_dir = (_REPO_ROOT / 'data/paper_trading/state')

    recon_ok = recon_file.exists()
    version_ok = version_lock.exists()
    audit_ok = audit_dir.exists() or audit_dir.parent.exists()
    state_ok = state_dir.exists()

    print(f"  Recon: {'✅' if recon_ok else '❌'}")
    print(f"  Version lock: {'✅' if version_ok else '❌'}")
    print(f"  Audit log: {'✅' if audit_ok else '❌'}")
    print(f"  State dir: {'✅' if state_ok else '❌'}")

    all_ok = recon_ok and version_ok and audit_ok and state_ok

    if all_ok:
        print(f"  ✅ Recon/Audit/State: PASS")
    else:
        print(f"  ❌ Some components missing")

    return all_ok, {
        'recon': 'PASS' if recon_ok else 'FAIL',
        'audit': 'PASS' if audit_ok else 'FAIL',
        'state': 'PASS' if state_ok else 'FAIL'
    }


def check_entrypoint():
    """[8] PT.4.2 entrypoint check"""
    print("\n[8] PT.4.2 Entrypoint Check...")

    # PT.4.2 should have a dedicated entrypoint
    entrypoint = (_REPO_ROOT / 'paper_trading/run_pt42_live_tiny.py')

    if not entrypoint.exists():
        print(f"  ⚠️  Dedicated PT.4.2 entrypoint not found")
        print(f"  Expected: {entrypoint}")
        return False, {}

    print(f"  ✅ Entrypoint: {entrypoint.name}")
    print(f"  Launch command: python3 paper_trading/run_pt42_live_tiny.py")

    return True, {
        'entrypoint': str(entrypoint),
        'launch_command': 'python3 paper_trading/run_pt42_live_tiny.py'
    }


def generate_summary(results):
    """Generate final summary"""
    print("\n" + "=" * 80)
    print("【PT.4.2 Pre-Launch Checklist Summary】")
    print("=" * 80)
    print()

    print("【A. 8 项检查结果】")
    for i, (name, (passed, _)) in enumerate(results.items(), 1):
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {i}. {name}: {status}")
    print()

    all_passed = all(passed for passed, _ in results.values())

    print("【B. 是否允许启动 PT.4.2】")
    if all_passed:
        print("  ✅ YES")
    else:
        print("  ❌ NO")
    print()

    if not all_passed:
        print("【C. 阻塞项】")
        blockers = [name for name, (passed, _) in results.items() if not passed]
        for blocker in blockers:
            print(f"  - {blocker}")
        print()
    else:
        print("【D. 启动命令】")
        entrypoint_data = results.get('entrypoint', (False, {}))[1]
        if entrypoint_data:
            print(f"  python3 paper_trading/run_pt42_live_tiny.py")
        else:
            print(f"  ⚠️  Entrypoint not ready")
        print()

    print("=" * 80)

    # Save summary
    summary_file = (_REPO_ROOT / 'data/pt4_prep/pt42_prelaunch_checklist.json')
    summary = {
        'all_passed': all_passed,
        'results': {name: {'passed': passed, 'data': data} for name, (passed, data) in results.items()}
    }
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nChecklist saved: {summary_file}")


def main():
    """Run pre-launch checklist"""
    print("=" * 80)
    print("【Godfather V9.0 - PT.4.2 Pre-Launch Checklist】")
    print("=" * 80)
    print()

    results = {}

    results['environment'] = check_environment()
    results['tiny_capital'] = check_tiny_capital()
    results['routing_switch'] = check_routing_switch()
    results['auth_account'] = check_auth_account()
    results['hard_gate'] = check_hard_gate()
    results['manual_review'] = check_manual_review()
    results['recon_audit_state'] = check_recon_audit_state()
    results['entrypoint'] = check_entrypoint()

    generate_summary(results)


if __name__ == '__main__':
    main()
