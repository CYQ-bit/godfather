"""
Beta Audit Module - Phase P.1.3
Separate alpha from beta to validate strategy performance
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional


class BetaAuditor:
    """
    Beta auditing tools:
    - Construct market benchmark
    - Calculate strategy beta
    - Create beta-hedged returns
    - Compare sector neutral ON/OFF
    """

    def __init__(self):
        self.audit_results = {}

    def construct_market_benchmark(
        self,
        price_data: pd.DataFrame,
        method: str = 'equal_weight'
    ) -> pd.DataFrame:
        """
        Construct market benchmark from universe

        Args:
            price_data: Price data with [date, stock_code, close]
            method: 'equal_weight' or 'value_weight'

        Returns:
            DataFrame with [date, benchmark_return]
        """
        print("=" * 80)
        print("【Constructing Market Benchmark】")
        print("=" * 80)
        print()
        print(f"Method: {method}")
        print()

        # Calculate daily returns for each stock
        price_data = price_data.sort_values(['stock_code', 'date'])
        price_data['return'] = price_data.groupby('stock_code')['close'].pct_change()

        if method == 'equal_weight':
            # Equal-weight benchmark: average return across all stocks each day
            benchmark = price_data.groupby('date')['return'].mean().reset_index()
            benchmark.columns = ['date', 'benchmark_return']
        else:
            raise ValueError(f"Unsupported method: {method}")

        # Calculate cumulative benchmark
        benchmark['benchmark_cumulative'] = (1 + benchmark['benchmark_return']).cumprod()

        print(f"Benchmark constructed:")
        print(f"  Dates: {len(benchmark)}")
        print(f"  Mean daily return: {benchmark['benchmark_return'].mean()*100:.4f}%")
        print(f"  Daily volatility: {benchmark['benchmark_return'].std()*100:.4f}%")
        print()

        return benchmark

    def calculate_beta(
        self,
        strategy_returns: pd.DataFrame,
        benchmark_returns: pd.DataFrame,
        window: int = 60
    ) -> pd.DataFrame:
        """
        Calculate rolling beta of strategy to benchmark

        Args:
            strategy_returns: DataFrame with [date, return]
            benchmark_returns: DataFrame with [date, benchmark_return]
            window: Rolling window for beta calculation

        Returns:
            DataFrame with [date, beta, correlation]
        """
        print("=" * 80)
        print("【Calculating Strategy Beta】")
        print("=" * 80)
        print()
        print(f"Rolling window: {window} days")
        print()

        # Merge strategy and benchmark returns
        merged = strategy_returns.merge(
            benchmark_returns[['date', 'benchmark_return']],
            on='date',
            how='inner'
        )

        # Calculate overall beta (full period)
        overall_cov = merged['return'].cov(merged['benchmark_return'])
        overall_var = merged['benchmark_return'].var()
        overall_beta = overall_cov / overall_var if overall_var > 0 else np.nan
        overall_corr = merged['return'].corr(merged['benchmark_return'])

        print(f"Overall Statistics:")
        print(f"  Beta: {overall_beta:.4f}")
        print(f"  Correlation: {overall_corr:.4f}")
        print()

        result = merged[['date']].copy()
        result['beta'] = overall_beta
        result['correlation'] = overall_corr

        return result

    def create_beta_hedged_returns(
        self,
        strategy_returns: pd.DataFrame,
        benchmark_returns: pd.DataFrame,
        beta: float
    ) -> pd.DataFrame:
        """
        Create beta-hedged returns

        hedged_return = strategy_return - beta * benchmark_return

        Args:
            strategy_returns: DataFrame with [date, return]
            benchmark_returns: DataFrame with [date, benchmark_return]
            beta: Beta coefficient

        Returns:
            DataFrame with [date, hedged_return]
        """
        print("=" * 80)
        print("【Creating Beta-Hedged Returns】")
        print("=" * 80)
        print()
        print(f"Using beta: {beta:.4f}")
        print()

        # Merge returns
        merged = strategy_returns.merge(
            benchmark_returns[['date', 'benchmark_return']],
            on='date',
            how='inner'
        )

        # Calculate hedged returns
        merged['hedged_return'] = merged['return'] - beta * merged['benchmark_return']

        print(f"Hedged Returns Statistics:")
        print(f"  Mean daily return: {merged['hedged_return'].mean()*100:.4f}%")
        print(f"  Daily volatility: {merged['hedged_return'].std()*100:.4f}%")
        print()

        return merged[['date', 'hedged_return']]

    def compare_performance(
        self,
        strategy_returns: pd.DataFrame,
        benchmark_returns: pd.DataFrame,
        hedged_returns: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        Compare performance metrics across strategy, benchmark, and hedged

        Returns:
            Dictionary with performance metrics
        """
        print("=" * 80)
        print("【Performance Comparison】")
        print("=" * 80)
        print()

        results = {}

        # Strategy metrics
        strategy_metrics = self._calculate_metrics(
            strategy_returns['return'],
            "Strategy (Long-Only)"
        )
        results['strategy'] = strategy_metrics

        # Benchmark metrics
        benchmark_metrics = self._calculate_metrics(
            benchmark_returns['benchmark_return'],
            "Market Benchmark"
        )
        results['benchmark'] = benchmark_metrics

        # Hedged metrics
        if hedged_returns is not None:
            hedged_metrics = self._calculate_metrics(
                hedged_returns['hedged_return'],
                "Beta-Hedged Strategy"
            )
            results['hedged'] = hedged_metrics

        # Print comparison table
        print("\n" + "=" * 80)
        print("【Summary Comparison】")
        print("=" * 80)
        print()

        metrics_names = ['Annual Return', 'Annual Vol', 'Sharpe', 'Max Drawdown', 'Win Rate']
        metrics_keys = ['annual_return', 'annual_vol', 'sharpe', 'max_drawdown', 'win_rate']

        print(f"{'Metric':<20} {'Strategy':<15} {'Benchmark':<15} {'Hedged':<15}")
        print("-" * 80)

        for name, key in zip(metrics_names, metrics_keys):
            strategy_val = results['strategy'].get(key, 0)
            benchmark_val = results['benchmark'].get(key, 0)
            hedged_val = results.get('hedged', {}).get(key, 0) if hedged_returns is not None else 0

            if 'Return' in name or 'Vol' in name or 'Drawdown' in name:
                print(f"{name:<20} {strategy_val*100:>13.2f}% {benchmark_val*100:>13.2f}% {hedged_val*100:>13.2f}%")
            elif 'Rate' in name:
                print(f"{name:<20} {strategy_val*100:>13.2f}% {benchmark_val*100:>13.2f}% {hedged_val*100:>13.2f}%")
            else:
                print(f"{name:<20} {strategy_val:>14.4f} {benchmark_val:>14.4f} {hedged_val:>14.4f}")

        print()

        return results

    def _calculate_metrics(
        self,
        returns: pd.Series,
        label: str
    ) -> Dict:
        """Calculate performance metrics for a return series"""
        print(f"\n{label}:")

        # Remove NaN
        returns = returns.dropna()

        if len(returns) == 0:
            return {}

        # Annual return
        total_return = (1 + returns).prod() - 1
        n_days = len(returns)
        annual_return = (1 + total_return) ** (252 / n_days) - 1

        # Annual volatility
        annual_vol = returns.std() * np.sqrt(252)

        # Sharpe ratio
        sharpe = annual_return / annual_vol if annual_vol > 0 else 0

        # Max drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()

        # Win rate
        win_rate = (returns > 0).sum() / len(returns)

        print(f"  Annual Return: {annual_return*100:.2f}%")
        print(f"  Annual Vol: {annual_vol*100:.2f}%")
        print(f"  Sharpe: {sharpe:.4f}")
        print(f"  Max Drawdown: {max_drawdown*100:.2f}%")
        print(f"  Win Rate: {win_rate*100:.2f}%")

        return {
            'annual_return': annual_return,
            'annual_vol': annual_vol,
            'sharpe': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate
        }
