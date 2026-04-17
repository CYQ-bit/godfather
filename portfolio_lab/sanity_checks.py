"""
Phase P.1.2.1 Sanity Check Audit Module
Comprehensive auditing tools to validate P.1.2 results
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta


class SanityCheckAuditor:
    """
    Audit tools for validating backtest results:
    - Manual inspection of rebalance days
    - Placebo test with randomized signals
    - T+2 lag test
    - Long/Short leg attribution
    """

    def __init__(self):
        self.audit_results = {}

    def manual_inspection_rebalance_days(
        self,
        portfolio_returns: pd.DataFrame,
        trade_records: pd.DataFrame,
        target_weights: pd.DataFrame,
        price_data: pd.DataFrame,
        n_samples: int = 5
    ) -> List[Dict]:
        """
        Manually inspect N rebalance days to verify execution logic

        Returns detailed audit cases showing:
        - Signal date vs trade date
        - Pre/post trade positions
        - Actual trade prices
        - Transaction costs
        - Holding period PnL
        """
        print("=" * 80)
        print("【Audit A: Manual Inspection of Rebalance Days】")
        print("=" * 80)
        print()

        # Get all rebalance dates
        rebalance_dates = sorted(target_weights['date'].unique())

        if len(rebalance_dates) < n_samples:
            n_samples = len(rebalance_dates)

        # Sample dates: early, middle, late, best day, worst day
        indices = [
            0,  # First rebalance
            len(rebalance_dates) // 4,  # Early-mid
            len(rebalance_dates) // 2,  # Middle
            3 * len(rebalance_dates) // 4,  # Late-mid
            len(rebalance_dates) - 1  # Last rebalance
        ]

        # Find best and worst return days
        if len(portfolio_returns) > 0 and 'return' in portfolio_returns.columns:
            best_day = portfolio_returns.loc[portfolio_returns['return'].idxmax(), 'date']
            worst_day = portfolio_returns.loc[portfolio_returns['return'].idxmin(), 'date']

            # Replace middle samples with best/worst if available
            if len(indices) >= 3:
                indices[2] = rebalance_dates.index(min(rebalance_dates, key=lambda x: abs((x - best_day).days)))
            if len(indices) >= 4:
                indices[3] = rebalance_dates.index(min(rebalance_dates, key=lambda x: abs((x - worst_day).days)))

        sampled_dates = [rebalance_dates[i] for i in indices[:n_samples]]

        audit_cases = []

        for idx, signal_date in enumerate(sampled_dates):
            print(f"\n{'=' * 80}")
            print(f"【Audit Case #{idx + 1}: Signal Date = {signal_date.strftime('%Y-%m-%d')}】")
            print(f"{'=' * 80}\n")

            case = self._inspect_single_rebalance_day(
                signal_date,
                portfolio_returns,
                trade_records,
                target_weights,
                price_data
            )

            audit_cases.append(case)

        return audit_cases

    def _inspect_single_rebalance_day(
        self,
        signal_date: pd.Timestamp,
        portfolio_returns: pd.DataFrame,
        trade_records: pd.DataFrame,
        target_weights: pd.DataFrame,
        price_data: pd.DataFrame
    ) -> Dict:
        """Inspect a single rebalance day in detail"""

        case = {
            'signal_date': signal_date,
            'execution_date': None,
            'pre_trade_positions': [],
            'target_weights': [],
            'trades_executed': [],
            'post_trade_positions': [],
            'holding_period_pnl': None
        }

        # 1. Signal date
        print(f"1. Signal Date: {signal_date.strftime('%Y-%m-%d')}")

        # 2. Trade date (should be t+1)
        trades_on_signal = trade_records[trade_records['signal_date'] == signal_date]
        if len(trades_on_signal) > 0:
            execution_date = trades_on_signal['execution_date'].iloc[0]
            case['execution_date'] = execution_date
            print(f"2. Trade Date: {execution_date.strftime('%Y-%m-%d')} (T+1 = {(execution_date - signal_date).days} days)")
        else:
            print(f"2. Trade Date: No trades found for this signal date")
            return case

        # 3. Pre-trade positions
        print(f"\n3. Pre-Trade Positions:")
        if len(trades_on_signal) > 0:
            # Get sell trades (these were pre-trade positions)
            pre_positions = trades_on_signal[trades_on_signal['action'] == 'sell'][['stock_code', 'shares']].copy()
            if len(pre_positions) > 0:
                print(f"   Holdings: {len(pre_positions)} stocks")
                for _, row in pre_positions.head(5).iterrows():
                    print(f"   - {row['stock_code']}: {row['shares']:.0f} shares")
                if len(pre_positions) > 5:
                    print(f"   ... and {len(pre_positions) - 5} more")
                case['pre_trade_positions'] = pre_positions.to_dict('records')
            else:
                print(f"   No pre-trade positions (first rebalance)")
        else:
            print(f"   No pre-trade positions")

        # 4. Target weights
        print(f"\n4. Target Weights:")
        targets = target_weights[target_weights['date'] == signal_date]
        if len(targets) > 0:
            print(f"   Target portfolio: {len(targets)} stocks")
            for _, row in targets.head(5).iterrows():
                print(f"   - {row['stock_code']}: {row['weight']*100:.2f}%")
            if len(targets) > 5:
                print(f"   ... and {len(targets) - 5} more")
            case['target_weights'] = targets.to_dict('records')

        # 5. Actual trade prices (must be t+1 close)
        print(f"\n5. Actual Trade Prices (must be T+1 close):")
        if len(trades_on_signal) > 0:
            print(f"   Executed {len(trades_on_signal)} trades")
            for _, row in trades_on_signal.head(5).iterrows():
                direction = row['action'].upper()
                print(f"   - {direction} {row['stock_code']}: {row['shares']:.0f} shares @ ${row['price']:.2f}")
            if len(trades_on_signal) > 5:
                print(f"   ... and {len(trades_on_signal) - 5} more")
            case['trades_executed'] = trades_on_signal.to_dict('records')

        # 6. Transaction costs
        print(f"\n6. Transaction Costs:")
        total_cost = trades_on_signal['cost'].sum()
        total_volume = (trades_on_signal['shares'].abs() * trades_on_signal['price']).sum()
        print(f"   Total cost: ${total_cost:,.2f}")
        print(f"   Total volume: ${total_volume:,.2f}")
        if total_volume > 0:
            print(f"   Cost as % of volume: {total_cost/total_volume*100:.2f}%")
        case['total_cost'] = total_cost

        # 7. Post-trade positions
        print(f"\n7. Post-Trade Positions:")
        # Get buy trades (these are the new positions)
        post_positions = trades_on_signal[trades_on_signal['action'] == 'buy'][['stock_code', 'shares']].copy()
        if len(post_positions) > 0:
            print(f"   Holdings: {len(post_positions)} stocks")
            for _, row in post_positions.head(5).iterrows():
                print(f"   - {row['stock_code']}: {row['shares']:.0f} shares")
            if len(post_positions) > 5:
                print(f"   ... and {len(post_positions) - 5} more")
            case['post_trade_positions'] = post_positions.to_dict('records')
        else:
            print(f"   No post-trade positions")

        # 8. Holding period PnL
        print(f"\n8. Holding Period PnL:")
        next_returns = portfolio_returns[portfolio_returns['date'] > execution_date].head(5)
        if len(next_returns) > 0:
            cumulative_return = (1 + next_returns['return']).prod() - 1
            print(f"   Next 5 days cumulative return: {cumulative_return*100:.2f}%")
            case['holding_period_pnl'] = cumulative_return
        else:
            print(f"   No subsequent returns available")

        print()
        return case

    def placebo_test(
        self,
        predictions: pd.DataFrame,
        price_data: pd.DataFrame,
        stock_data: pd.DataFrame,
        backtester,
        seed: int = 42
    ) -> Dict:
        """
        Placebo test: randomize prediction scores within each rebalance day

        If placebo results are still good, there's likely an implementation bug.
        If placebo results are near zero or much worse, real results are more credible.
        """
        print("\n" + "=" * 80)
        print("【Audit B: Placebo Test (Randomized Signals)】")
        print("=" * 80)
        print()
        print("Randomizing prediction scores within each date...")
        print("This breaks the symbol-prediction relationship while keeping distribution.")
        print()

        # Create placebo predictions
        np.random.seed(seed)
        placebo_preds = predictions.copy()

        # Shuffle predictions within each date
        for date in placebo_preds['date'].unique():
            mask = placebo_preds['date'] == date
            scores = placebo_preds.loc[mask, 'prediction'].values
            np.random.shuffle(scores)
            placebo_preds.loc[mask, 'prediction'] = scores

        print("Running backtest with randomized signals...")
        result = backtester.run_backtest(
            placebo_preds,
            price_data,
            stock_data,
            verbose=False
        )

        metrics = result['metrics']

        print("\n【Placebo Test Results】")
        print(f"Annual Return: {metrics.get('annualized_return', 0) * 100:.2f}%")
        print(f"Volatility: {metrics.get('volatility', 0) * 100:.2f}%")
        print(f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.4f}")
        print(f"Max Drawdown: {metrics.get('max_drawdown', 0) * 100:.2f}%")
        print(f"Win Rate: {metrics.get('win_rate', 0) * 100:.2f}%")
        print(f"Avg Turnover: {metrics.get('avg_turnover', 0) * 100:.2f}%")
        print()

        return {
            'metrics': metrics,
            'result': result
        }

    def t2_lag_test(
        self,
        predictions: pd.DataFrame,
        price_data: pd.DataFrame,
        stock_data: pd.DataFrame,
        backtester_t1,
        backtester_t2
    ) -> Dict:
        """
        T+2 lag test: compare T+1 vs T+2 execution delay

        If T+2 is similar or better than T+1, there may be a timing issue.
        If T+2 is slightly worse, that's expected signal decay.
        If T+2 collapses, signal decays too fast for production.
        """
        print("\n" + "=" * 80)
        print("【Audit C: T+2 Lag Test (Execution Delay)】")
        print("=" * 80)
        print()

        # Run T+1 baseline
        print("Running T+1 baseline (signal at t, trade at t+1 close)...")
        result_t1 = backtester_t1.run_backtest(
            predictions,
            price_data,
            stock_data,
            verbose=False
        )
        metrics_t1 = result_t1['metrics']

        # Run T+2 test
        print("Running T+2 test (signal at t, trade at t+2 close)...")
        result_t2 = backtester_t2.run_backtest(
            predictions,
            price_data,
            stock_data,
            verbose=False
        )
        metrics_t2 = result_t2['metrics']

        print("\n【T+1 vs T+2 Comparison】")
        print(f"\nT+1 Execution:")
        print(f"  Annual Return: {metrics_t1.get('annualized_return', 0) * 100:.2f}%")
        print(f"  Sharpe Ratio: {metrics_t1.get('sharpe_ratio', 0):.4f}")
        print(f"  Max Drawdown: {metrics_t1.get('max_drawdown', 0) * 100:.2f}%")
        print(f"  Win Rate: {metrics_t1.get('win_rate', 0) * 100:.2f}%")

        print(f"\nT+2 Execution:")
        print(f"  Annual Return: {metrics_t2.get('annualized_return', 0) * 100:.2f}%")
        print(f"  Sharpe Ratio: {metrics_t2.get('sharpe_ratio', 0):.4f}")
        print(f"  Max Drawdown: {metrics_t2.get('max_drawdown', 0) * 100:.2f}%")
        print(f"  Win Rate: {metrics_t2.get('win_rate', 0) * 100:.2f}%")

        # Calculate degradation
        sharpe_decay = (metrics_t2.get('sharpe_ratio', 0) - metrics_t1.get('sharpe_ratio', 0)) / max(metrics_t1.get('sharpe_ratio', 1), 0.01) * 100
        return_decay = (metrics_t2.get('annualized_return', 0) - metrics_t1.get('annualized_return', 0)) / max(metrics_t1.get('annualized_return', 1), 0.01) * 100

        print(f"\nPerformance Decay:")
        print(f"  Sharpe decay: {sharpe_decay:+.1f}%")
        print(f"  Return decay: {return_decay:+.1f}%")
        print()

        return {
            't1_metrics': metrics_t1,
            't2_metrics': metrics_t2,
            'sharpe_decay_pct': sharpe_decay,
            'return_decay_pct': return_decay
        }

    def long_short_attribution(
        self,
        portfolio_returns: pd.DataFrame,
        trade_records: pd.DataFrame,
        target_weights: pd.DataFrame,
        price_data: pd.DataFrame
    ) -> Dict:
        """
        Long/Short leg attribution

        Separate performance of long and short legs to understand
        where alpha is coming from.
        """
        print("\n" + "=" * 80)
        print("【Audit D: Long/Short Leg Attribution】")
        print("=" * 80)
        print()

        # This is a simplified attribution
        # In a real implementation, we'd need to track long/short positions separately

        print("Note: Current implementation uses long-only portfolio.")
        print("For true long-short attribution, we need separate long/short tracking.")
        print()

        # Calculate basic stats
        if len(portfolio_returns) > 0:
            total_return = (1 + portfolio_returns['return']).prod() - 1
            annual_return = (1 + total_return) ** (252 / len(portfolio_returns)) - 1
            volatility = portfolio_returns['return'].std() * np.sqrt(252)
            sharpe = annual_return / volatility if volatility > 0 else 0

            print(f"【Combined Portfolio】")
            print(f"  Total Return: {total_return * 100:.2f}%")
            print(f"  Annual Return: {annual_return * 100:.2f}%")
            print(f"  Volatility: {volatility * 100:.2f}%")
            print(f"  Sharpe Ratio: {sharpe:.4f}")
            print()

        return {
            'combined_metrics': {
                'annual_return': annual_return,
                'volatility': volatility,
                'sharpe': sharpe
            }
        }
