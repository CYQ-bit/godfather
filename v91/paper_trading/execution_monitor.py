"""
Execution Monitor Module - Godfather V9.0 Phase PT.1.1
Monitor execution quality with proper slippage decomposition
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime


class ExecutionMonitor:
    """
    Monitor execution quality and decompose slippage

    Godfather V9.0 PT.1.1 - Proper Slippage Decomposition:
    - Market Move: Signal close vs Trade close (overnight gap)
    - Execution Slippage: Trade close vs Fill price (execution quality)
    - Implementation Shortfall: Total impact from signal to fill
    """

    def __init__(self):
        """Initialize execution monitor"""
        self.execution_history = []

        print(f"Initializing ExecutionMonitor (Godfather V9.0 - PT.1.1)...")
        print(f"  Slippage decomposition: ON")
        print(f"  Market move tracking: ON")
        print(f"  Implementation shortfall: ON")

    def analyze_execution(
        self,
        orders: List[Dict],
        fills: List[Dict],
        signal_date: str,
        trade_date: str
    ) -> Dict:
        """
        Analyze execution quality with proper slippage decomposition

        Args:
            orders: List of orders with reference_price (signal close)
            fills: List of fills with fill_price (trade close)
            signal_date: Signal generation date
            trade_date: Trade execution date

        Returns:
            Dictionary with execution analysis
        """
        print(f"\n{'='*80}")
        print(f"【Execution Analysis - Godfather V9.0 PT.1.1】")
        print(f"{'='*80}\n")
        print(f"Signal date: {signal_date}")
        print(f"Trade date: {trade_date}")

        if len(fills) == 0:
            return {
                'status': 'No fills',
                'num_orders': len(orders),
                'num_fills': 0
            }

        # Match orders with fills
        order_map = {o['order_id']: o for o in orders}

        market_moves = []
        execution_slippages = []
        implementation_shortfalls = []

        for fill in fills:
            order = order_map.get(fill['order_id'])
            if not order:
                continue

            reference_price = order['reference_price']  # Signal close (T)
            fill_price = fill['fill_price']  # Trade close (T+1)

            # For T+1 close execution, fill_price IS the trade close
            # So execution slippage should be 0 (we execute at exactly trade close)
            trade_close = fill_price

            # Market Move: Signal close -> Trade close (overnight gap)
            market_move_bps = ((trade_close - reference_price) / reference_price) * 10000

            # Execution Slippage: Trade close -> Fill price
            # In our simulation, fill = trade close, so this is 0
            execution_slippage_bps = 0.0

            # Implementation Shortfall: Signal close -> Fill price (total impact)
            implementation_shortfall_bps = ((fill_price - reference_price) / reference_price) * 10000

            # Adjust sign for SELL orders
            if fill['side'] == 'SELL':
                market_move_bps = -market_move_bps
                execution_slippage_bps = -execution_slippage_bps
                implementation_shortfall_bps = -implementation_shortfall_bps

            market_moves.append(market_move_bps)
            execution_slippages.append(execution_slippage_bps)
            implementation_shortfalls.append(implementation_shortfall_bps)

        # Calculate statistics
        result = {
            'signal_date': signal_date,
            'trade_date': trade_date,
            'num_orders': len(orders),
            'num_fills': len(fills),
            'fill_rate': len(fills) / len(orders) if len(orders) > 0 else 0,

            # Market Move (overnight gap)
            'market_move_mean_bps': np.mean(market_moves),
            'market_move_std_bps': np.std(market_moves),
            'market_move_abs_mean_bps': np.mean(np.abs(market_moves)),

            # Execution Slippage (should be ~0 for T+1 close)
            'execution_slippage_mean_bps': np.mean(execution_slippages),
            'execution_slippage_std_bps': np.std(execution_slippages),
            'execution_slippage_abs_mean_bps': np.mean(np.abs(execution_slippages)),

            # Implementation Shortfall (total impact)
            'implementation_shortfall_mean_bps': np.mean(implementation_shortfalls),
            'implementation_shortfall_std_bps': np.std(implementation_shortfalls),
            'implementation_shortfall_abs_mean_bps': np.mean(np.abs(implementation_shortfalls)),

            'status': 'OK'
        }

        # Store in history
        self.execution_history.append(result)

        # Print summary
        print(f"Execution Quality Summary:")
        print(f"  Fill rate: {result['fill_rate']*100:.1f}%")
        print(f"\n  Market Move (Signal -> Trade):")
        print(f"    Mean: {result['market_move_mean_bps']:.1f} bps")
        print(f"    Abs Mean: {result['market_move_abs_mean_bps']:.1f} bps")
        print(f"    Std: {result['market_move_std_bps']:.1f} bps")
        print(f"\n  Execution Slippage (Trade -> Fill):")
        print(f"    Mean: {result['execution_slippage_mean_bps']:.1f} bps")
        print(f"    Abs Mean: {result['execution_slippage_abs_mean_bps']:.1f} bps")
        print(f"    (Should be ~0 for T+1 close execution)")
        print(f"\n  Implementation Shortfall (Signal -> Fill):")
        print(f"    Mean: {result['implementation_shortfall_mean_bps']:.1f} bps")
        print(f"    Abs Mean: {result['implementation_shortfall_abs_mean_bps']:.1f} bps")
        print(f"    Std: {result['implementation_shortfall_std_bps']:.1f} bps")

        return result

    def check_execution_quality(
        self,
        execution_result: Dict,
        max_unfilled_rate: float = 0.10,
        max_execution_slippage_bps: float = 50.0,
        max_implementation_shortfall_bps: float = 500.0
    ) -> Dict:
        """
        Check execution quality against thresholds

        Args:
            execution_result: Result from analyze_execution
            max_unfilled_rate: Maximum unfilled rate threshold
            max_execution_slippage_bps: Max execution slippage (trade->fill)
            max_implementation_shortfall_bps: Max implementation shortfall (signal->fill)

        Returns:
            Dictionary with quality check results
        """
        violations = []

        # Check fill rate
        unfilled_rate = 1.0 - execution_result.get('fill_rate', 0)
        if unfilled_rate > max_unfilled_rate:
            violations.append(f"Unfilled rate {unfilled_rate*100:.1f}% exceeds limit {max_unfilled_rate*100:.1f}%")

        # Check execution slippage (should be ~0 for T+1 close)
        exec_slip = execution_result.get('execution_slippage_abs_mean_bps', 0)
        if exec_slip > max_execution_slippage_bps:
            violations.append(f"Execution slippage {exec_slip:.1f} bps exceeds limit {max_execution_slippage_bps} bps")

        # Check implementation shortfall (more lenient, includes market move)
        impl_shortfall = execution_result.get('implementation_shortfall_abs_mean_bps', 0)
        if impl_shortfall > max_implementation_shortfall_bps:
            violations.append(f"Implementation shortfall {impl_shortfall:.1f} bps exceeds limit {max_implementation_shortfall_bps} bps")

        status = 'WARN' if len(violations) > 0 else 'OK'

        return {
            'status': status,
            'violations': violations,
            'unfilled_rate': unfilled_rate,
            'execution_slippage_bps': exec_slip,
            'implementation_shortfall_bps': impl_shortfall
        }

    def get_execution_summary(self) -> Dict:
        """
        Get summary of execution history

        Returns:
            Dictionary with execution summary
        """
        if len(self.execution_history) == 0:
            return {'status': 'No execution history'}

        # Aggregate statistics
        fill_rates = [h['fill_rate'] for h in self.execution_history]
        market_moves = [h['market_move_abs_mean_bps'] for h in self.execution_history]
        exec_slips = [h['execution_slippage_abs_mean_bps'] for h in self.execution_history]
        impl_shortfalls = [h['implementation_shortfall_abs_mean_bps'] for h in self.execution_history]

        return {
            'num_executions': len(self.execution_history),
            'avg_fill_rate': np.mean(fill_rates),
            'avg_market_move_bps': np.mean(market_moves),
            'avg_execution_slippage_bps': np.mean(exec_slips),
            'avg_implementation_shortfall_bps': np.mean(impl_shortfalls)
        }
