"""
PT.4.2a Auto-Approval Validation - Godfather V9.0
Test paper auto-approval and live protection
"""
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from paper_trading.manual_review_checkpoints import ManualReviewCheckpoints
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))


def test_paper_auto_approval():
    """Test auto-approval in paper + tiny capital mode"""
    print("="*80)
    print("【Test 1: Paper + Tiny Capital Auto-Approval】")
    print("="*80 + "\n")

    output_dir = 'Path(__file__).resolve().parent.parent/data/paper_trading'

    review = ManualReviewCheckpoints(
        output_dir=output_dir,
        broker_env='paper',
        tiny_capital_enabled=True
    )
    print()

    # Create pre-trade review with gate PASS
    checklist = review.create_pre_trade_review(
        date='2026-03-16',
        orders=[{'symbol': 'AAPL', 'side': 'BUY', 'quantity': 1, 'notional': 150.0}],
        portfolio_summary={'cash': 5000.0, 'value': 5000.0},
        risk_status='OK',
        gate_status='PASS'
    )

    print(f"Status: {checklist['status']}")
    print(f"Approved: {checklist['approved']}")
    print(f"Auto-approved: {checklist.get('auto_approved', False)}")
    print(f"Reviewer: {checklist['reviewer']}")
    print()

    if checklist['status'] == 'APPROVED' and checklist.get('auto_approved', False):
        print("✅ PASS: Paper mode auto-approved")
        return True
    else:
        print("❌ FAIL: Paper mode did not auto-approve")
        return False


def test_live_manual_review():
    """Test that live mode still requires manual review"""
    print("="*80)
    print("【Test 2: Live Mode Manual Review Protection】")
    print("="*80 + "\n")

    output_dir = 'Path(__file__).resolve().parent.parent/data/paper_trading'

    review = ManualReviewCheckpoints(
        output_dir=output_dir,
        broker_env='live',
        tiny_capital_enabled=True
    )
    print()

    # Create pre-trade review with gate PASS
    checklist = review.create_pre_trade_review(
        date='2026-03-16-live',
        orders=[{'symbol': 'AAPL', 'side': 'BUY', 'quantity': 1, 'notional': 150.0}],
        portfolio_summary={'cash': 5000.0, 'value': 5000.0},
        risk_status='OK',
        gate_status='PASS'
    )

    print(f"Status: {checklist['status']}")
    print(f"Approved: {checklist['approved']}")
    print(f"Auto-approved: {checklist.get('auto_approved', False)}")
    print()

    if checklist['status'] == 'PENDING' and not checklist['approved']:
        print("✅ PASS: Live mode requires manual review")
        return True
    else:
        print("❌ FAIL: Live mode was auto-approved (SECURITY VIOLATION)")
        return False


def test_gate_block_no_auto_approve():
    """Test that gate BLOCK prevents auto-approval"""
    print("="*80)
    print("【Test 3: Gate BLOCK Prevents Auto-Approval】")
    print("="*80 + "\n")

    output_dir = 'Path(__file__).resolve().parent.parent/data/paper_trading'

    review = ManualReviewCheckpoints(
        output_dir=output_dir,
        broker_env='paper',
        tiny_capital_enabled=True
    )
    print()

    # Create pre-trade review with gate BLOCK
    checklist = review.create_pre_trade_review(
        date='2026-03-16-blocked',
        orders=[{'symbol': 'AAPL', 'side': 'BUY', 'quantity': 1, 'notional': 150.0}],
        portfolio_summary={'cash': 5000.0, 'value': 5000.0},
        risk_status='OK',
        gate_status='BLOCK'
    )

    print(f"Status: {checklist['status']}")
    print(f"Approved: {checklist['approved']}")
    print(f"Auto-approved: {checklist.get('auto_approved', False)}")
    print()

    if checklist['status'] == 'PENDING' and not checklist['approved']:
        print("✅ PASS: Gate BLOCK prevents auto-approval")
        return True
    else:
        print("❌ FAIL: Gate BLOCK did not prevent auto-approval")
        return False


def generate_report(results):
    """Generate final validation report"""
    print("\n" + "="*80)
    print("【PT.4.2a Auto-Approval Validation Report】")
    print("="*80 + "\n")

    print("【A. 改了哪些文件】")
    print("  1. paper_trading/manual_review_checkpoints.py - Auto-approval logic")
    print("  2. paper_trading/live_tiny_mode_executor.py - Pass gate_status")
    print("  3. paper_trading/run_pt42_live_tiny.py - Pass broker_env + tiny_capital")
    print()

    print("【B. Auto-approve 是否已生效】")
    if results['paper_auto_approve']:
        print("  ✅ YES")
    else:
        print("  ❌ NO")
    print()

    print("【C. paper 模式是否自动批准成功】")
    if results['paper_auto_approve']:
        print("  ✅ YES - Auto-approved in paper + tiny capital + gate PASS")
    else:
        print("  ❌ NO")
    print()

    print("【D. live 模式是否仍要求人工审核】")
    if results['live_manual_review']:
        print("  ✅ YES - Live mode protected, requires manual review")
    else:
        print("  ❌ NO - SECURITY VIOLATION")
    print()

    all_pass = all(results.values())

    print("【E. 最终结论】")
    print()
    print("1. Godfather V9.0 - PT.4.2a 是否完成？")
    if all_pass:
        print("   ✅ 是")
    else:
        print("   ❌ 否")
    print()

    print("2. 当前 paper 模式是否可全自动执行？")
    if results['paper_auto_approve']:
        print("   ✅ 是")
        print("   条件: paper + tiny capital + gate PASS")
    else:
        print("   ❌ 否")
    print()

    print("3. live 模式是否仍被保护？")
    if results['live_manual_review']:
        print("   ✅ 是")
        print("   live 环境仍要求人工审核")
    else:
        print("   ❌ 否 - SECURITY VIOLATION")
    print()

    print("4. 给出唯一正确启动命令。")
    if all_pass:
        print("   python3 paper_trading/run_pt42_live_tiny.py")
    else:
        print("   N/A (未满足条件)")
    print()

    print("="*80)

    # Save report
    report_file = (_REPO_ROOT / 'data/pt4_prep/pt42a_auto_approval_validation.json')
    with open(report_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': results,
            'all_pass': all_pass
        }, f, indent=2)

    print(f"\nReport saved: {report_file}")


def main():
    try:
        results = {
            'paper_auto_approve': test_paper_auto_approval(),
            'live_manual_review': test_live_manual_review(),
            'gate_block_protection': test_gate_block_no_auto_approve()
        }

        generate_report(results)

    except Exception as e:
        print(f"\n❌ Validation failed with error:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
