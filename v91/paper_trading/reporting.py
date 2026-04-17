"""
Reporting Module - Godfather V9.0 Phase PT.1.1
Generate daily and weekly paper trading reports with proper accounting
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import json


class ReportGenerator:
    """
    Generate paper trading reports - Godfather V9.0 PT.1.1

    Features:
    - Daily trading reports with proper accounting
    - Weekly performance summaries
    - Risk status tracking
    - Drift monitoring results
    - Execution quality metrics with slippage decomposition
    - Hold buffer statistics
    """

    def __init__(self, output_dir: str):
        """
        Initialize report generator

        Args:
            output_dir: Output directory for reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        print(f"Initializing ReportGenerator (Godfather V9.0 - PT.1.1a)...")
        print(f"  Output directory: {self.output_dir}")

    def generate_daily_report(
        self,
        date: str,
        signal_summary: Dict,
        portfolio_summary: Dict,
        order_summary: Dict,
        accounting_summary: Dict,
        execution_summary: Dict,
        risk_results: Dict,
        drift_results: Dict
    ) -> str:
        """
        Generate daily paper trading report

        Args:
            date: Report date
            signal_summary: Signal generation summary
            portfolio_summary: Portfolio construction summary
            order_summary: Order execution summary
            accounting_summary: Accounting summary (cash, holdings, PnL)
            execution_summary: Execution quality summary
            risk_results: Risk check results
            drift_results: Drift monitoring results

        Returns:
            Report text
        """
        report = []
        report.append("=" * 80)
        report.append(f"【Godfather V9.0 - Phase PT.1.1a Daily Report】")
        report.append(f"Date: {date}")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        report.append("")

        # Section 1: Signal Summary
        report.append("【1. Signal Generation】")
        report.append("")
        if signal_summary.get('status') == 'No signal data':
            report.append("  No signals generated")
        else:
            report.append(f"  Signal date: {signal_summary.get('signal_date', 'N/A')}")
            report.append(f"  Number of signals: {signal_summary.get('num_signals', 0)}")
            report.append(f"  Number of symbols: {signal_summary.get('num_symbols', 0)}")
            report.append(f"  Score mean: {signal_summary.get('raw_score_mean', 0):.4f}")
            report.append(f"  Score std: {signal_summary.get('raw_score_std', 0):.4f}")
            report.append(f"  Model version: {signal_summary.get('model_version', 'N/A')}")
        report.append("")

        # Section 2: Portfolio Construction
        report.append("【2. Portfolio Construction】")
        report.append("")
        if portfolio_summary.get('status') == 'No rebalance':
            report.append("  No rebalance today")
        else:
            report.append(f"  Target stocks: {portfolio_summary.get('num_stocks', 0)}")
            report.append(f"  Expected turnover: {portfolio_summary.get('expected_turnover', 0)*100:.2f}%")
            report.append(f"  Gross exposure: {portfolio_summary.get('gross_exposure', 0)*100:.2f}%")
            report.append(f"  Net exposure: {portfolio_summary.get('net_exposure', 0)*100:.2f}%")
            report.append(f"  Rebalance count: {portfolio_summary.get('rebalance_count', 0)}")

            # Hold buffer statistics
            if 'buffer_stats' in portfolio_summary:
                buffer = portfolio_summary['buffer_stats']
                report.append("")
                report.append("  Hold Buffer Statistics:")
                report.append(f"    Retained positions: {buffer.get('retained', 0)}")
                report.append(f"    New positions: {buffer.get('added', 0)}")
                report.append(f"    Dropped positions: {buffer.get('dropped', 0)}")

            if 'sector_exposure' in portfolio_summary:
                report.append("")
                report.append("  Top Sector Exposure:")
                for sector, weight in sorted(portfolio_summary['sector_exposure'].items(), key=lambda x: -x[1])[:5]:
                    report.append(f"    {sector}: {weight*100:.2f}%")
        report.append("")

        # Section 3: Order Execution
        report.append("【3. Order Execution】")
        report.append("")
        if order_summary.get('status') == 'No orders':
            report.append("  No orders executed")
        else:
            report.append(f"  Total orders: {order_summary.get('total_orders', 0)}")
            report.append(f"  Filled orders: {order_summary.get('filled_orders', 0)}")
            report.append(f"  Failed orders: {order_summary.get('failed_orders', 0)}")
            report.append(f"  Fill rate: {order_summary.get('fill_rate', 0)*100:.2f}%")
            report.append(f"  Total transaction cost: ${order_summary.get('total_cost', 0):,.2f}")
        report.append("")

        # Section 4: Execution Quality (PT.1.1a - Slippage Decomposition)
        report.append("【4. Execution Quality - Slippage Decomposition (PT.1.1a)】")
        report.append("")
        if execution_summary.get('status') == 'No fills':
            report.append("  No fills to analyze")
        else:
            report.append(f"  Market Move (Signal -> Trade):")
            report.append(f"    Mean: {execution_summary.get('market_move_mean_bps', 0):.1f} bps")
            report.append(f"    Abs Mean: {execution_summary.get('market_move_abs_mean_bps', 0):.1f} bps")
            report.append("")
            report.append(f"  Execution Slippage (Trade -> Fill):")
            report.append(f"    Mean: {execution_summary.get('execution_slippage_mean_bps', 0):.1f} bps")
            report.append(f"    Abs Mean: {execution_summary.get('execution_slippage_abs_mean_bps', 0):.1f} bps")
            report.append(f"    (Should be ~0 for T+1 close execution)")
            report.append("")
            report.append(f"  Implementation Shortfall (Signal -> Fill):")
            report.append(f"    Mean: {execution_summary.get('implementation_shortfall_mean_bps', 0):.1f} bps")
            report.append(f"    Abs Mean: {execution_summary.get('implementation_shortfall_abs_mean_bps', 0):.1f} bps")
        report.append("")

        # Section 5: Portfolio Accounting (PT.1.1a - Mark-to-Market)
        report.append("【5. Portfolio Accounting - Mark-to-Market (PT.1.1a)】")
        report.append("")
        report.append(f"  Cash: ${accounting_summary.get('cash', 0):,.2f}")
        report.append(f"  Holdings value: ${accounting_summary.get('holdings_value', 0):,.2f}")
        report.append(f"  Total portfolio value: ${accounting_summary.get('total_value', 0):,.2f}")
        report.append("")
        report.append(f"  Unrealized PnL: ${accounting_summary.get('unrealized_pnl', 0):,.2f}")
        report.append(f"  Realized PnL: ${accounting_summary.get('realized_pnl', 0):,.2f}")
        report.append(f"  Total PnL: ${accounting_summary.get('total_pnl', 0):,.2f}")
        report.append(f"  Return: {accounting_summary.get('return_pct', 0)*100:.2f}%")
        report.append("")
        report.append(f"  Number of positions: {accounting_summary.get('num_positions', 0)}")
        report.append(f"  Total transaction costs: ${accounting_summary.get('total_transaction_costs', 0):,.2f}")

        # Cash constraint status (PT.1.1a)
        if accounting_summary.get('cash_constraint_triggered', False):
            report.append(f"  Cash constraint: ⚠️  TRIGGERED")
        else:
            report.append(f"  Cash constraint: ✅ OK")
        report.append("")

        # Section 6: Risk Status
        report.append("【6. Risk Status】")
        report.append("")
        overall_status = risk_results.get('overall_status', 'UNKNOWN')
        report.append(f"  Overall status: {overall_status}")

        if len(risk_results.get('violations', [])) > 0:
            report.append("")
            report.append("  Violations:")
            for violation in risk_results['violations']:
                report.append(f"    ⚠️  {violation}")
        else:
            report.append("  ✅ All risk checks passed")
        report.append("")

        # Section 7: Drift Status
        report.append("【7. Drift Monitoring】")
        report.append("")
        drift_detected = drift_results.get('drift_detected', False)
        report.append(f"  Drift detected: {'YES ⚠️' if drift_detected else 'NO ✅'}")

        if drift_detected:
            report.append("")
            report.append("  Drift details:")
            for check_name, check_result in drift_results.get('checks', {}).items():
                if check_result.get('drift_detected', False):
                    report.append(f"    {check_name}: drift detected")
        report.append("")

        report.append("=" * 80)

        report_text = "\n".join(report)

        # Save report
        report_file = self.output_dir / 'daily_reports' / f"{date}.txt"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, 'w') as f:
            f.write(report_text)

        # Save JSON summary
        json_summary = {
            'date': date,
            'signal_summary': signal_summary,
            'portfolio_summary': portfolio_summary,
            'order_summary': order_summary,
            'accounting_summary': accounting_summary,
            'execution_summary': execution_summary,
            'risk_results': risk_results,
            'drift_results': drift_results
        }

        json_file = self.output_dir / 'daily_reports' / f"{date}.json"
        with open(json_file, 'w') as f:
            json.dump(json_summary, f, indent=2, default=str)

        print(f"\n✅ Daily report saved:")
        print(f"   {report_file}")
        print(f"   {json_file}")

        return report_text

    def generate_weekly_summary(
        self,
        start_date: str,
        end_date: str,
        daily_reports: List[Dict]
    ) -> str:
        """
        Generate weekly summary report

        Args:
            start_date: Week start date
            end_date: Week end date
            daily_reports: List of daily report summaries

        Returns:
            Report text
        """
        report = []
        report.append("=" * 80)
        report.append(f"【Godfather V9.0 - Phase PT.1.1a Weekly Summary】")
        report.append(f"Week: {start_date} to {end_date}")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        report.append("")

        # Calculate weekly metrics
        accounting_summaries = [r.get('accounting_summary', {}) for r in daily_reports if r.get('accounting_summary')]

        if len(accounting_summaries) > 0:
            start_value = accounting_summaries[0].get('total_value', 0)
            end_value = accounting_summaries[-1].get('total_value', 0)
            weekly_return = (end_value - start_value) / start_value if start_value > 0 else 0

            report.append("【Weekly Performance】")
            report.append("")
            report.append(f"  Trading days: {len(daily_reports)}")
            report.append(f"  Start value: ${start_value:,.2f}")
            report.append(f"  End value: ${end_value:,.2f}")
            report.append(f"  Weekly return: {weekly_return*100:.2f}%")
            report.append("")

        # Aggregate execution stats
        total_orders = sum(r.get('order_summary', {}).get('total_orders', 0) for r in daily_reports)
        total_filled = sum(r.get('order_summary', {}).get('filled_orders', 0) for r in daily_reports)
        total_cost = sum(r.get('order_summary', {}).get('total_cost', 0) for r in daily_reports)

        report.append("【Weekly Execution】")
        report.append("")
        report.append(f"  Total orders: {total_orders}")
        report.append(f"  Filled orders: {total_filled}")
        report.append(f"  Fill rate: {total_filled/total_orders*100:.2f}%" if total_orders > 0 else "  Fill rate: N/A")
        report.append(f"  Total transaction cost: ${total_cost:,.2f}")
        report.append("")

        # Risk and drift summary
        risk_violations = sum(1 for r in daily_reports if len(r.get('risk_results', {}).get('violations', [])) > 0)
        drift_detections = sum(1 for r in daily_reports if r.get('drift_results', {}).get('drift_detected', False))

        report.append("【Weekly Risk & Drift】")
        report.append("")
        report.append(f"  Days with risk violations: {risk_violations}")
        report.append(f"  Days with drift detected: {drift_detections}")
        report.append("")

        report.append("=" * 80)

        report_text = "\n".join(report)

        # Save report
        report_file = self.output_dir / 'weekly_reports' / f"{start_date}_to_{end_date}.txt"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, 'w') as f:
            f.write(report_text)

        print(f"\n✅ Weekly summary saved: {report_file}")

        return report_text
