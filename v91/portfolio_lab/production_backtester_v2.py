"""
Production Backtester V2 - Phase P.1.2
Enhanced with multi-frequency rebalancing and turnover control experiments
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from signal_processor import SignalProcessor
from risk_model import BarraLiteRiskModel
from optimizer_v2 import TurnoverAwareOptimizer
from execution_simulator import ExecutionSimulator


class ProductionBacktesterV2:
    """
    Enhanced backtester for Phase P.1.2 experiments:
    - Multi-frequency rebalancing (daily, 5d, 10d)
    - Turnover-aware optimization
    - Hold buffer mechanisms
    - Bucket width experiments
    """

    def __init__(
        self,
        transaction_cost_bps: float = 10.0,
        max_stock_weight: float = 0.10,
        n_stocks: int = 20,
        sector_neutral: bool = True,
        initial_capital: float = 1_000_000.0,
        rebalance_frequency: int = 1,
        turnover_penalty: float = 0.0,
        hold_buffer_percentile: float = 0.0
    ):
        """
        Args:
            transaction_cost_bps: Transaction cost in basis points
            max_stock_weight: Maximum weight per stock
            n_stocks: Number of stocks to hold
            sector_neutral: Whether to apply sector neutralization
            initial_capital: Initial portfolio capital
            rebalance_frequency: Rebalance every N trading days (1=daily)
            turnover_penalty: Lambda for turnover penalty
            hold_buffer_percentile: Buffer percentile for holding positions
        """
        self.transaction_cost_bps = transaction_cost_bps
        self.max_stock_weight = max_stock_weight
        self.n_stocks = n_stocks
        self.sector_neutral = sector_neutral
        self.initial_capital = initial_capital
        self.rebalance_frequency = rebalance_frequency
        self.turnover_penalty = turnover_penalty
        self.hold_buffer_percentile = hold_buffer_percentile

        # Initialize components
        self.signal_processor = SignalProcessor(sector_col='sector')
        self.risk_model = BarraLiteRiskModel()
        self.optimizer = TurnoverAwareOptimizer(
            max_stock_weight=max_stock_weight,
            turnover_penalty=turnover_penalty,
            hold_buffer_percentile=hold_buffer_percentile
        )
        self.executor = ExecutionSimulator(
            transaction_cost_bps=transaction_cost_bps,
            initial_capital=initial_capital
        )

    def run_backtest(
        self,
        predictions: pd.DataFrame,
        price_data: pd.DataFrame,
        stock_data: pd.DataFrame,
        verbose: bool = True
    ) -> Dict:
        """
        Run backtest with current configuration

        Args:
            predictions: ML predictions
            price_data: Price data
            stock_data: Full stock data
            verbose: Whether to print progress

        Returns:
            Dictionary with results
        """
        if verbose:
            print("=" * 80)
            print(f"【Backtest Configuration】")
            print("=" * 80)
            print(f"Rebalance frequency: Every {self.rebalance_frequency} day(s)")
            print(f"Turnover penalty: {self.turnover_penalty}")
            print(f"Hold buffer: {self.hold_buffer_percentile * 100:.0f}%")
            print(f"Number of stocks: {self.n_stocks}")
            print(f"Sector neutral: {self.sector_neutral}")
            print()

        # Step 1: Process signals
        if verbose:
            print("Step 1: Processing signals...")
        processed_signals = self.signal_processor.process(
            predictions,
            sector_neutral=self.sector_neutral
        )
        if verbose:
            signal_stats = self.signal_processor.get_signal_stats(processed_signals)
            print(f"  Signal stats: mean={signal_stats['mean']:.4f}, std={signal_stats['std']:.4f}")
            print()

        # Step 2: Construct portfolios with frequency control
        if verbose:
            print("Step 2: Constructing portfolios...")
        target_weights_list = []
        previous_weights = None

        unique_dates = sorted(processed_signals['date'].unique())
        rebalance_dates = unique_dates[::self.rebalance_frequency]

        for date in rebalance_dates:
            group = processed_signals[processed_signals['date'] == date]

            weights = self.optimizer.optimize(
                group,
                method='top_n_with_buffer',
                n_stocks=self.n_stocks,
                sector_col='sector',
                previous_weights=previous_weights
            )

            for stock_code, weight in weights.items():
                target_weights_list.append({
                    'date': date,
                    'stock_code': stock_code,
                    'weight': weight
                })

            previous_weights = weights

        target_weights = pd.DataFrame(target_weights_list)
        if verbose:
            print(f"  Generated {len(target_weights['date'].unique())} rebalance dates")
            print()

        # Step 3: Calculate risk exposures (skip if fails)
        if verbose:
            print("Step 3: Calculating risk factor exposures...")
        try:
            risk_exposures = self._calculate_risk_exposures(
                target_weights,
                stock_data
            )
            if verbose:
                print(f"  Calculated exposures for {len(risk_exposures)} rebalance dates")
        except Exception as e:
            if verbose:
                print(f"  WARNING: Risk exposure calculation failed: {str(e)[:100]}")
                print(f"  Continuing without risk exposures...")
            risk_exposures = pd.DataFrame()
        if verbose:
            print()

        # Step 4: Simulate execution
        if verbose:
            print("Step 4: Simulating T+1 execution...")
        portfolio_returns, trade_records = self.executor.simulate(
            target_weights,
            price_data
        )
        if verbose:
            print(f"  Simulated {len(portfolio_returns)} trading days")
            print(f"  Executed {len(trade_records)} trades")
            print()

        # Step 5: Generate report
        if verbose:
            print("Step 5: Generating report...")
        report = self._generate_report(
            portfolio_returns,
            trade_records,
            target_weights,
            processed_signals,
            risk_exposures
        )
        if verbose:
            print()

        return {
            'portfolio_returns': portfolio_returns,
            'trade_records': trade_records,
            'target_weights': target_weights,
            'processed_signals': processed_signals,
            'risk_exposures': risk_exposures,
            'report': report,
            'metrics': self.executor.calculate_performance_metrics(portfolio_returns)
        }

    def _calculate_risk_exposures(
        self,
        target_weights: pd.DataFrame,
        stock_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Calculate portfolio risk factor exposures"""
        exposures_list = []

        for date in target_weights['date'].unique():
            weights = target_weights[target_weights['date'] == date].copy()
            weights_series = pd.Series(
                weights['weight'].values,
                index=weights['stock_code']
            )

            factor_exp = self.risk_model.calculate_factor_exposures(
                stock_data,
                date
            )

            if len(factor_exp) == 0:
                continue

            portfolio_exp = self.risk_model.calculate_portfolio_exposure(
                weights_series,
                factor_exp
            )

            portfolio_exp['date'] = date
            exposures_list.append(portfolio_exp)

        return pd.DataFrame(exposures_list)

    def _generate_report(
        self,
        portfolio_returns: pd.DataFrame,
        trade_records: pd.DataFrame,
        target_weights: pd.DataFrame,
        processed_signals: pd.DataFrame,
        risk_exposures: pd.DataFrame
    ) -> str:
        """Generate backtest report"""
        report = []

        metrics = self.executor.calculate_performance_metrics(portfolio_returns)

        report.append(f"Rebalance Frequency: Every {self.rebalance_frequency} day(s)")
        report.append(f"Turnover Penalty: {self.turnover_penalty}")
        report.append(f"Hold Buffer: {self.hold_buffer_percentile * 100:.0f}%")
        report.append(f"Number of Stocks: {self.n_stocks}")
        report.append("")
        report.append(f"Annual Return: {metrics.get('annualized_return', 0) * 100:.2f}%")
        report.append(f"Volatility: {metrics.get('volatility', 0) * 100:.2f}%")
        report.append(f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.4f}")
        report.append(f"Max Drawdown: {metrics.get('max_drawdown', 0) * 100:.2f}%")
        report.append(f"Win Rate: {metrics.get('win_rate', 0) * 100:.2f}%")
        report.append(f"Avg Turnover: {metrics.get('avg_turnover', 0) * 100:.2f}%")

        if len(trade_records) > 0:
            total_cost = trade_records['cost'].sum()
            cost_pct = (total_cost / self.initial_capital) * 100
            report.append(f"Total Cost: ${total_cost:,.2f} ({cost_pct:.2f}% of capital)")

        return "\n".join(report)
