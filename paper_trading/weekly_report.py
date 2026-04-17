"""
Weekly Report Generator - Godfather V9.0 Phase PT.2.3
Enhanced with Normal vs Stress regime separation
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import json


class WeeklyReportGenerator:
    """Generate weekly summary reports with regime separation"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.weekly_reports_dir = self.output_dir / 'weekly_reports'
        self.weekly_reports_dir.mkdir(parents=True, exist_ok=True)

        print(f"Initializing WeeklyReportGenerator (Godfather V9.0 - PT.2.3)...")
        print(f"  Output directory: {self.weekly_reports_dir}")
        print(f"  Regime-aware reporting: ON")

    def generate_weekly_report(
        self,
        week_start: str,
        week_end: str,
        daily_results: list,
        baseline_metrics: dict
    ) -> str:
        """
        Generate weekly report

        Args:
            week_start: Week start date
            week_end: Week end date
            daily_results: List of daily results
            baseline_metrics: Baseline metrics for comparison

        Returns:
            Report text
        """
        # Filter results for this week
        week_results = [r for r in daily_results
                       if r['status'] == 'completed'
                       and week_start <= r.get('date', '') <= week_end]

        if len(week_results) == 0:
            return f"No data for week {week_start} to {week_end}"

        # PT.2.3: Separate by regime
        normal_results = [r for r in week_results if r.get('regime', 'normal') in ['normal', 'high_vol']]
        stress_results = [r for r in week_results if r.get('regime') in ['stress', 'extreme']]

        # Generate report with regime separation
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append(f"【Godfather V9.0 - Weekly Report】")
        report_lines.append(f"Week: {week_start} to {week_end}")
        report_lines.append("=" * 80)
        report_lines.append("")
        report_lines.append(f"Total observations: {len(week_results)}")
        report_lines.append(f"  Normal regime: {len(normal_results)}")
        report_lines.append(f"  Stress regime: {len(stress_results)}")
        report_lines.append("")

        # Normal Regime Summary
        if len(normal_results) > 0:
            report_lines.append("=" * 80)
            report_lines.append("【Normal Regime Summary】")
            report_lines.append("=" * 80)
            report_lines.extend(self._generate_regime_summary(normal_results, baseline_metrics, "normal"))
            report_lines.append("")

        # Stress Regime Summary
        if len(stress_results) > 0:
            report_lines.append("=" * 80)
            report_lines.append("【Stress Regime Summary】")
            report_lines.append("=" * 80)
            report_lines.extend(self._generate_regime_summary(stress_results, baseline_metrics, "stress"))
            report_lines.append("")

        report_lines.append("=" * 80)

        report_text = '\n'.join(report_lines)

        # Save report
        report_file = self.weekly_reports_dir / f'week_{week_start}_to_{week_end}.txt'
        with open(report_file, 'w') as f:
            f.write(report_text)

        return report_text

    def _generate_regime_summary(self, results: list, baseline_metrics: dict, regime_type: str) -> list:
        """Generate summary for a specific regime"""
        lines = []

        # Portfolio values and returns
        portfolio_values = [r['accounting_summary']['total_value'] for r in results]
        returns = [(portfolio_values[i] - portfolio_values[i-1]) / portfolio_values[i-1]
                   for i in range(1, len(portfolio_values))]

        period_return = (portfolio_values[-1] - portfolio_values[0]) / portfolio_values[0] if len(portfolio_values) > 1 else 0
        period_volatility = np.std(returns) * np.sqrt(252) if len(returns) > 0 else 0

        # Max drawdown
        cummax = np.maximum.accumulate(portfolio_values)
        drawdowns = (np.array(portfolio_values) - cummax) / cummax
        max_dd = np.min(drawdowns) if len(drawdowns) > 0 else 0

        # Turnover
        turnovers = [r['portfolio_summary'].get('expected_turnover', 0)
                    for r in results
                    if r['portfolio_summary'].get('status') != 'No rebalance']

        avg_turnover = np.mean(turnovers) if len(turnovers) > 0 else 0
        ex_first_turnover = np.mean(turnovers[1:]) if len(turnovers) > 1 else avg_turnover

        # Implementation shortfall
        impl_shortfalls = [r['execution_summary'].get('implementation_shortfall_abs_mean_bps', 0)
                          for r in results
                          if r['execution_summary'].get('status') != 'No fills']

        impl_mean = np.mean(impl_shortfalls) if len(impl_shortfalls) > 0 else 0
        impl_p95 = np.percentile(impl_shortfalls, 95) if len(impl_shortfalls) > 0 else 0

        # Retained/added/dropped
        retained_list = []
        added_list = []
        dropped_list = []

        for r in results:
            if r['portfolio_summary'].get('status') != 'No rebalance':
                buffer_stats = r['portfolio_summary'].get('buffer_stats', {})
                retained_list.append(buffer_stats.get('retained', 0))
                added_list.append(buffer_stats.get('added', 0))
                dropped_list.append(buffer_stats.get('dropped', 0))

        avg_retained = np.mean(retained_list) if len(retained_list) > 0 else 0
        avg_added = np.mean(added_list) if len(added_list) > 0 else 0
        avg_dropped = np.mean(dropped_list) if len(dropped_list) > 0 else 0

        # Risk/Drift warnings
        risk_warns = sum(1 for r in results if r['risk_results'].get('overall_status') == 'WARN')
        drift_warns = sum(1 for r in results if r['drift_results'].get('drift_detected'))

        # Shadow validation (if available)
        shadow_validations = [r.get('shadow_validation', {}) for r in results]
        shadow_pass_count = sum(1 for sv in shadow_validations if sv.get('status') == 'PASS')
        shadow_pass_rate = shadow_pass_count / len(shadow_validations) if len(shadow_validations) > 0 else 0

        # Baseline comparison
        baseline_sharpe = baseline_metrics.get('sharpe', 2.2341)
        baseline_turnover = baseline_metrics.get('avg_turnover', 0.4014)

        # Generate lines
        lines.append(f"Observations: {len(results)}")
        lines.append("")
        lines.append(f"Performance:")
        lines.append(f"  Return: {period_return*100:.2f}%")
        lines.append(f"  Volatility (annualized): {period_volatility*100:.2f}%")
        lines.append(f"  Max drawdown: {max_dd*100:.2f}%")
        lines.append("")
        lines.append(f"Turnover:")
        lines.append(f"  Average: {avg_turnover*100:.1f}%")
        lines.append(f"  Ex-first: {ex_first_turnover*100:.1f}%")
        lines.append(f"  Baseline: {baseline_turnover*100:.1f}%")
        lines.append(f"  Drift: {(ex_first_turnover - baseline_turnover)*100:+.1f} pct points")
        lines.append("")
        lines.append(f"Implementation Shortfall:")
        lines.append(f"  Mean: {impl_mean:.1f} bps")
        lines.append(f"  P95: {impl_p95:.1f} bps")
        lines.append("")
        lines.append(f"Retained/Added/Dropped:")
        lines.append(f"  Avg retained: {avg_retained:.1f} stocks")
        lines.append(f"  Avg added: {avg_added:.1f} stocks")
        lines.append(f"  Avg dropped: {avg_dropped:.1f} stocks")
        lines.append("")
        lines.append(f"Risk/Drift Warnings:")
        lines.append(f"  Risk WARNs: {risk_warns}")
        lines.append(f"  Drift WARNs: {drift_warns}")
        lines.append("")

        if len(shadow_validations) > 0:
            lines.append(f"Shadow Validation:")
            lines.append(f"  Pass rate: {shadow_pass_rate*100:.1f}%")
            lines.append(f"  Total checks: {len(shadow_validations)}")
            lines.append("")

        if regime_type == "stress":
            lines.append(f"Note: Elevated metrics expected during stress regime")

        return lines
