"""
Lag Curve Audit Module - Phase P.1.3
Test signal decay with increasing execution delays
"""
import pandas as pd
import numpy as np
from typing import Dict, List


class LagCurveAuditor:
    """
    Lag curve analysis:
    - Test T+1, T+2, T+3, T+5 execution delays
    - Measure signal decay rate
    - Determine alpha half-life
    - Resolve T+2 anomaly from P.1.2.1
    """

    def __init__(self):
        self.lag_results = {}

    def run_lag_curve_test(
        self,
        predictions: pd.DataFrame,
        price_data: pd.DataFrame,
        stock_data: pd.DataFrame,
        backtester_class,
        lags: List[int] = [1, 2, 3, 5]
    ) -> Dict:
        """
        Run backtest with different execution lags

        Args:
            predictions: Original predictions with [date, stock_code, prediction]
            price_data: Price data
            stock_data: Stock metadata
            backtester_class: Backtester class to instantiate
            lags: List of lag days to test

        Returns:
            Dictionary with lag curve results
        """
        print("=" * 80)
        print("【Lag Curve Analysis】")
        print("=" * 80)
        print()
        print(f"Testing execution lags: {lags}")
        print()

        results = []

        for lag in lags:
            print(f"\n{'=' * 80}")
            print(f"【Testing T+{lag} Execution Lag】")
            print(f"{'=' * 80}\n")

            # Shift predictions backward by (lag - 1) days
            # T+1 = no shift (baseline)
            # T+2 = shift back 1 day
            # T+3 = shift back 2 days
            # etc.
            predictions_shifted = predictions.copy()
            if lag > 1:
                predictions_shifted['date'] = predictions_shifted['date'] - pd.Timedelta(days=lag - 1)
                print(f"Shifted predictions back by {lag - 1} days")
                print(f"Original date range: {predictions['date'].min()} to {predictions['date'].max()}")
                print(f"Shifted date range: {predictions_shifted['date'].min()} to {predictions_shifted['date'].max()}")
                print()

            # Create backtester with P.1.2 optimal config
            backtester = backtester_class(
                transaction_cost_bps=10.0,
                max_stock_weight=0.10,
                n_stocks=20,
                sector_neutral=True,
                initial_capital=1_000_000,
                rebalance_frequency=5,
                turnover_penalty=0.0,
                hold_buffer_percentile=0.50
            )

            # Run backtest
            result = backtester.run_backtest(
                predictions_shifted,
                price_data,
                stock_data,
                verbose=False
            )

            metrics = result['metrics']

            # Store results
            lag_result = {
                'lag': f'T+{lag}',
                'lag_days': lag,
                'annual_return': metrics.get('annualized_return', 0),
                'volatility': metrics.get('volatility', 0),
                'sharpe': metrics.get('sharpe_ratio', 0),
                'max_drawdown': metrics.get('max_drawdown', 0),
                'win_rate': metrics.get('win_rate', 0),
                'avg_turnover': metrics.get('avg_turnover', 0)
            }

            results.append(lag_result)

            print(f"T+{lag} Results:")
            print(f"  Annual Return: {lag_result['annual_return']*100:.2f}%")
            print(f"  Sharpe Ratio: {lag_result['sharpe']:.4f}")
            print(f"  Max Drawdown: {lag_result['max_drawdown']*100:.2f}%")
            print(f"  Win Rate: {lag_result['win_rate']*100:.2f}%")
            print()

        # Create results DataFrame
        results_df = pd.DataFrame(results)

        # Calculate decay metrics
        baseline_sharpe = results_df[results_df['lag_days'] == 1]['sharpe'].iloc[0]

        print("\n" + "=" * 80)
        print("【Lag Curve Summary】")
        print("=" * 80)
        print()
        print(f"{'Lag':<10} {'Return':<12} {'Sharpe':<10} {'Decay %':<12} {'MaxDD':<12}")
        print("-" * 80)

        for _, row in results_df.iterrows():
            decay_pct = ((row['sharpe'] - baseline_sharpe) / baseline_sharpe * 100) if baseline_sharpe != 0 else 0
            print(f"{row['lag']:<10} {row['annual_return']*100:>10.2f}% {row['sharpe']:>9.4f} {decay_pct:>10.1f}% {row['max_drawdown']*100:>10.2f}%")

        print()

        # Analyze decay pattern
        self._analyze_decay_pattern(results_df, baseline_sharpe)

        return {
            'results': results_df,
            'baseline_sharpe': baseline_sharpe
        }

    def _analyze_decay_pattern(self, results_df: pd.DataFrame, baseline_sharpe: float):
        """Analyze signal decay pattern"""
        print("\n" + "=" * 80)
        print("【Signal Decay Analysis】")
        print("=" * 80)
        print()

        # Calculate decay from T+1 to T+2
        t1_sharpe = results_df[results_df['lag_days'] == 1]['sharpe'].iloc[0]
        t2_sharpe = results_df[results_df['lag_days'] == 2]['sharpe'].iloc[0]
        t1_to_t2_decay = ((t2_sharpe - t1_sharpe) / t1_sharpe * 100) if t1_sharpe != 0 else 0

        print(f"T+1 Sharpe: {t1_sharpe:.4f}")
        print(f"T+2 Sharpe: {t2_sharpe:.4f}")
        print(f"T+1 → T+2 Decay: {t1_to_t2_decay:+.1f}%")
        print()

        # Assess T+2 anomaly
        if abs(t1_to_t2_decay) < 5:
            print("⚠️  T+2 ANOMALY CONFIRMED")
            print("   Signal shows minimal decay from T+1 to T+2")
            print("   Possible causes:")
            print("   1. Signal has genuine 2-day persistence")
            print("   2. Implementation bug in lag simulation")
            print("   3. Market microstructure effects")
            print()
        elif t1_to_t2_decay < -10:
            print("✅ NORMAL SIGNAL DECAY")
            print("   Signal decays as expected with execution delay")
            print()
        elif t1_to_t2_decay > 5:
            print("⚠️  REVERSE DECAY (SUSPICIOUS)")
            print("   T+2 performs better than T+1")
            print("   Likely indicates implementation bug")
            print()

        # Calculate half-life
        if len(results_df) >= 3:
            half_sharpe = baseline_sharpe / 2
            print(f"Signal Half-Life Analysis:")
            print(f"  Baseline Sharpe: {baseline_sharpe:.4f}")
            print(f"  Half-Sharpe Target: {half_sharpe:.4f}")

            # Find where Sharpe crosses half-life
            for _, row in results_df.iterrows():
                if row['sharpe'] < half_sharpe:
                    print(f"  Half-life reached at: T+{row['lag_days']}")
                    break
            else:
                print(f"  Half-life not reached within tested lags")
            print()

        # Production tradability assessment
        print("【Production Tradability Assessment】")
        print()

        if t1_to_t2_decay > -20:
            print("✅ GOOD: Signal persists well (< 20% decay)")
            print("   Strategy is robust to execution delays")
            print("   Suitable for production trading")
        elif t1_to_t2_decay > -40:
            print("⚠️  MODERATE: Signal decays moderately (20-40% decay)")
            print("   Execution speed matters")
            print("   Consider faster execution infrastructure")
        else:
            print("❌ POOR: Signal decays rapidly (> 40% decay)")
            print("   Strategy requires ultra-fast execution")
            print("   May not be practical for production")
        print()
