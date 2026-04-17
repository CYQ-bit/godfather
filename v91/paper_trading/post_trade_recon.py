"""
Post-trade Reconciliation - Godfather V9.0 PT.4
End-of-day reconciliation
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List


class PostTradeReconciliation:
    """End-of-day reconciliation"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.recon_dir = self.output_dir / 'recon'
        self.recon_dir.mkdir(parents=True, exist_ok=True)

        print(f"Initializing PostTradeReconciliation (Godfather V9.0 - PT.4)...")
        print(f"  Output directory: {self.recon_dir}")

    def reconcile(
        self,
        date: str,
        expected_orders: List[Dict],
        actual_fills: List[Dict],
        expected_positions: Dict,
        actual_positions: Dict,
        expected_cash: float,
        actual_cash: float
    ) -> Dict:
        """
        Perform end-of-day reconciliation

        Returns:
            Reconciliation report
        """
        recon_report = {
            'timestamp': datetime.now().isoformat(),
            'date': date,
            'orders_recon': self._reconcile_orders(expected_orders, actual_fills),
            'positions_recon': self._reconcile_positions(expected_positions, actual_positions),
            'cash_recon': self._reconcile_cash(expected_cash, actual_cash)
        }

        # Overall status
        orders_ok = recon_report['orders_recon']['status'] == 'MATCHED'
        positions_ok = recon_report['positions_recon']['status'] == 'MATCHED'
        cash_ok = recon_report['cash_recon']['status'] == 'MATCHED'

        if orders_ok and positions_ok and cash_ok:
            recon_report['overall_status'] = 'MATCHED'
        else:
            recon_report['overall_status'] = 'MISMATCHED'

        # Save report
        recon_file = self.recon_dir / f'{date}_recon.json'
        with open(recon_file, 'w') as f:
            json.dump(recon_report, f, indent=2)

        return recon_report

    def _reconcile_orders(self, expected: List[Dict], actual: List[Dict]) -> Dict:
        """Reconcile orders vs fills"""
        expected_symbols = {o['symbol']: o for o in expected}
        actual_symbols = {f['symbol']: f for f in actual}

        matched = []
        missing_fills = []
        unexpected_fills = []

        for symbol in expected_symbols:
            if symbol in actual_symbols:
                matched.append(symbol)
            else:
                missing_fills.append(symbol)

        for symbol in actual_symbols:
            if symbol not in expected_symbols:
                unexpected_fills.append(symbol)

        return {
            'status': 'MATCHED' if len(missing_fills) == 0 and len(unexpected_fills) == 0 else 'MISMATCHED',
            'expected_count': len(expected),
            'actual_count': len(actual),
            'matched_count': len(matched),
            'missing_fills': missing_fills,
            'unexpected_fills': unexpected_fills
        }

    def _reconcile_positions(self, expected: Dict, actual: Dict) -> Dict:
        """Reconcile positions"""
        expected_symbols = set(expected.keys())
        actual_symbols = set(actual.keys())

        matched = []
        position_diffs = []

        for symbol in expected_symbols | actual_symbols:
            exp_qty = expected.get(symbol, {}).get('quantity', 0)
            act_qty = actual.get(symbol, {}).get('quantity', 0)

            if exp_qty == act_qty:
                matched.append(symbol)
            else:
                position_diffs.append({
                    'symbol': symbol,
                    'expected_qty': exp_qty,
                    'actual_qty': act_qty,
                    'diff': act_qty - exp_qty
                })

        return {
            'status': 'MATCHED' if len(position_diffs) == 0 else 'MISMATCHED',
            'expected_positions': len(expected),
            'actual_positions': len(actual),
            'matched_count': len(matched),
            'position_diffs': position_diffs
        }

    def _reconcile_cash(self, expected: float, actual: float) -> Dict:
        """Reconcile cash"""
        diff = actual - expected
        tolerance = 1.0  # $1 tolerance

        return {
            'status': 'MATCHED' if abs(diff) <= tolerance else 'MISMATCHED',
            'expected_cash': expected,
            'actual_cash': actual,
            'diff': diff
        }
