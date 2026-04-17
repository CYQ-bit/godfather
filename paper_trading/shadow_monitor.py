"""
Shadow Monitor - Godfather V9.0 Phase PT.3a
Monitor paper vs shadow order comparison
"""
import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime


class ShadowMonitor:
    """Monitor paper vs shadow order comparison"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.shadow_dir = self.output_dir / 'shadow_orders'
        self.shadow_reports_dir = self.output_dir / 'shadow_reports'
        self.integration_checks_dir = self.output_dir / 'integration_checks'

        self.shadow_dir.mkdir(parents=True, exist_ok=True)
        self.shadow_reports_dir.mkdir(parents=True, exist_ok=True)
        self.integration_checks_dir.mkdir(parents=True, exist_ok=True)

        self.comparison_history = []

        print(f"Initializing ShadowMonitor (Godfather V9.0 - PT.3a)...")
        print(f"  Output: {self.shadow_dir}")

    def compare_paper_vs_shadow(
        self,
        date: str,
        target_portfolio: 'pd.DataFrame',
        paper_orders: List[Dict],
        shadow_payloads: List[Dict],
        integration_checks: Dict,
        lifecycle_events: List[Dict]
    ) -> Dict:
        """
        Compare paper vs shadow orders

        Args:
            date: Signal date
            target_portfolio: Target portfolio
            paper_orders: Paper trading orders
            shadow_payloads: Shadow broker payloads
            integration_checks: Integration check results
            lifecycle_events: Order lifecycle events

        Returns:
            Comparison results
        """
        comparison = {
            'date': date,
            'timestamp': datetime.now().isoformat(),
            'target_weights': {},
            'paper_orders': {
                'count': len(paper_orders),
                'total_notional': sum(abs(o['target_shares'] * o['reference_price']) for o in paper_orders)
            },
            'shadow_payloads': {
                'count': len(shadow_payloads),
                'total_notional': sum(p['notional'] for p in shadow_payloads)
            },
            'integration_checks': {
                'overall_status': integration_checks.get('overall_status', 'UNKNOWN'),
                'symbol_mapping': integration_checks['checks']['symbol_mapping']['status'],
                'trading_calendar': integration_checks['checks']['trading_calendar']['status'],
                'tradability': integration_checks['checks']['tradability']['status'],
                'order_fields': integration_checks['checks']['order_fields']['status']
            },
            'lifecycle_summary': self._summarize_lifecycle(lifecycle_events),
            'validation': {
                'payload_validation_pass': integration_checks.get('overall_status') == 'PASS',
                'rejected_count': sum(1 for e in lifecycle_events if e['status'] == 'rejected'),
                'missing_symbol_count': integration_checks['checks']['tradability'].get('missing_count', 0),
                'bad_field_count': integration_checks['checks']['order_fields'].get('incomplete_count', 0)
            }
        }

        # Extract target weights
        if len(target_portfolio) > 0:
            comparison['target_weights'] = {
                row['stock_code']: row['target_weight']
                for _, row in target_portfolio.iterrows()
            }

        self.comparison_history.append(comparison)

        # Save comparison
        self._save_comparison(date, comparison)

        # Save shadow payloads
        self._save_shadow_payloads(date, shadow_payloads)

        # Save integration checks
        self._save_integration_checks(date, integration_checks)

        # Save lifecycle events
        self._save_lifecycle_events(date, lifecycle_events)

        return comparison

    def _summarize_lifecycle(self, lifecycle_events: List[Dict]) -> Dict:
        """Summarize lifecycle events"""
        if len(lifecycle_events) == 0:
            return {'total': 0}

        status_counts = {}
        for event in lifecycle_events:
            status = event['status']
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            'total_events': len(lifecycle_events),
            'status_counts': status_counts
        }

    def _save_comparison(self, date: str, comparison: Dict):
        """Save comparison report"""
        report_file = self.shadow_reports_dir / f"{date}_comparison.json"
        with open(report_file, 'w') as f:
            json.dump(comparison, f, indent=2)

    def _save_shadow_payloads(self, date: str, shadow_payloads: List[Dict]):
        """Save shadow payloads"""
        # Convert pandas Timestamps to strings for JSON serialization
        serializable_payloads = []
        for payload in shadow_payloads:
            serializable = payload.copy()
            if 'intended_trade_date' in serializable:
                serializable['intended_trade_date'] = str(serializable['intended_trade_date'])
            serializable_payloads.append(serializable)

        payload_file = self.shadow_dir / f"{date}_payloads.json"
        with open(payload_file, 'w') as f:
            json.dump(serializable_payloads, f, indent=2)

    def _save_integration_checks(self, date: str, integration_checks: Dict):
        """Save integration checks"""
        check_file = self.integration_checks_dir / f"{date}_checks.json"
        with open(check_file, 'w') as f:
            json.dump(integration_checks, f, indent=2)

    def _save_lifecycle_events(self, date: str, lifecycle_events: List[Dict]):
        """Save lifecycle events"""
        lifecycle_file = self.shadow_dir / f"{date}_lifecycle.json"
        with open(lifecycle_file, 'w') as f:
            json.dump(lifecycle_events, f, indent=2)

    def get_shadow_summary(self) -> Dict:
        """Get shadow monitoring summary"""
        if len(self.comparison_history) == 0:
            return {'total': 0}

        total_comparisons = len(self.comparison_history)
        validation_passed = sum(1 for c in self.comparison_history if c['validation']['payload_validation_pass'])
        total_rejected = sum(c['validation']['rejected_count'] for c in self.comparison_history)
        total_missing = sum(c['validation']['missing_symbol_count'] for c in self.comparison_history)
        total_bad_fields = sum(c['validation']['bad_field_count'] for c in self.comparison_history)

        return {
            'total_comparisons': total_comparisons,
            'validation_passed': validation_passed,
            'validation_failed': total_comparisons - validation_passed,
            'total_rejected': total_rejected,
            'total_missing_symbols': total_missing,
            'total_bad_fields': total_bad_fields,
            'pass_rate': validation_passed / total_comparisons if total_comparisons > 0 else 0
        }

    def print_shadow_summary(self):
        """Print shadow monitoring summary"""
        summary = self.get_shadow_summary()

        if summary['total_comparisons'] == 0:
            print("No shadow comparisons")
            return

        print(f"\n{'='*80}")
        print(f"【Shadow Monitoring Summary】")
        print(f"{'='*80}\n")
        print(f"  Total comparisons: {summary['total_comparisons']}")
        print(f"  Validation passed: {summary['validation_passed']}")
        print(f"  Validation failed: {summary['validation_failed']}")
        print(f"  Pass rate: {summary['pass_rate']*100:.1f}%")
        print()
        print(f"  Total rejected orders: {summary['total_rejected']}")
        print(f"  Total missing symbols: {summary['total_missing_symbols']}")
        print(f"  Total bad fields: {summary['total_bad_fields']}")
        print()
