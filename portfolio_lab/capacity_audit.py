"""
Capacity & Market Impact Cost Audit Module - Phase P.1.3
Determine strategy scalability and capacity limits
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple


class CapacityAuditor:
    """
    Capacity analysis tools:
    - Calculate ADV (Average Daily Volume)
    - Compute position size as % of ADV
    - Apply market impact cost model
    - Test multiple capital tiers
    - Determine capacity limits
    """

    def __init__(self):
        self.capacity_results = {}

    def calculate_adv(
        self,
        price_data: pd.DataFrame,
        window: int = 20
    ) -> pd.DataFrame:
        """
        Calculate Average Daily Volume (ADV) for each stock

        Args:
            price_data: DataFrame with [date, stock_code, close, volume]
            window: Rolling window for ADV calculation (default 20 days)

        Returns:
            DataFrame with [date, stock_code, adv, dollar_volume]
        """
        print("=" * 80)
        print("【Calculating Average Daily Volume (ADV)】")
        print("=" * 80)
        print()

        # Calculate dollar volume
        price_data = price_data.copy()
        price_data['dollar_volume'] = price_data['close'] * price_data['volume']

        # Calculate rolling ADV
        price_data = price_data.sort_values(['stock_code', 'date'])
        price_data['adv'] = price_data.groupby('stock_code')['dollar_volume'].transform(
            lambda x: x.rolling(window, min_periods=1).mean()
        )

        print(f"ADV calculated with {window}-day rolling window")
        print(f"Total records: {len(price_data)}")
        print(f"Mean ADV: ${price_data['adv'].mean():,.0f}")
        print(f"Median ADV: ${price_data['adv'].median():,.0f}")
        print()

        return price_data[['date', 'stock_code', 'adv', 'dollar_volume']]

    def calculate_market_impact_cost(
        self,
        trade_value: float,
        adv: float,
        model: str = 'sqrt'
    ) -> float:
        """
        Calculate market impact cost using specified model

        Args:
            trade_value: Dollar value of trade
            adv: Average Daily Volume in dollars
            model: 'sqrt' (square root law) or 'linear'

        Returns:
            Impact cost as fraction of trade value
        """
        if adv <= 0:
            return 0.0

        participation_rate = trade_value / adv

        if model == 'sqrt':
            # Square root law: impact ∝ sqrt(participation_rate)
            # Typical coefficient: 0.1 for liquid stocks
            impact_bps = 10.0 * np.sqrt(participation_rate)
        elif model == 'linear':
            # Linear model: impact ∝ participation_rate
            impact_bps = 100.0 * participation_rate
        else:
            raise ValueError(f"Unknown model: {model}")

        # Cap at 500 bps (5%)
        impact_bps = min(impact_bps, 500.0)

        return impact_bps / 10000.0  # Convert bps to fraction

    def run_capacity_test(
        self,
        predictions: pd.DataFrame,
        price_data: pd.DataFrame,
        stock_data: pd.DataFrame,
        backtester_class,
        capital_tiers: list = [1_000_000, 10_000_000, 50_000_000]
    ) -> Dict:
        """
        Test strategy performance at different capital levels

        Args:
            predictions: Predictions DataFrame
            price_data: Price data with volume
            stock_data: Stock metadata
            backtester_class: Backtester class
            capital_tiers: List of capital amounts to test

        Returns:
            Dictionary with capacity test results
        """
        print("=" * 80)
        print("【Capacity Test】")
        print("=" * 80)
        print()
        print(f"Testing capital tiers: {[f'${c:,}' for c in capital_tiers]}")
        print()

        # Calculate ADV
        adv_data = self.calculate_adv(price_data)

        results = []

        for capital in capital_tiers:
            print(f"\n{'=' * 80}")
            print(f"【Testing Capital: ${capital:,}】")
            print(f"{'=' * 80}\n")

            # Run baseline backtest
            backtester = backtester_class(
                transaction_cost_bps=10.0,
                max_stock_weight=0.10,
                n_stocks=20,
                sector_neutral=True,
                initial_capital=capital,
                rebalance_frequency=5,
                turnover_penalty=0.0,
                hold_buffer_percentile=0.50
            )

            result = backtester.run_backtest(
                predictions,
                price_data,
                stock_data,
                verbose=False
            )

            # Calculate impact costs
            trade_records = result['trade_records']
            if len(trade_records) > 0:
                # Merge with ADV data
                trade_records = trade_records.merge(
                    adv_data,
                    left_on=['execution_date', 'stock_code'],
                    right_on=['date', 'stock_code'],
                    how='left'
                )

                # Calculate impact cost for each trade
                trade_records['trade_value'] = trade_records['shares'].abs() * trade_records['price']
                trade_records['impact_cost'] = trade_records.apply(
                    lambda row: self.calculate_market_impact_cost(
                        row['trade_value'],
                        row['adv'],
                        model='sqrt'
                    ) * row['trade_value'],
                    axis=1
                )

                # Calculate participation rates
                trade_records['participation_rate'] = trade_records['trade_value'] / trade_records['adv']

                total_impact_cost = trade_records['impact_cost'].sum()
                avg_participation = trade_records['participation_rate'].mean()
                max_participation = trade_records['participation_rate'].max()
            else:
                total_impact_cost = 0
                avg_participation = 0
                max_participation = 0

            # Adjust returns for impact cost
            metrics = result['metrics']
            baseline_return = metrics.get('annualized_return', 0)
            baseline_sharpe = metrics.get('sharpe_ratio', 0)

            # Impact cost as % of capital
            impact_cost_pct = total_impact_cost / capital

            # Adjusted return (subtract impact cost)
            adjusted_return = baseline_return - impact_cost_pct

            # Adjusted Sharpe (approximate)
            volatility = metrics.get('volatility', 0)
            adjusted_sharpe = adjusted_return / volatility if volatility > 0 else 0

            # Store results
            capacity_result = {
                'capital': capital,
                'baseline_return': baseline_return,
                'baseline_sharpe': baseline_sharpe,
                'impact_cost_pct': impact_cost_pct,
                'adjusted_return': adjusted_return,
                'adjusted_sharpe': adjusted_sharpe,
                'avg_participation': avg_participation,
                'max_participation': max_participation,
                'max_drawdown': metrics.get('max_drawdown', 0),
                'avg_turnover': metrics.get('avg_turnover', 0)
            }

            results.append(capacity_result)

            print(f"Baseline Performance:")
            print(f"  Annual Return: {baseline_return*100:.2f}%")
            print(f"  Sharpe Ratio: {baseline_sharpe:.4f}")
            print()
            print(f"Market Impact Analysis:")
            print(f"  Total Impact Cost: ${total_impact_cost:,.0f} ({impact_cost_pct*100:.2f}% of capital)")
            print(f"  Avg Participation Rate: {avg_participation*100:.2f}%")
            print(f"  Max Participation Rate: {max_participation*100:.2f}%")
            print()
            print(f"Adjusted Performance:")
            print(f"  Adjusted Return: {adjusted_return*100:.2f}%")
            print(f"  Adjusted Sharpe: {adjusted_sharpe:.4f}")
            print(f"  Sharpe Degradation: {(adjusted_sharpe - baseline_sharpe):.4f}")
            print()

        # Create results DataFrame
        results_df = pd.DataFrame(results)

        # Print summary
        self._print_capacity_summary(results_df)

        return {
            'results': results_df,
            'adv_data': adv_data
        }

    def _print_capacity_summary(self, results_df: pd.DataFrame):
        """Print capacity test summary"""
        print("\n" + "=" * 80)
        print("【Capacity Test Summary】")
        print("=" * 80)
        print()

        print(f"{'Capital':<15} {'Baseline':<12} {'Impact':<12} {'Adjusted':<12} {'Sharpe':<10} {'Degradation':<12}")
        print(f"{'':15} {'Sharpe':<12} {'Cost %':<12} {'Sharpe':<12} {'Loss':<10} {'%':<12}")
        print("-" * 80)

        baseline_sharpe = results_df.iloc[0]['baseline_sharpe']

        for _, row in results_df.iterrows():
            capital_str = f"${row['capital']/1e6:.0f}M" if row['capital'] >= 1e6 else f"${row['capital']/1e3:.0f}K"
            degradation = row['adjusted_sharpe'] - row['baseline_sharpe']
            degradation_pct = (degradation / baseline_sharpe * 100) if baseline_sharpe != 0 else 0

            print(f"{capital_str:<15} {row['baseline_sharpe']:>11.4f} {row['impact_cost_pct']*100:>11.2f}% "
                  f"{row['adjusted_sharpe']:>11.4f} {degradation:>9.4f} {degradation_pct:>11.1f}%")

        print()

        # Determine capacity limit
        print("【Capacity Limit Assessment】")
        print()

        # Find where Sharpe degrades by more than 20%
        for _, row in results_df.iterrows():
            sharpe_loss_pct = ((row['adjusted_sharpe'] - baseline_sharpe) / baseline_sharpe * 100)
            if sharpe_loss_pct < -20:
                capital_str = f"${row['capital']/1e6:.0f}M" if row['capital'] >= 1e6 else f"${row['capital']/1e3:.0f}K"
                print(f"⚠️  Capacity limit reached at {capital_str}")
                print(f"   Sharpe degradation: {sharpe_loss_pct:.1f}%")
                print(f"   Impact cost: {row['impact_cost_pct']*100:.2f}% of capital")
                break
        else:
            max_capital = results_df.iloc[-1]['capital']
            capital_str = f"${max_capital/1e6:.0f}M" if max_capital >= 1e6 else f"${max_capital/1e3:.0f}K"
            print(f"✅ Strategy scales well up to {capital_str}")
            print(f"   Max Sharpe degradation: {((results_df.iloc[-1]['adjusted_sharpe'] - baseline_sharpe) / baseline_sharpe * 100):.1f}%")

        print()

        # Participation rate assessment
        print("【Participation Rate Assessment】")
        print()

        max_participation = results_df['max_participation'].max()
        avg_participation = results_df['avg_participation'].max()

        print(f"Max Participation Rate: {max_participation*100:.2f}%")
        print(f"Avg Participation Rate: {avg_participation*100:.2f}%")
        print()

        if max_participation < 0.05:
            print("✅ EXCELLENT: Max participation < 5%")
            print("   Minimal market impact expected")
        elif max_participation < 0.10:
            print("✅ GOOD: Max participation < 10%")
            print("   Moderate market impact")
        elif max_participation < 0.20:
            print("⚠️  MODERATE: Max participation < 20%")
            print("   Significant market impact")
        else:
            print("❌ HIGH: Max participation > 20%")
            print("   Severe market impact - capacity constrained")

        print()
