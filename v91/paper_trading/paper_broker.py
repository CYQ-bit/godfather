"""
Paper Broker Module - Godfather V9.0 Phase PT.1.1a
Simulate order lifecycle with cash constraint and proper accounting
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import uuid


class PaperBroker:
    """
    Paper broker for simulating order execution with proper accounting

    Godfather V9.0 PT.1.1a Features:
    - Pre-trade cash constraint
    - Order creation and tracking
    - Simulated fills at T+1 close
    - Mark-to-market accounting
    - Transaction cost modeling
    - Order status management
    - No real broker connection
    """

    def __init__(
        self,
        transaction_cost_bps: float = 10.0,
        initial_capital: float = 1_000_000
    ):
        """
        Initialize paper broker

        Args:
            transaction_cost_bps: Transaction cost in basis points
            initial_capital: Initial capital
        """
        self.transaction_cost_bps = transaction_cost_bps
        self.initial_capital = initial_capital
        self.cash = initial_capital

        self.orders = []
        self.fills = []
        self.positions = {}  # {symbol: shares}
        self.position_costs = {}  # {symbol: avg_cost}

        self.realized_pnl = 0.0
        self.total_transaction_costs = 0.0

        # Cash constraint tracking
        self.cash_constraint_triggered = False
        self.cash_constraint_log = []

        print(f"Initializing PaperBroker (Godfather V9.0 - PT.1.1a)...")
        print(f"  Initial capital: ${self.initial_capital:,.0f}")
        print(f"  Transaction cost: {self.transaction_cost_bps} bps")
        print(f"  Mark-to-market accounting: ON")
        print(f"  Pre-trade cash constraint: ON")

    def mark_to_market(self, prices: pd.DataFrame) -> Dict:
        """
        Mark positions to market and calculate portfolio value

        Args:
            prices: Current prices [stock_code, close]

        Returns:
            Dictionary with accounting summary
        """
        holdings_value = 0.0
        unrealized_pnl = 0.0

        for symbol, shares in self.positions.items():
            if shares == 0:
                continue

            price_row = prices[prices['stock_code'] == symbol]
            if len(price_row) == 0:
                # Use last known cost if price not available
                avg_cost = self.position_costs.get(symbol, 0)
                holdings_value += shares * avg_cost
                continue

            current_price = price_row['close'].iloc[0]
            position_value = shares * current_price
            holdings_value += position_value

            # Calculate unrealized PnL
            avg_cost = self.position_costs.get(symbol, current_price)
            unrealized_pnl += (current_price - avg_cost) * shares

        total_value = self.cash + holdings_value

        return {
            'cash': self.cash,
            'holdings_value': holdings_value,
            'total_value': total_value,
            'unrealized_pnl': unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'total_pnl': unrealized_pnl + self.realized_pnl,
            'num_positions': len([s for s, shares in self.positions.items() if shares > 0])
        }

    def create_orders(
        self,
        target_portfolio: pd.DataFrame,
        signal_date: str,
        intended_trade_date: str,
        reference_prices: pd.DataFrame
    ) -> List[Dict]:
        """
        Create orders from target portfolio with cash constraint

        Args:
            target_portfolio: Target portfolio with [stock_code, target_weight]
            signal_date: Signal generation date
            intended_trade_date: Intended trade date (T+1)
            reference_prices: Reference prices for sizing

        Returns:
            List of order dictionaries
        """
        print(f"\n{'='*80}")
        print(f"【Creating Orders - Godfather V9.0 PT.1.1a】")
        print(f"{'='*80}\n")
        print(f"Signal date: {signal_date}")
        print(f"Intended trade date: {intended_trade_date}")

        # Calculate current portfolio value (cash + holdings)
        accounting = self.mark_to_market(reference_prices)
        portfolio_value = accounting['total_value']

        print(f"\nPortfolio Accounting:")
        print(f"  Cash: ${accounting['cash']:,.2f}")
        print(f"  Holdings value: ${accounting['holdings_value']:,.2f}")
        print(f"  Total portfolio value: ${portfolio_value:,.2f}")

        # Step 1: Create SELL orders first (to free up cash)
        sell_orders = []
        current_symbols = set(self.positions.keys())
        target_symbols = set(target_portfolio['stock_code'].values)
        symbols_to_close = current_symbols - target_symbols

        estimated_sell_proceeds = 0.0

        for symbol in symbols_to_close:
            shares = self.positions[symbol]
            if shares == 0:
                continue

            # Get reference price
            ref_price_row = reference_prices[reference_prices['stock_code'] == symbol]
            if len(ref_price_row) == 0:
                print(f"⚠️  Skipping close of {symbol}: No price available")
                continue

            ref_price = ref_price_row['close'].iloc[0]
            notional = shares * ref_price
            cost = notional * (self.transaction_cost_bps / 10000.0)
            estimated_sell_proceeds += (notional - cost)

            order = {
                'order_id': str(uuid.uuid4()),
                'timestamp_created': datetime.now(),
                'signal_date': pd.to_datetime(signal_date),
                'intended_trade_date': pd.to_datetime(intended_trade_date),
                'stock_code': symbol,
                'side': 'SELL',
                'target_weight': 0.0,
                'target_shares': abs(shares),
                'reference_price': ref_price,
                'status': 'CREATED'
            }

            sell_orders.append(order)

        # Step 2: Calculate available cash for buys
        available_cash = self.cash + estimated_sell_proceeds

        print(f"\n【Cash Constraint Check - PT.1.1a】")
        print(f"  Pre-trade cash: ${self.cash:,.2f}")
        print(f"  Estimated sell proceeds: ${estimated_sell_proceeds:,.2f}")
        print(f"  Available cash for buys: ${available_cash:,.2f}")

        # Step 3: Create BUY orders with cash constraint
        target_with_prices = target_portfolio.merge(
            reference_prices[['stock_code', 'close']],
            left_on='stock_code',
            right_on='stock_code',
            how='left'
        )

        # Calculate theoretical target
        target_with_prices['theoretical_dollar'] = target_with_prices['target_weight'] * portfolio_value
        target_with_prices['theoretical_shares'] = (
            target_with_prices['theoretical_dollar'] / target_with_prices['close']
        ).fillna(0).astype(int)

        # Calculate required buy notional
        buy_orders_data = []
        total_buy_notional = 0.0
        total_buy_cost_estimate = 0.0

        for _, row in target_with_prices.iterrows():
            if pd.isna(row['close']) or row['close'] <= 0:
                continue

            current_shares = self.positions.get(row['stock_code'], 0)
            target_shares = row['theoretical_shares']
            shares_to_trade = target_shares - current_shares

            if shares_to_trade > 0:  # BUY
                notional = shares_to_trade * row['close']
                cost = notional * (self.transaction_cost_bps / 10000.0)
                total_buy_notional += notional
                total_buy_cost_estimate += cost

                buy_orders_data.append({
                    'stock_code': row['stock_code'],
                    'target_weight': row['target_weight'],
                    'shares': shares_to_trade,
                    'price': row['close'],
                    'notional': notional,
                    'cost': cost,
                    'score': row.get('sector_neutral_score', 0)
                })
            elif shares_to_trade < 0:  # Additional SELL
                order = {
                    'order_id': str(uuid.uuid4()),
                    'timestamp_created': datetime.now(),
                    'signal_date': pd.to_datetime(signal_date),
                    'intended_trade_date': pd.to_datetime(intended_trade_date),
                    'stock_code': row['stock_code'],
                    'side': 'SELL',
                    'target_weight': row['target_weight'],
                    'target_shares': abs(shares_to_trade),
                    'reference_price': row['close'],
                    'status': 'CREATED'
                }
                sell_orders.append(order)

        total_buy_required = total_buy_notional + total_buy_cost_estimate

        print(f"  Target buy notional: ${total_buy_notional:,.2f}")
        print(f"  Estimated buy costs: ${total_buy_cost_estimate:,.2f}")
        print(f"  Total buy required: ${total_buy_required:,.2f}")

        # Step 4: Apply cash constraint if needed
        buy_orders = []
        scaling_factor = 1.0

        if total_buy_required > available_cash:
            # Cash constraint triggered - scale down buys
            scaling_factor = available_cash / total_buy_required
            self.cash_constraint_triggered = True

            print(f"\n  ⚠️  CASH CONSTRAINT TRIGGERED")
            print(f"  Scaling factor: {scaling_factor:.4f} ({scaling_factor*100:.2f}%)")

            self.cash_constraint_log.append({
                'date': signal_date,
                'available_cash': available_cash,
                'required_cash': total_buy_required,
                'scaling_factor': scaling_factor
            })
        else:
            print(f"  ✅ Cash constraint: OK (sufficient cash)")

        # Create scaled buy orders
        scaled_buy_notional = 0.0
        for buy_data in buy_orders_data:
            scaled_shares = int(buy_data['shares'] * scaling_factor)
            if scaled_shares == 0:
                continue

            scaled_notional = scaled_shares * buy_data['price']
            scaled_cost = scaled_notional * (self.transaction_cost_bps / 10000.0)
            scaled_buy_notional += scaled_notional

            order = {
                'order_id': str(uuid.uuid4()),
                'timestamp_created': datetime.now(),
                'signal_date': pd.to_datetime(signal_date),
                'intended_trade_date': pd.to_datetime(intended_trade_date),
                'stock_code': buy_data['stock_code'],
                'side': 'BUY',
                'target_weight': buy_data['target_weight'],
                'target_shares': scaled_shares,
                'reference_price': buy_data['price'],
                'status': 'CREATED',
                'theoretical_shares': buy_data['shares'],
                'scaling_factor': scaling_factor
            }

            buy_orders.append(order)

        if scaling_factor < 1.0:
            print(f"  Scaled buy notional: ${scaled_buy_notional:,.2f}")
            print(f"  Leftover cash (estimated): ${available_cash - scaled_buy_notional:,.2f}")

        # Combine all orders
        orders = sell_orders + buy_orders

        # Add to broker's order list
        self.orders.extend(orders)

        print(f"\n✅ Created {len(orders)} orders")
        print(f"   SELL orders: {len(sell_orders)}")
        print(f"   BUY orders: {len(buy_orders)}")
        if scaling_factor < 1.0:
            print(f"   Cash constraint: ACTIVE (scaled to {scaling_factor*100:.1f}%)")

        return orders

    def simulate_fills(
        self,
        orders: List[Dict],
        fill_prices: pd.DataFrame,
        fill_date: str
    ) -> List[Dict]:
        """
        Simulate order fills at T+1 close with proper accounting

        Args:
            orders: List of orders to fill
            fill_prices: Fill prices [stock_code, close]
            fill_date: Fill date

        Returns:
            List of fill dictionaries
        """
        print(f"\n{'='*80}")
        print(f"【Simulating Order Fills - Godfather V9.0 PT.1.1a】")
        print(f"{'='*80}\n")
        print(f"Fill date: {fill_date}")

        fills = []

        # PT.1.1a: Process SELL orders first, then BUY orders
        sell_orders = [o for o in orders if o['side'] == 'SELL']
        buy_orders = [o for o in orders if o['side'] == 'BUY']
        ordered_orders = sell_orders + buy_orders

        print(f"Processing {len(sell_orders)} SELL orders first, then {len(buy_orders)} BUY orders")

        for order in ordered_orders:
            # Get fill price
            price_row = fill_prices[fill_prices['stock_code'] == order['stock_code']]

            if len(price_row) == 0:
                # No price available - mark as FAILED
                order['status'] = 'FAILED'
                order['failure_reason'] = 'NO_PRICE'
                print(f"❌ {order['stock_code']}: No fill price available")
                continue

            fill_price = price_row['close'].iloc[0]

            # Calculate transaction cost
            notional = order['target_shares'] * fill_price
            cost = notional * (self.transaction_cost_bps / 10000.0)

            # Create fill
            fill = {
                'fill_id': str(uuid.uuid4()),
                'order_id': order['order_id'],
                'stock_code': order['stock_code'],
                'side': order['side'],
                'shares': order['target_shares'],
                'fill_price': fill_price,
                'fill_timestamp': pd.to_datetime(fill_date),
                'notional': notional,
                'cost': cost,
                'status': 'FILLED'
            }

            fills.append(fill)
            self.fills.append(fill)

            # Update order status
            order['status'] = 'FILLED'
            order['fill_price'] = fill_price
            order['fill_timestamp'] = pd.to_datetime(fill_date)
            order['cost'] = cost

            # Update positions and accounting
            symbol = order['stock_code']
            current_shares = self.positions.get(symbol, 0)
            current_avg_cost = self.position_costs.get(symbol, 0)

            if order['side'] == 'BUY':
                # PT.1.1a: Check cash constraint at fill time
                required_cash = notional + cost
                if self.cash < required_cash:
                    # Insufficient cash - mark order as FAILED
                    order['status'] = 'FAILED'
                    order['failure_reason'] = 'INSUFFICIENT_CASH'
                    print(f"⚠️  {order['stock_code']}: Insufficient cash (need ${required_cash:,.2f}, have ${self.cash:,.2f})")
                    fills.pop()  # Remove the fill we just added
                    self.fills.pop()
                    continue

                # Buy: update position and avg cost
                new_shares = current_shares + order['target_shares']

                if new_shares > 0:
                    # Calculate new average cost
                    total_cost = (current_shares * current_avg_cost) + (order['target_shares'] * fill_price)
                    new_avg_cost = total_cost / new_shares
                    self.position_costs[symbol] = new_avg_cost

                self.positions[symbol] = new_shares

                # Update cash
                self.cash -= (notional + cost)
                self.total_transaction_costs += cost

            else:  # SELL
                # Sell: realize PnL
                shares_sold = order['target_shares']
                realized_pnl_this_trade = (fill_price - current_avg_cost) * shares_sold
                self.realized_pnl += realized_pnl_this_trade

                # Update position
                new_shares = current_shares - shares_sold
                self.positions[symbol] = new_shares

                if new_shares == 0:
                    # Clear position cost if fully closed
                    self.position_costs.pop(symbol, None)

                # Update cash
                self.cash += (notional - cost)
                self.total_transaction_costs += cost

        print(f"\n✅ Filled {len(fills)} orders")
        print(f"   Total transaction cost: ${sum(f['cost'] for f in fills):,.2f}")
        print(f"   Cash after fills: ${self.cash:,.2f}")
        print(f"   Current positions: {len([s for s, shares in self.positions.items() if shares > 0])}")

        return fills

    def get_current_positions(self) -> pd.DataFrame:
        """
        Get current positions

        Returns:
            DataFrame with [stock_code, shares]
        """
        positions = [
            {'stock_code': symbol, 'shares': shares}
            for symbol, shares in self.positions.items()
            if shares != 0
        ]

        return pd.DataFrame(positions)

    def get_portfolio_value(self, prices: pd.DataFrame) -> float:
        """
        Calculate current portfolio value

        Args:
            prices: Current prices [stock_code, close]

        Returns:
            Total portfolio value
        """
        accounting = self.mark_to_market(prices)
        return accounting['total_value']

    def get_accounting_summary(self, prices: pd.DataFrame) -> Dict:
        """
        Get complete accounting summary

        Args:
            prices: Current prices for mark-to-market

        Returns:
            Dictionary with complete accounting
        """
        accounting = self.mark_to_market(prices)

        return {
            'cash': accounting['cash'],
            'holdings_value': accounting['holdings_value'],
            'total_value': accounting['total_value'],
            'unrealized_pnl': accounting['unrealized_pnl'],
            'realized_pnl': accounting['realized_pnl'],
            'total_pnl': accounting['total_pnl'],
            'total_transaction_costs': self.total_transaction_costs,
            'num_positions': accounting['num_positions'],
            'return_pct': (accounting['total_value'] - self.initial_capital) / self.initial_capital,
            'cash_constraint_triggered': self.cash_constraint_triggered
        }

    def get_order_summary(self) -> Dict:
        """
        Get order summary statistics

        Returns:
            Dictionary with order statistics
        """
        if len(self.orders) == 0:
            return {"status": "No orders"}

        filled_orders = [o for o in self.orders if o['status'] == 'FILLED']
        failed_orders = [o for o in self.orders if o['status'] == 'FAILED']

        return {
            "total_orders": len(self.orders),
            "filled_orders": len(filled_orders),
            "failed_orders": len(failed_orders),
            "fill_rate": len(filled_orders) / len(self.orders) if len(self.orders) > 0 else 0,
            "total_cost": sum(o.get('cost', 0) for o in filled_orders),
            "current_positions": len([s for s, shares in self.positions.items() if shares > 0]),
            "cash": self.cash,
            "cash_constraint_triggered": self.cash_constraint_triggered
        }

    def get_cash_constraint_log(self) -> List[Dict]:
        """
        Get cash constraint log

        Returns:
            List of cash constraint events
        """
        return self.cash_constraint_log
