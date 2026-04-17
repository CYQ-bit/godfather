"""
Production Backtester - Comprehensive Portfolio Backtest with Risk Monitoring
Integrates all pipeline components and generates full production-level reports
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime

from signal_processor import SignalProcessor
from risk_model import BarraLiteRiskModel
from optimizer import PortfolioOptimizer
from execution_simulator import ExecutionSimulator


class ProductionBacktester:
    """
    Production-level backtester with comprehensive reporting:
    - Signal processing with sector neutralization
    - Risk factor exposure monitoring
    - Constrained portfolio optimization
    - T+1 execution simulation
    - Multi-dimensional performance analysis
    """

    def __init__(
        self,
        transaction_cost_bps: float = 10.0,
        max_stock_weight: float = 0.10,
        n_stocks: int = 20,
        sector_neutral: bool = True,
        initial_capital: float = 1_000_000.0
    ):
        """
        Args:
            transaction_cost_bps: Transaction cost in basis points
            max_stock_weight: Maximum weight per stock
            n_stocks: Number of stocks to hold
            sector_neutral: Whether to apply sector neutralization
            initial_capital: Initial portfolio capital
        """
        self.transaction_cost_bps = transaction_cost_bps
        self.max_stock_weight = max_stock_weight
        self.n_stocks = n_stocks
        self.sector_neutral = sector_neutral
        self.initial_capital = initial_capital

        # Initialize components
        self.signal_processor = SignalProcessor(sector_col='sector')
        self.risk_model = BarraLiteRiskModel()
        self.optimizer = PortfolioOptimizer(max_stock_weight=max_stock_weight)
        self.executor = ExecutionSimulator(
            transaction_cost_bps=transaction_cost_bps,
            initial_capital=initial_capital
        )

    def run_backtest(
        self,
        predictions: pd.DataFrame,
        price_data: pd.DataFrame,
        stock_data: pd.DataFrame
    ) -> Dict:
        """
        Run full production backtest pipeline

        Args:
            predictions: ML predictions with columns [date, stock_code, prediction, sector]
            price_data: Price data with columns [date, stock_code, close, volume]
            stock_data: Full stock data for risk model (includes market_cap)

        Returns:
            Dictionary containing all backtest results and reports
        """
        print("=" * 80)
        print("【Phase P.1 — Production-Level Portfolio Backtest】")
        print("=" * 80)
        print()

        # Step 1: Process signals
        print("Step 1: Processing signals (sector neutralization)...")
        processed_signals = self.signal_processor.process(
            predictions,
            sector_neutral=self.sector_neutral
        )
        signal_stats = self.signal_processor.get_signal_stats(processed_signals)
        print(f"  Signal stats: mean={signal_stats['mean']:.4f}, std={signal_stats['std']:.4f}")
        print(f"  Sector neutrality: {signal_stats.get('sector_mean_abs', 0):.6f}")
        print()

        # Step 2: Construct portfolios
        print("Step 2: Constructing portfolios (constrained optimization)...")
        target_weights_list = []
        for date, group in processed_signals.groupby('date'):
            weights = self.optimizer.optimize(
                group,
                method='top_n',
                n_stocks=self.n_stocks,
                sector_col='sector'
            )

            for stock_code, weight in weights.items():
                target_weights_list.append({
                    'date': date,
                    'stock_code': stock_code,
                    'weight': weight
                })

        target_weights = pd.DataFrame(target_weights_list)
        print(f"  Generated {len(target_weights['date'].unique())} rebalance dates")
        print()

        # Step 3: Calculate risk exposures
        print("Step 3: Calculating risk factor exposures...")
        try:
            risk_exposures = self._calculate_risk_exposures(
                target_weights,
                stock_data
            )
            print(f"  Calculated exposures for {len(risk_exposures)} rebalance dates")
        except Exception as e:
            print(f"  WARNING: Risk exposure calculation failed: {e}")
            print(f"  Continuing without risk exposures...")
            risk_exposures = pd.DataFrame()
        print()

        # Step 4: Simulate execution
        print("Step 4: Simulating T+1 execution with transaction costs...")
        portfolio_returns, trade_records = self.executor.simulate(
            target_weights,
            price_data
        )
        print(f"  Simulated {len(portfolio_returns)} trading days")
        print(f"  Executed {len(trade_records)} trades")
        print()

        # Step 5: Generate comprehensive report
        print("Step 5: Generating comprehensive report...")
        report = self._generate_report(
            portfolio_returns,
            trade_records,
            target_weights,
            processed_signals,
            risk_exposures
        )
        print()

        return {
            'portfolio_returns': portfolio_returns,
            'trade_records': trade_records,
            'target_weights': target_weights,
            'processed_signals': processed_signals,
            'risk_exposures': risk_exposures,
            'report': report
        }

    def _calculate_risk_exposures(
        self,
        target_weights: pd.DataFrame,
        stock_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Calculate portfolio risk factor exposures over time"""
        exposures_list = []

        for date in target_weights['date'].unique():
            # Get weights for this date
            weights = target_weights[target_weights['date'] == date].copy()
            weights_series = pd.Series(
                weights['weight'].values,
                index=weights['stock_code']
            )

            # Calculate factor exposures
            factor_exp = self.risk_model.calculate_factor_exposures(
                stock_data,
                date
            )

            if len(factor_exp) == 0:
                continue

            # Calculate portfolio exposure
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
        """Generate comprehensive backtest report"""
        report = []
        report.append("=" * 80)
        report.append("【Production-Level Backtest Report】")
        report.append("=" * 80)
        report.append("")

        # Section A: Overall Performance
        report.append("=" * 80)
        report.append("【A. 整体表现 Overall Performance】")
        report.append("=" * 80)
        report.append("")

        metrics = self.executor.calculate_performance_metrics(portfolio_returns)
        report.append(f"回测区间: {portfolio_returns['date'].min()} to {portfolio_returns['date'].max()}")
        report.append(f"交易天数: {metrics.get('n_days', 0):.0f} ({metrics.get('n_years', 0):.2f} years)")
        report.append("")
        report.append(f"总收益率: {metrics.get('total_return', 0) * 100:.2f}%")
        report.append(f"年化收益: {metrics.get('annualized_return', 0) * 100:.2f}%")
        report.append(f"年化波动: {metrics.get('volatility', 0) * 100:.2f}%")
        report.append(f"Sharpe比率: {metrics.get('sharpe_ratio', 0):.4f}")
        report.append(f"最大回撤: {metrics.get('max_drawdown', 0) * 100:.2f}%")
        report.append(f"胜率: {metrics.get('win_rate', 0) * 100:.2f}%")
        report.append("")

        # Section B: Yearly Performance
        report.append("=" * 80)
        report.append("【B. 逐年表现 Yearly Performance】")
        report.append("=" * 80)
        report.append("")

        yearly_stats = self._calculate_yearly_performance(portfolio_returns)
        for year, stats in yearly_stats.items():
            report.append(f"{year}:")
            report.append(f"  收益率: {stats['return'] * 100:>8.2f}%")
            report.append(f"  波动率: {stats['volatility'] * 100:>8.2f}%")
            report.append(f"  Sharpe: {stats['sharpe']:>8.4f}")
            report.append(f"  最大回撤: {stats['max_dd'] * 100:>8.2f}%")
        report.append("")

        # Section C: Risk Factor Exposure
        report.append("=" * 80)
        report.append("【C. 风险因子暴露 Risk Factor Exposure】")
        report.append("=" * 80)
        report.append("")

        if len(risk_exposures) > 0:
            for factor in ['beta', 'volatility', 'momentum', 'liquidity', 'size']:
                if factor in risk_exposures.columns:
                    mean_exp = risk_exposures[factor].mean()
                    std_exp = risk_exposures[factor].std()
                    report.append(f"{factor:>12s}: {mean_exp:>8.4f} ± {std_exp:.4f}")
        report.append("")

        # Section D: Turnover and Costs
        report.append("=" * 80)
        report.append("【D. 换手率与成本 Turnover and Transaction Costs】")
        report.append("=" * 80)
        report.append("")

        avg_turnover = metrics.get('avg_turnover', 0)
        total_cost = trade_records['cost'].sum() if len(trade_records) > 0 else 0
        cost_pct = (total_cost / self.initial_capital) * 100

        report.append(f"平均换手率: {avg_turnover * 100:.2f}%")
        report.append(f"总交易成本: ${total_cost:,.2f} ({cost_pct:.2f}% of initial capital)")
        report.append(f"成本设定: {self.transaction_cost_bps} bps")
        report.append("")

        # Section E: Sector Distribution
        report.append("=" * 80)
        report.append("【E. 行业分布 Sector Distribution】")
        report.append("=" * 80)
        report.append("")

        sector_stats = self._calculate_sector_distribution(target_weights, processed_signals)
        for sector, weight in sector_stats.items():
            report.append(f"{sector:>20s}: {weight * 100:>6.2f}%")
        report.append("")

        # Section F: Position Concentration
        report.append("=" * 80)
        report.append("【F. 持仓集中度 Position Concentration】")
        report.append("=" * 80)
        report.append("")

        concentration_stats = self._calculate_concentration(target_weights)
        report.append(f"平均持仓数: {concentration_stats['avg_n_stocks']:.1f}")
        report.append(f"最大个股权重: {concentration_stats['max_stock_weight'] * 100:.2f}%")
        report.append(f"Top 5权重占比: {concentration_stats['top5_weight'] * 100:.2f}%")
        report.append(f"HHI指数: {concentration_stats['hhi']:.4f}")
        report.append("")

        # Section G: Final Conclusions
        report.append("=" * 80)
        report.append("【G. 最终结论 Final Conclusions】")
        report.append("=" * 80)
        report.append("")

        sharpe = metrics.get('sharpe_ratio', 0)
        max_dd = metrics.get('max_drawdown', 0)

        if sharpe > 1.0 and max_dd > -0.20:
            report.append("✅ 策略表现优秀 (Sharpe > 1.0, MaxDD > -20%)")
        elif sharpe > 0.5:
            report.append("⚠️  策略表现中等 (Sharpe > 0.5)")
        else:
            report.append("❌ 策略表现不佳 (Sharpe < 0.5)")

        report.append("")
        report.append("生产就绪检查:")
        report.append(f"  {'✅' if sharpe > 0.5 else '❌'} Sharpe > 0.5")
        report.append(f"  {'✅' if max_dd > -0.30 else '❌'} MaxDD > -30%")
        report.append(f"  {'✅' if avg_turnover < 2.0 else '❌'} Turnover < 200%")
        report.append(f"  {'✅' if concentration_stats['max_stock_weight'] <= self.max_stock_weight else '❌'} Max weight <= {self.max_stock_weight * 100}%")
        report.append("")

        report.append("=" * 80)
        report.append("✅ Phase P.1 完成！")
        report.append("=" * 80)

        return "\n".join(report)

    def _calculate_yearly_performance(self, portfolio_returns: pd.DataFrame) -> Dict:
        """Calculate performance metrics by year"""
        df = portfolio_returns.copy()
        df['year'] = pd.to_datetime(df['date']).dt.year

        yearly_stats = {}
        for year, group in df.groupby('year'):
            returns = group['return'].dropna()

            if len(returns) == 0:
                continue

            total_return = (1 + returns).prod() - 1
            volatility = returns.std() * np.sqrt(252)
            sharpe = (total_return * 252 / len(returns)) / volatility if volatility > 0 else 0

            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_dd = drawdown.min()

            yearly_stats[year] = {
                'return': total_return,
                'volatility': volatility,
                'sharpe': sharpe,
                'max_dd': max_dd
            }

        return yearly_stats

    def _calculate_sector_distribution(
        self,
        target_weights: pd.DataFrame,
        processed_signals: pd.DataFrame
    ) -> Dict[str, float]:
        """Calculate average sector weights"""
        merged = target_weights.merge(
            processed_signals[['date', 'stock_code', 'sector']],
            on=['date', 'stock_code'],
            how='left'
        )

        sector_weights = merged.groupby(['date', 'sector'])['weight'].sum()
        avg_sector_weights = sector_weights.groupby('sector').mean()

        return avg_sector_weights.to_dict()

    def _calculate_concentration(self, target_weights: pd.DataFrame) -> Dict:
        """Calculate position concentration metrics"""
        stats = {}

        # Average number of stocks
        n_stocks_per_date = target_weights.groupby('date')['stock_code'].count()
        stats['avg_n_stocks'] = n_stocks_per_date.mean()

        # Maximum stock weight
        stats['max_stock_weight'] = target_weights['weight'].max()

        # Top 5 weight concentration
        top5_weights = target_weights.groupby('date').apply(
            lambda x: x.nlargest(5, 'weight')['weight'].sum()
        )
        stats['top5_weight'] = top5_weights.mean()

        # HHI (Herfindahl-Hirschman Index)
        hhi_per_date = target_weights.groupby('date').apply(
            lambda x: (x['weight'] ** 2).sum()
        )
        stats['hhi'] = hhi_per_date.mean()

        return stats
