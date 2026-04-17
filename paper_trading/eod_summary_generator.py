"""
EOD Summary Generator - Godfather V9.0 PT.4
Generate end-of-day summary report
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict


class EODSummaryGenerator:
    """Generate end-of-day summary"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.eod_dir = self.output_dir / 'dashboard'
        self.eod_dir.mkdir(parents=True, exist_ok=True)

        print(f"Initializing EODSummaryGenerator (Godfather V9.0 - PT.4)...")
        print(f"  Output directory: {self.eod_dir}")

    def generate_eod_summary(
        self,
        run_id: str,
        date: str,
        regime: str,
        target_positions: int,
        actual_positions: int,
        shadow_order_count: int,
        fills_count: int,
        cash: float,
        holdings_value: float,
        total_value: float,
        turnover: float,
        retained: int,
        added: int,
        dropped: int,
        impl_shortfall: float,
        risk_status: str,
        drift_status: str,
        recon_status: str,
        shadow_validation_pass_rate: float,
        alert_count: int,
        gate_status: str = "PASS"
    ) -> Dict:
        """Generate EOD summary"""

        summary = {
            'timestamp': datetime.now().isoformat(),
            'version': 'V9.0',
            'phase': 'PT.4',
            'run_id': run_id,
            'date': date,
            'regime': regime,
            'portfolio': {
                'target_positions': target_positions,
                'actual_positions': actual_positions,
                'cash': cash,
                'holdings_value': holdings_value,
                'total_value': total_value
            },
            'execution': {
                'shadow_order_count': shadow_order_count,
                'fills_count': fills_count,
                'turnover': turnover,
                'retained': retained,
                'added': added,
                'dropped': dropped,
                'impl_shortfall': impl_shortfall
            },
            'status': {
                'gate': gate_status,
                'risk': risk_status,
                'drift': drift_status,
                'reconciliation': recon_status
            },
            'validation': {
                'shadow_validation_pass_rate': shadow_validation_pass_rate,
                'alert_count': alert_count
            }
        }

        # Save JSON
        json_file = self.eod_dir / f'{date}_eod_summary.json'
        with open(json_file, 'w') as f:
            json.dump(summary, f, indent=2)

        # Save TXT
        txt_file = self.eod_dir / f'{date}_eod_summary.txt'
        self._save_txt_summary(summary, txt_file)

        return summary

    def _save_txt_summary(self, summary: Dict, txt_file: Path):
        """Save text version of summary"""
        lines = []
        lines.append("=" * 80)
        lines.append(f"【Godfather {summary['version']} - EOD Summary】")
        lines.append(f"Phase: {summary['phase']}")
        lines.append(f"Date: {summary['date']}")
        lines.append(f"Run ID: {summary['run_id'][:8]}...")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Regime: {summary['regime']}")
        lines.append("")
        lines.append("【Portfolio】")
        lines.append(f"  Target positions: {summary['portfolio']['target_positions']}")
        lines.append(f"  Actual positions: {summary['portfolio']['actual_positions']}")
        lines.append(f"  Cash: ${summary['portfolio']['cash']:,.2f}")
        lines.append(f"  Holdings: ${summary['portfolio']['holdings_value']:,.2f}")
        lines.append(f"  Total value: ${summary['portfolio']['total_value']:,.2f}")
        lines.append("")
        lines.append("【Execution】")
        lines.append(f"  Shadow orders: {summary['execution']['shadow_order_count']}")
        lines.append(f"  Fills: {summary['execution']['fills_count']}")
        lines.append(f"  Turnover: {summary['execution']['turnover']*100:.1f}%")
        lines.append(f"  Retained: {summary['execution']['retained']}")
        lines.append(f"  Added: {summary['execution']['added']}")
        lines.append(f"  Dropped: {summary['execution']['dropped']}")
        lines.append(f"  Impl shortfall: {summary['execution']['impl_shortfall']:.1f} bps")
        lines.append("")
        lines.append("【Status】")
        lines.append(f"  Gate: {summary['status']['gate']}")
        lines.append(f"  Risk: {summary['status']['risk']}")
        lines.append(f"  Drift: {summary['status']['drift']}")
        lines.append(f"  Reconciliation: {summary['status']['reconciliation']}")
        lines.append("")
        lines.append("【Validation】")
        lines.append(f"  Shadow validation: {summary['validation']['shadow_validation_pass_rate']*100:.1f}%")
        lines.append(f"  Alerts: {summary['validation']['alert_count']}")
        lines.append("")
        lines.append("=" * 80)

        with open(txt_file, 'w') as f:
            f.write('\n'.join(lines))
