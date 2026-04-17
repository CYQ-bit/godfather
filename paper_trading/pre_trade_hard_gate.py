"""
Pre-trade Hard Gate - Godfather V9.0 PT.4
Block invalid orders before execution
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple


class PreTradeHardGate:
    """Pre-trade validation gate"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.gate_dir = self.output_dir / 'pretrade'
        self.gate_dir.mkdir(parents=True, exist_ok=True)

        # Hard limits
        self.max_single_stock_weight = 0.10
        self.max_sector_weight = 0.30
        self.max_gross_exposure = 1.00
        self.min_net_exposure = 0.90
        self.max_net_exposure = 1.00
        self.max_daily_turnover = 1.00
        self.min_cash_buffer = 0.0

        print(f"Initializing PreTradeHardGate (Godfather V9.0 - PT.4)...")
        print(f"  Output directory: {self.gate_dir}")

    def validate_orders(
        self,
        date: str,
        orders: List[Dict],
        current_cash: float,
        current_holdings: Dict,
        portfolio_value: float,
        market_data: Dict,
        tradable_symbols: set
    ) -> Tuple[str, List[str], Dict]:
        """
        Validate orders before execution

        Returns:
            (status, block_reasons, audit_trail)
            status: PASS / WARN / BLOCK
        """
        block_reasons = []
        warnings = []
        audit_trail = {
            'timestamp': datetime.now().isoformat(),
            'date': date,
            'total_orders': len(orders),
            'checks': []
        }

        # Check 1: Cash sufficiency
        buy_notional = sum(o['notional'] for o in orders if o['side'] == 'BUY')
        sell_proceeds = sum(o['notional'] for o in orders if o['side'] == 'SELL')
        available_cash = current_cash + sell_proceeds

        if buy_notional > available_cash:
            block_reasons.append(f"Insufficient cash: need ${buy_notional:,.2f}, have ${available_cash:,.2f}")

        audit_trail['checks'].append({
            'check': 'cash_sufficiency',
            'status': 'PASS' if buy_notional <= available_cash else 'BLOCK',
            'buy_notional': buy_notional,
            'available_cash': available_cash
        })

        # Check 2: Duplicate orders
        order_keys = [(o['symbol'], o['side']) for o in orders]
        if len(order_keys) != len(set(order_keys)):
            block_reasons.append("Duplicate orders detected")

        audit_trail['checks'].append({
            'check': 'duplicate_orders',
            'status': 'PASS' if len(order_keys) == len(set(order_keys)) else 'BLOCK'
        })

        # Check 3: Missing prices
        missing_prices = []
        for order in orders:
            symbol = order['symbol']
            if symbol not in market_data or market_data[symbol].get('close') is None:
                missing_prices.append(symbol)

        if len(missing_prices) > 0:
            block_reasons.append(f"Missing prices: {missing_prices}")

        audit_trail['checks'].append({
            'check': 'missing_prices',
            'status': 'PASS' if len(missing_prices) == 0 else 'BLOCK',
            'missing_symbols': missing_prices
        })

        # Check 4: Tradability
        untradable = []
        for order in orders:
            symbol = order['symbol']
            if symbol not in tradable_symbols:
                untradable.append(symbol)

        if len(untradable) > 0:
            block_reasons.append(f"Untradable symbols: {untradable}")

        audit_trail['checks'].append({
            'check': 'tradability',
            'status': 'PASS' if len(untradable) == 0 else 'BLOCK',
            'untradable_symbols': untradable
        })

        # Check 5: Order payload completeness
        incomplete_orders = []
        for i, order in enumerate(orders):
            required_fields = ['symbol', 'side', 'quantity', 'notional']
            missing_fields = [f for f in required_fields if f not in order or order[f] is None]
            if len(missing_fields) > 0:
                incomplete_orders.append({'order_idx': i, 'missing_fields': missing_fields})

        if len(incomplete_orders) > 0:
            block_reasons.append(f"Incomplete orders: {len(incomplete_orders)}")

        audit_trail['checks'].append({
            'check': 'payload_completeness',
            'status': 'PASS' if len(incomplete_orders) == 0 else 'BLOCK',
            'incomplete_count': len(incomplete_orders)
        })

        # Check 6: Turnover limit
        total_turnover = sum(abs(o['notional']) for o in orders) / portfolio_value if portfolio_value > 0 else 0
        if total_turnover > self.max_daily_turnover:
            block_reasons.append(f"Turnover {total_turnover*100:.1f}% exceeds limit {self.max_daily_turnover*100:.1f}%")

        audit_trail['checks'].append({
            'check': 'turnover_limit',
            'status': 'PASS' if total_turnover <= self.max_daily_turnover else 'BLOCK',
            'turnover': total_turnover,
            'limit': self.max_daily_turnover
        })

        # Check 7: Negative cash projection
        projected_cash = current_cash + sell_proceeds - buy_notional
        if projected_cash < self.min_cash_buffer:
            block_reasons.append(f"Projected negative cash: ${projected_cash:,.2f}")

        audit_trail['checks'].append({
            'check': 'negative_cash_projection',
            'status': 'PASS' if projected_cash >= self.min_cash_buffer else 'BLOCK',
            'projected_cash': projected_cash
        })

        # Determine final status
        if len(block_reasons) > 0:
            status = 'BLOCK'
        elif len(warnings) > 0:
            status = 'WARN'
        else:
            status = 'PASS'

        audit_trail['final_status'] = status
        audit_trail['block_reasons'] = block_reasons
        audit_trail['warnings'] = warnings

        # Save audit trail
        audit_file = self.gate_dir / f'{date}_gate.json'
        with open(audit_file, 'w') as f:
            json.dump(audit_trail, f, indent=2)

        return status, block_reasons, audit_trail
