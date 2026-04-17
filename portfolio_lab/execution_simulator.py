"""
Execution Simulator - T+1 Close Execution with Transaction Costs
Simulates realistic portfolio execution with T+1 delay and costs
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple


class ExecutionSimulator:
    """
    Simulates portfolio execution with:
    - T+1 execution delay (signal on day T, execute at close of day T+1)
    - Transaction costs (configurable bps)
    - Position tracking
    - Return calculation
    """

    def __init__(
        self,
        transaction_cost_bps: float = 10.0,
        initial_capital: float = 1_000_000.0
    ):
        """
        Args:
            transaction_cost_bps: Transaction cost in basis points (default 10 bps)
            initial_capital: Initial portfolio capital
        """
        self.transaction_cost_bps = transaction_cost_bps
        self.initial_capital = initial_capital
        self.transaction_cost_rate = transaction_cost_bps / 10000.0

    def simulate(
        self,
        target_weights: pd.DataFrame,
        price_data: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Simulate portfolio execution over time

        Args:
            target_weights: DataFrame with columns [date, stock_code, weight]
                            date = signal generation date (T)
            price_data: DataFrame with columns [date, stock_code, close]
                        date = trading date

        Returns:
            Tuple of (portfolio_returns, trade_records)
            - portfolio_returns: DataFrame with daily portfolio metrics
            - trade_records: DataFrame with all executed trades
        """
        # Sort data
        target_weights = target_weights.sort_values('date')
        price_data = price_data.sort_values(['stock_code', 'date'])

        # Get unique rebalance dates
        rebalance_dates = sorted(target_weights['date'].unique())

        # Initialize tracking
        current_positions = {}  # {stock_code: shares}
        current_cash = self.initial_capital
        portfolio_value = self.initial_capital

        portfolio_records = []
        trade_records = []

        for i, signal_date in enumerate(rebalance_dates):
            # T+1 execution: execute at close of next trading day
            execution_date = self._get_next_trading_day(signal_date, price_data)

            if execution_date is None:
                continue

            # Get target weights for this rebalance
            target_wts = target_weights[target_weights['date'] == signal_date].copy()

            # Get execution prices
            exec_prices = price_data[price_data['date'] == execution_date].copy()
            exec_prices = exec_prices.set_index('stock_code')['close']

            # Calculate current portfolio value before rebalance
            portfolio_value = self._calculate_portfolio_value(
                current_positions,
                current_cash,
                exec_prices
            )

            # Execute rebalance
            trades, new_positions, new_cash = self._execute_rebalance(
                target_wts,
                current_positions,
                portfolio_value,
                exec_prices
            )

            # Record trades
            for trade in trades:
                trade['signal_date'] = signal_date
                trade['execution_date'] = execution_date
                trade_records.append(trade)

            # Update positions
            current_positions = new_positions
            current_cash = new_cash

            # Calculate portfolio value after rebalance
            portfolio_value_after = self._calculate_portfolio_value(
                current_positions,
                current_cash,
                exec_prices
            )

            # Record portfolio state
            portfolio_records.append({
                'date': execution_date,
                'portfolio_value': portfolio_value_after,
                'cash': current_cash,
                'n_positions': len(current_positions),
                'turnover': sum(abs(t['value']) for t in trades) / portfolio_value if portfolio_value > 0 else 0
            })

            # Mark-to-market on non-rebalance days
            if i < len(rebalance_dates) - 1:
                next_signal_date = rebalance_dates[i + 1]
                next_execution_date = self._get_next_trading_day(next_signal_date, price_data)

                # Only process if next_execution_date is valid
                if next_execution_date is not None:
                    # Get all trading days between current and next rebalance
                    trading_days = price_data[
                        (price_data['date'] > execution_date) &
                        (price_data['date'] < next_execution_date)
                    ]['date'].unique()

                    for trading_day in sorted(trading_days):
                        mtm_prices = price_data[price_data['date'] == trading_day].copy()
                        mtm_prices = mtm_prices.set_index('stock_code')['close']

                        mtm_value = self._calculate_portfolio_value(
                            current_positions,
                            current_cash,
                            mtm_prices
                        )

                        portfolio_records.append({
                            'date': trading_day,
                            'portfolio_value': mtm_value,
                            'cash': current_cash,
                            'n_positions': len(current_positions),
                            'turnover': 0.0
                        })

        # Convert to DataFrames
        portfolio_df = pd.DataFrame(portfolio_records).sort_values('date')
        trades_df = pd.DataFrame(trade_records) if trade_records else pd.DataFrame()

        # Calculate returns
        portfolio_df['return'] = portfolio_df['portfolio_value'].pct_change()
        portfolio_df['cumulative_return'] = (1 + portfolio_df['return']).cumprod() - 1

        return portfolio_df, trades_df

    def _get_next_trading_day(
        self,
        signal_date: pd.Timestamp,
        price_data: pd.DataFrame
    ) -> pd.Timestamp:
        """Get next available trading day after signal date (T+1)"""
        future_dates = price_data[price_data['date'] > signal_date]['date'].unique()

        if len(future_dates) == 0:
            return None

        return sorted(future_dates)[0]

    def _calculate_portfolio_value(
        self,
        positions: Dict[str, float],
        cash: float,
        prices: pd.Series
    ) -> float:
        """Calculate total portfolio value"""
        position_value = 0.0

        for stock_code, shares in positions.items():
            if stock_code in prices.index:
                position_value += shares * prices[stock_code]

        return position_value + cash

    def _execute_rebalance(
        self,
        target_weights: pd.DataFrame,
        current_positions: Dict[str, float],
        portfolio_value: float,
        prices: pd.Series
    ) -> Tuple[List[Dict], Dict[str, float], float]:
        """
        Execute rebalance from current positions to target weights

        Returns:
            Tuple of (trades, new_positions, new_cash)
        """
        trades = []
        new_positions = {}

        # If no current positions (first rebalance), start with full portfolio value as cash
        if len(current_positions) == 0:
            cash = portfolio_value
        else:
            cash = 0.0

        # Liquidate all current positions
        for stock_code, shares in current_positions.items():
            if stock_code in prices.index and shares > 0:
                price = prices[stock_code]
                gross_value = shares * price
                cost = gross_value * self.transaction_cost_rate
                net_value = gross_value - cost

                cash += net_value

                trades.append({
                    'stock_code': stock_code,
                    'action': 'sell',
                    'shares': shares,
                    'price': price,
                    'value': -gross_value,
                    'cost': cost
                })

        # Buy target positions
        for _, row in target_weights.iterrows():
            stock_code = row['stock_code']
            target_weight = row['weight']

            if stock_code not in prices.index:
                continue

            price = prices[stock_code]
            target_value = portfolio_value * target_weight
            cost = target_value * self.transaction_cost_rate
            net_value = target_value + cost

            if net_value > cash:
                # Not enough cash, scale down
                net_value = cash
                target_value = net_value / (1 + self.transaction_cost_rate)
                cost = net_value - target_value

            shares = target_value / price
            cash -= net_value

            new_positions[stock_code] = shares

            trades.append({
                'stock_code': stock_code,
                'action': 'buy',
                'shares': shares,
                'price': price,
                'value': target_value,
                'cost': cost
            })

        return trades, new_positions, cash

    def calculate_performance_metrics(
        self,
        portfolio_returns: pd.DataFrame
    ) -> Dict:
        """
        Calculate portfolio performance metrics

        Args:
            portfolio_returns: DataFrame from simulate()

        Returns:
            Dictionary of performance metrics
        """
        returns = portfolio_returns['return'].dropna()

        if len(returns) == 0:
            return {}

        # Annualization factor (assuming daily data)
        n_days = len(returns)
        n_years = n_days / 252.0

        # Total return
        total_return = portfolio_returns['cumulative_return'].iloc[-1]

        # Annualized return
        annualized_return = (1 + total_return) ** (1 / n_years) - 1

        # Volatility
        volatility = returns.std() * np.sqrt(252)

        # Sharpe ratio (assuming 0% risk-free rate)
        sharpe = annualized_return / volatility if volatility > 0 else 0

        # Maximum drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()

        # Win rate
        win_rate = (returns > 0).sum() / len(returns)

        # Average turnover
        avg_turnover = portfolio_returns['turnover'].mean()

        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'avg_turnover': avg_turnover,
            'n_days': n_days,
            'n_years': n_years
        }
