"""
Manual Review Checkpoints - Godfather V9.0 PT.4.2a
Human review gates with paper auto-approval
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List


class ManualReviewCheckpoints:
    """Manual review checkpoints for PT.4.2a"""

    def __init__(self, output_dir: str, broker_env: str = 'unknown', tiny_capital_enabled: bool = False):
        self.output_dir = Path(output_dir)
        self.review_dir = self.output_dir / 'manual_reviews'
        self.review_dir.mkdir(parents=True, exist_ok=True)
        self.broker_env = broker_env
        self.tiny_capital_enabled = tiny_capital_enabled

        print("Initializing ManualReviewCheckpoints (Godfather V9.0 - PT.4.2a)...")
        print(f"  Output directory: {self.review_dir}")
        print(f"  Broker env: {self.broker_env}")
        print(f"  Tiny capital: {self.tiny_capital_enabled}")

        if self.broker_env == 'paper' and self.tiny_capital_enabled:
            print(f"  Auto-approve: ENABLED (paper + tiny capital)")
        else:
            print(f"  Auto-approve: DISABLED (manual review required)")

    def create_pre_trade_review(
        self,
        date: str,
        orders: List[Dict],
        portfolio_summary: Dict,
        risk_status: str,
        gate_status: str = 'UNKNOWN'
    ) -> Dict:
        """
        Create pre-trade review checklist

        PT.4.2a: Auto-approve if paper + tiny capital + gate PASS

        Returns:
            Review checklist
        """
        checklist = {
            'timestamp': datetime.now().isoformat(),
            'date': date,
            'review_type': 'pre_trade',
            'status': 'PENDING',
            'orders_count': len(orders),
            'total_notional': sum(abs(o['notional']) for o in orders),
            'checks': [
                {'item': 'Orders reviewed', 'status': 'PENDING', 'note': ''},
                {'item': 'Portfolio summary reviewed', 'status': 'PENDING', 'note': ''},
                {'item': 'Risk status acceptable', 'status': 'PENDING', 'note': ''},
                {'item': 'Tiny capital limits checked', 'status': 'PENDING', 'note': ''},
                {'item': 'No duplicate orders', 'status': 'PENDING', 'note': ''},
                {'item': 'All prices available', 'status': 'PENDING', 'note': ''}
            ],
            'reviewer': '',
            'review_timestamp': '',
            'approved': False
        }

        # PT.4.2a: Auto-approve in paper + tiny capital mode if gate PASS
        if self.broker_env == 'paper' and self.tiny_capital_enabled and gate_status == 'PASS':
            checklist['status'] = 'APPROVED'
            checklist['approved'] = True
            checklist['reviewer'] = 'system_auto'
            checklist['review_timestamp'] = datetime.now().isoformat()
            checklist['auto_approved'] = True
            checklist['auto_approve_reason'] = 'Auto-approved in paper tiny-capital mode'

            # Mark all checks as PASS
            for check in checklist['checks']:
                check['status'] = 'PASS'

            print(f"  ✅ Auto-approved (paper + tiny capital + gate PASS)")

        # Save checklist
        review_file = self.review_dir / f'{date}_pre_trade_review.json'
        with open(review_file, 'w') as f:
            json.dump(checklist, f, indent=2)

        return checklist

    def create_post_fill_review(
        self,
        date: str,
        fills: List[Dict],
        execution_summary: Dict
    ) -> Dict:
        """
        Create post-fill review checklist

        Returns:
            Review checklist
        """
        checklist = {
            'timestamp': datetime.now().isoformat(),
            'date': date,
            'review_type': 'post_fill',
            'status': 'PENDING',
            'fills_count': len(fills),
            'checks': [
                {'item': 'All fills reviewed', 'status': 'PENDING', 'note': ''},
                {'item': 'Fill prices reasonable', 'status': 'PENDING', 'note': ''},
                {'item': 'No unexpected fills', 'status': 'PENDING', 'note': ''},
                {'item': 'Implementation shortfall acceptable', 'status': 'PENDING', 'note': ''}
            ],
            'reviewer': '',
            'review_timestamp': '',
            'approved': False
        }

        # Save checklist
        review_file = self.review_dir / f'{date}_post_fill_review.json'
        with open(review_file, 'w') as f:
            json.dump(checklist, f, indent=2)

        return checklist

    def create_eod_recon_review(
        self,
        date: str,
        recon_report: Dict
    ) -> Dict:
        """
        Create end-of-day reconciliation review checklist

        Returns:
            Review checklist
        """
        checklist = {
            'timestamp': datetime.now().isoformat(),
            'date': date,
            'review_type': 'eod_recon',
            'status': 'PENDING',
            'recon_status': recon_report.get('overall_status', 'UNKNOWN'),
            'checks': [
                {'item': 'Orders reconciled', 'status': 'PENDING', 'note': ''},
                {'item': 'Positions reconciled', 'status': 'PENDING', 'note': ''},
                {'item': 'Cash reconciled', 'status': 'PENDING', 'note': ''},
                {'item': 'No mismatches', 'status': 'PENDING', 'note': ''},
                {'item': 'All discrepancies explained', 'status': 'PENDING', 'note': ''}
            ],
            'reviewer': '',
            'review_timestamp': '',
            'approved': False
        }

        # Save checklist
        review_file = self.review_dir / f'{date}_eod_recon_review.json'
        with open(review_file, 'w') as f:
            json.dump(checklist, f, indent=2)

        return checklist

    def approve_review(self, review_file: str, reviewer: str, notes: str = "") -> bool:
        """
        Approve a review checklist

        Returns:
            Success status
        """
        review_path = Path(review_file)
        if not review_path.exists():
            print(f"❌ Review file not found: {review_file}")
            return False

        with open(review_path, 'r') as f:
            checklist = json.load(f)

        checklist['status'] = 'APPROVED'
        checklist['reviewer'] = reviewer
        checklist['review_timestamp'] = datetime.now().isoformat()
        checklist['approved'] = True
        checklist['reviewer_notes'] = notes

        # Mark all checks as PASS
        for check in checklist['checks']:
            check['status'] = 'PASS'

        with open(review_path, 'w') as f:
            json.dump(checklist, f, indent=2)

        print(f"✅ Review approved by {reviewer}")
        return True
