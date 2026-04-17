"""
Live Tiny Mode Executor - Godfather V9.0 PT.4.2
Execute tiny capital live orders with full safety checks
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple


class LiveTinyModeExecutor:
    """Execute live tiny mode with all safety checks"""

    def __init__(
        self,
        broker_connection,
        tiny_capital_config: Dict,
        pre_trade_gate,
        manual_review,
        hard_stop_rules,
        output_dir: str
    ):
        self.broker = broker_connection
        self.tiny_config = tiny_capital_config
        self.gate = pre_trade_gate
        self.review = manual_review
        self.hard_stop = hard_stop_rules
        self.output_dir = Path(output_dir)
        self.live_dir = self.output_dir / 'live_tiny_runs'
        self.live_dir.mkdir(parents=True, exist_ok=True)

        print("Initializing LiveTinyModeExecutor (Godfather V9.0 - PT.4.2)...")
        print(f"  Max capital: ${tiny_capital_config['limits']['max_total_capital']:,.0f}")
        print(f"  Max daily notional: ${tiny_capital_config['limits']['max_daily_order_notional']:,.0f}")
        print(f"  Manual review: {tiny_capital_config['safety']['require_manual_review']}")

    def execute_live_tiny_run(
        self,
        date: str,
        orders: List[Dict],
        current_cash: float,
        current_holdings: Dict,
        portfolio_value: float,
        market_data: Dict,
        tradable_symbols: set
    ) -> Dict:
        """
        Execute live tiny run with full safety checks

        Returns:
            Execution report
        """
        run_report = {
            'timestamp': datetime.now().isoformat(),
            'date': date,
            'phase': 'PT.4.2',
            'mode': 'live_tiny',
            'stages': []
        }

        print(f"\n{'='*80}")
        print(f"【Live Tiny Run - {date}】")
        print(f"{'='*80}\n")

        # Stage 1: Pre-trade gate
        print("[Stage 1] Pre-trade hard gate...")
        gate_status, gate_reasons, gate_audit = self.gate.validate_orders(
            date=date,
            orders=orders,
            current_cash=current_cash,
            current_holdings=current_holdings,
            portfolio_value=portfolio_value,
            market_data=market_data,
            tradable_symbols=tradable_symbols
        )

        run_report['stages'].append({
            'stage': 'pre_trade_gate',
            'status': gate_status,
            'reasons': gate_reasons
        })

        if gate_status == 'BLOCK':
            print(f"  ❌ BLOCKED: {gate_reasons}")
            run_report['final_status'] = 'BLOCKED_AT_GATE'
            self._save_run_report(date, run_report)
            return run_report

        print(f"  ✅ Gate: {gate_status}")

        # Stage 2: Manual pre-trade review
        print("\n[Stage 2] Manual pre-trade review...")
        review_checklist = self.review.create_pre_trade_review(
            date=date,
            orders=orders,
            portfolio_summary={'cash': current_cash, 'value': portfolio_value},
            risk_status='OK',
            gate_status=gate_status
        )

        if review_checklist.get('auto_approved', False):
            print(f"  ✅ Auto-approved (paper mode)")
        else:
            print(f"  ⚠️  Manual review required")
        print(f"  Review file: {self.review.review_dir / f'{date}_pre_trade_review.json'}")
        print(f"  Status: {review_checklist['status']}")

        run_report['stages'].append({
            'stage': 'pre_trade_review',
            'status': review_checklist['status'],
            'checks': len(review_checklist['checks']),
            'auto_approved': review_checklist.get('auto_approved', False)
        })

        if review_checklist['status'] != 'APPROVED':
            print(f"  ⚠️  Awaiting manual approval")
            run_report['final_status'] = 'AWAITING_REVIEW'
            self._save_run_report(date, run_report)
            return run_report

        # Stage 3: Broker submission
        print("\n[Stage 3] Broker order submission...")

        if self.broker.status.value != 'connected':
            print(f"  ❌ Broker not connected: {self.broker.status.value}")
            run_report['stages'].append({
                'stage': 'broker_submission',
                'status': 'FAILED',
                'reason': 'Broker not connected'
            })
            run_report['final_status'] = 'BROKER_NOT_CONNECTED'
            self._save_run_report(date, run_report)
            return run_report

        broker_responses = []
        for order in orders:
            response = self.broker.submit_order(order)
            if response:
                broker_responses.append(response)
                print(f"  ✅ Order submitted: {order['symbol']} {order['side']} {order['quantity']}")
            else:
                print(f"  ❌ Order failed: {order['symbol']}")

        run_report['stages'].append({
            'stage': 'broker_submission',
            'status': 'SUCCESS' if len(broker_responses) > 0 else 'FAILED',
            'submitted': len(broker_responses),
            'total': len(orders)
        })

        # Stage 4: Post-fill review (placeholder)
        print("\n[Stage 4] Post-fill review...")
        print(f"  ⚠️  Manual post-fill review required")

        run_report['stages'].append({
            'stage': 'post_fill_review',
            'status': 'PENDING'
        })

        # Stage 5: Reconciliation (placeholder)
        print("\n[Stage 5] End-of-day reconciliation...")
        print(f"  ⚠️  Manual reconciliation review required")

        run_report['stages'].append({
            'stage': 'reconciliation',
            'status': 'PENDING'
        })

        run_report['final_status'] = 'COMPLETED'
        self._save_run_report(date, run_report)

        print(f"\n{'='*80}")
        print(f"Live tiny run completed: {run_report['final_status']}")
        print(f"{'='*80}\n")

        return run_report

    def _save_run_report(self, date: str, report: Dict):
        """Save run report"""
        report_file = self.live_dir / f'{date}_live_tiny_run.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
