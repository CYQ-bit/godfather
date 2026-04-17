"""
Hard Stop Rules - Godfather V9.0 PT.4.1
Additional hard stop conditions for tiny capital live mode
"""
from typing import Dict, List, Tuple


class HardStopRules:
    """Hard stop rules for PT.4.1"""

    def __init__(self):
        print("Initializing HardStopRules (Godfather V9.0 - PT.4.1)...")
        print("  PT.4.1 hard stop conditions:")
        print("    - Reconciliation fail")
        print("    - Broker reject anomaly")
        print("    - Position mismatch")
        print("    - Cash mismatch")
        print("    - Duplicate order")
        print("    - Unexpected fill")
        print("    - Missing broker ack")
        print("    - Manual review fail")

    def check_hard_stop_conditions(
        self,
        recon_status: str,
        broker_reject_rate: float,
        position_mismatch: bool,
        cash_mismatch: bool,
        duplicate_orders: bool,
        unexpected_fills: bool,
        missing_acks: bool,
        manual_review_failed: bool
    ) -> Tuple[bool, List[str]]:
        """
        Check if any hard stop condition is met

        Returns:
            (should_halt, reasons)
        """
        should_halt = False
        reasons = []

        # [1] Reconciliation fail
        if recon_status == 'MISMATCHED':
            should_halt = True
            reasons.append("Reconciliation failed")

        # [2] Broker reject anomaly (>20% reject rate)
        if broker_reject_rate > 0.20:
            should_halt = True
            reasons.append(f"Broker reject rate {broker_reject_rate*100:.1f}% exceeds 20%")

        # [3] Position mismatch
        if position_mismatch:
            should_halt = True
            reasons.append("Position mismatch detected")

        # [4] Cash mismatch
        if cash_mismatch:
            should_halt = True
            reasons.append("Cash mismatch detected")

        # [5] Duplicate order
        if duplicate_orders:
            should_halt = True
            reasons.append("Duplicate orders detected")

        # [6] Unexpected fill
        if unexpected_fills:
            should_halt = True
            reasons.append("Unexpected fills detected")

        # [7] Missing broker ack
        if missing_acks:
            should_halt = True
            reasons.append("Missing broker acknowledgements")

        # [8] Manual review fail
        if manual_review_failed:
            should_halt = True
            reasons.append("Manual review failed")

        return should_halt, reasons

    def evaluate_and_halt(
        self,
        date: str,
        recon_report: Dict,
        execution_summary: Dict,
        manual_review_status: str
    ) -> Tuple[bool, List[str]]:
        """
        Evaluate all conditions and determine if halt is needed

        Returns:
            (should_halt, reasons)
        """
        # Extract metrics
        recon_status = recon_report.get('overall_status', 'UNKNOWN')

        # Broker reject rate (placeholder - would come from execution summary)
        total_orders = execution_summary.get('total_orders', 0)
        rejected_orders = execution_summary.get('rejected_orders', 0)
        broker_reject_rate = rejected_orders / total_orders if total_orders > 0 else 0

        # Position/cash mismatch
        position_mismatch = recon_report.get('positions_recon', {}).get('status') == 'MISMATCHED'
        cash_mismatch = recon_report.get('cash_recon', {}).get('status') == 'MISMATCHED'

        # Other conditions (would be extracted from logs)
        duplicate_orders = False  # Placeholder
        unexpected_fills = False  # Placeholder
        missing_acks = False  # Placeholder
        manual_review_failed = manual_review_status == 'FAILED'

        return self.check_hard_stop_conditions(
            recon_status=recon_status,
            broker_reject_rate=broker_reject_rate,
            position_mismatch=position_mismatch,
            cash_mismatch=cash_mismatch,
            duplicate_orders=duplicate_orders,
            unexpected_fills=unexpected_fills,
            missing_acks=missing_acks,
            manual_review_failed=manual_review_failed
        )
