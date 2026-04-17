"""
Dashboard Summary Generator - Godfather V9.0 Phase PT.2.3
Lightweight dashboard metrics aggregation with regime awareness
"""
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime


class DashboardGenerator:
    """Generate lightweight dashboard summary with regime tracking"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.dashboard_dir = self.output_dir / 'dashboard'
        self.dashboard_dir.mkdir(parents=True, exist_ok=True)

        print(f"Initializing DashboardGenerator (Godfather V9.0 - PT.2.3)...")
        print(f"  Output directory: {self.dashboard_dir}")
        print(f"  Regime-aware metrics: ON")

    def generate_dashboard(
        self,
        daily_results: list,
        run_id: str
    ) -> dict:
        """
        Generate dashboard summary

        Args:
            daily_results: List of daily results
            run_id: Current run ID

        Returns:
            Dashboard summary dict
        """
        completed = [r for r in daily_results if r['status'] == 'completed']

        if len(completed) == 0:
            return {'status': 'No data'}

        # Current portfolio
        latest = completed[-1]
        current_value = latest['accounting_summary']['total_value']
        current_cash = latest['accounting_summary']['cash']
        current_positions = latest['accounting_summary']['num_positions']
        cumulative_return = latest['accounting_summary']['return_pct']

        # Rolling Sharpe (last 20 observations)
        portfolio_values = [r['accounting_summary']['total_value'] for r in completed]

        if len(portfolio_values) > 1:
            returns = [(portfolio_values[i] - portfolio_values[i-1]) / portfolio_values[i-1]
                       for i in range(1, len(portfolio_values))]

            rolling_window = min(20, len(returns))
            rolling_returns = returns[-rolling_window:]
            rolling_sharpe = (np.mean(rolling_returns) / np.std(rolling_returns) * np.sqrt(252)) if np.std(rolling_returns) > 0 else 0
        else:
            rolling_sharpe = 0

        # Rolling drawdown
        cummax = np.maximum.accumulate(portfolio_values)
        drawdowns = (np.array(portfolio_values) - cummax) / cummax
        rolling_dd = np.min(drawdowns[-20:]) if len(drawdowns) >= 20 else np.min(drawdowns)

        # Ex-first turnover
        turnovers = [r['portfolio_summary'].get('expected_turnover', 0)
                    for r in completed
                    if r['portfolio_summary'].get('status') != 'No rebalance']

        ex_first_turnover = np.mean(turnovers[1:]) if len(turnovers) > 1 else 0

        # Implementation shortfall rolling mean
        impl_shortfalls = [r['execution_summary'].get('implementation_shortfall_abs_mean_bps', 0)
                          for r in completed
                          if r['execution_summary'].get('status') != 'No fills']

        rolling_impl = np.mean(impl_shortfalls[-5:]) if len(impl_shortfalls) >= 5 else (np.mean(impl_shortfalls) if len(impl_shortfalls) > 0 else 0)

        # Retained/added/dropped rolling mean
        retained_list = []
        added_list = []
        dropped_list = []

        for r in completed:
            if r['portfolio_summary'].get('status') != 'No rebalance':
                buffer_stats = r['portfolio_summary'].get('buffer_stats', {})
                retained_list.append(buffer_stats.get('retained', 0))
                added_list.append(buffer_stats.get('added', 0))
                dropped_list.append(buffer_stats.get('dropped', 0))

        rolling_retained = np.mean(retained_list[-5:]) if len(retained_list) >= 5 else (np.mean(retained_list) if len(retained_list) > 0 else 0)
        rolling_added = np.mean(added_list[-5:]) if len(added_list) >= 5 else (np.mean(added_list) if len(added_list) > 0 else 0)
        rolling_dropped = np.mean(dropped_list[-5:]) if len(dropped_list) >= 5 else (np.mean(dropped_list) if len(dropped_list) > 0 else 0)

        # Sector exposure (from latest portfolio)
        latest_portfolio_summary = latest['portfolio_summary']
        sector_exposure = latest_portfolio_summary.get('sector_exposure', {}) if latest_portfolio_summary.get('status') != 'No rebalance' else {}

        # Top 3 sectors
        if len(sector_exposure) > 0:
            top_sectors = sorted(sector_exposure.items(), key=lambda x: x[1], reverse=True)[:3]
        else:
            top_sectors = []

        # Latest status
        latest_risk_status = latest['risk_results'].get('overall_status', 'UNKNOWN')
        latest_drift_status = latest['drift_results'].get('drift_status', 'OK')

        # Alert counts
        risk_warns = sum(1 for r in completed if r['risk_results'].get('overall_status') == 'WARN')
        risk_halts = sum(1 for r in completed if r['risk_results'].get('overall_status') == 'HALT')
        drift_warns = sum(1 for r in completed if r['drift_results'].get('drift_detected'))

        # PT.2.3: Regime distribution
        regime_counts = {}
        for r in completed:
            regime = r.get('regime', 'unknown')
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

        latest_regime = latest.get('regime', 'unknown')

        # PT.2.3: Shadow validation pass rate (if available)
        shadow_validations = [r.get('shadow_validation', {}) for r in completed]
        shadow_pass_count = sum(1 for sv in shadow_validations if sv.get('status') == 'PASS')
        shadow_pass_rate = shadow_pass_count / len(shadow_validations) if len(shadow_validations) > 0 else 0

        # Dashboard summary
        dashboard = {
            'timestamp': datetime.now().isoformat(),
            'run_id': run_id,
            'observation_points': len(completed),
            'rebalance_points': len(turnovers),
            'current_portfolio': {
                'value': current_value,
                'cash': current_cash,
                'positions': current_positions,
                'cumulative_return_pct': cumulative_return * 100
            },
            'rolling_metrics': {
                'sharpe': rolling_sharpe,
                'drawdown': rolling_dd,
                'ex_first_turnover_pct': ex_first_turnover * 100,
                'impl_shortfall_bps': rolling_impl,
                'retained': rolling_retained,
                'added': rolling_added,
                'dropped': rolling_dropped
            },
            'sector_exposure_top3': [{'sector': s, 'weight_pct': w * 100} for s, w in top_sectors],
            'status': {
                'risk': latest_risk_status,
                'drift': latest_drift_status
            },
            'regime': {
                'current': latest_regime,
                'distribution': regime_counts
            },
            'alerts': {
                'risk_warns': risk_warns,
                'risk_halts': risk_halts,
                'drift_warns': drift_warns,
                'total': risk_warns + risk_halts + drift_warns
            },
            'shadow_validation': {
                'pass_rate_pct': shadow_pass_rate * 100,
                'total_checks': len(shadow_validations)
            }
        }

        # Save JSON
        json_file = self.dashboard_dir / 'dashboard_summary.json'
        with open(json_file, 'w') as f:
            json.dump(dashboard, f, indent=2)

        # Save TXT
        txt_file = self.dashboard_dir / 'dashboard_summary.txt'
        txt_lines = []
        txt_lines.append("=" * 80)
        txt_lines.append("【Godfather V9.0 - Dashboard Summary】")
        txt_lines.append(f"Updated: {dashboard['timestamp']}")
        txt_lines.append("=" * 80)
        txt_lines.append("")
        txt_lines.append(f"Run ID: {run_id[:8]}...")
        txt_lines.append(f"Observation points: {dashboard['observation_points']}")
        txt_lines.append(f"Rebalance points: {dashboard['rebalance_points']}")
        txt_lines.append("")
        txt_lines.append("【Current Portfolio】")
        txt_lines.append(f"  Value: ${dashboard['current_portfolio']['value']:,.2f}")
        txt_lines.append(f"  Cash: ${dashboard['current_portfolio']['cash']:,.2f}")
        txt_lines.append(f"  Positions: {dashboard['current_portfolio']['positions']}")
        txt_lines.append(f"  Cumulative return: {dashboard['current_portfolio']['cumulative_return_pct']:.2f}%")
        txt_lines.append("")
        txt_lines.append("【Rolling Metrics】")
        txt_lines.append(f"  Sharpe: {dashboard['rolling_metrics']['sharpe']:.2f}")
        txt_lines.append(f"  Drawdown: {dashboard['rolling_metrics']['drawdown']*100:.2f}%")
        txt_lines.append(f"  Ex-first turnover: {dashboard['rolling_metrics']['ex_first_turnover_pct']:.1f}%")
        txt_lines.append(f"  Impl shortfall (rolling): {dashboard['rolling_metrics']['impl_shortfall_bps']:.1f} bps")
        txt_lines.append(f"  Retained (rolling): {dashboard['rolling_metrics']['retained']:.1f}")
        txt_lines.append(f"  Added (rolling): {dashboard['rolling_metrics']['added']:.1f}")
        txt_lines.append(f"  Dropped (rolling): {dashboard['rolling_metrics']['dropped']:.1f}")
        txt_lines.append("")
        txt_lines.append("【Sector Exposure Top 3】")
        for item in dashboard['sector_exposure_top3']:
            txt_lines.append(f"  {item['sector']}: {item['weight_pct']:.1f}%")
        txt_lines.append("")
        txt_lines.append("【Status】")
        txt_lines.append(f"  Risk: {dashboard['status']['risk']}")
        txt_lines.append(f"  Drift: {dashboard['status']['drift']}")
        txt_lines.append("")
        txt_lines.append("【Alerts】")
        txt_lines.append(f"  Risk WARNs: {dashboard['alerts']['risk_warns']}")
        txt_lines.append(f"  Risk HALTs: {dashboard['alerts']['risk_halts']}")
        txt_lines.append(f"  Drift WARNs: {dashboard['alerts']['drift_warns']}")
        txt_lines.append(f"  Total: {dashboard['alerts']['total']}")
        txt_lines.append("")
        txt_lines.append("=" * 80)

        with open(txt_file, 'w') as f:
            f.write("\n".join(txt_lines))

        print(f"✅ Dashboard updated:")
        print(f"   {json_file}")
        print(f"   {txt_file}")

        return dashboard
