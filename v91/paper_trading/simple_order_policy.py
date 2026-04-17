"""
Simple Order Policy - Godfather V9.0 PT.4.1
Enforce simplest order semantics for tiny capital mode
"""
from typing import Dict, List, Tuple


class SimpleOrderPolicy:
    """Enforce simple order policy for PT.4.1"""

    def __init__(self):
        # Only allow simplest order types
        self.allowed_order_types = ['MARKET', 'LIMIT']
        self.allowed_tif = ['DAY', 'GTC']
        self.default_order_type = 'LIMIT'
        self.default_tif = 'DAY'

        print("Initializing SimpleOrderPolicy (Godfather V9.0 - PT.4.1)...")
        print(f"  Allowed order types: {self.allowed_order_types}")
        print(f"  Allowed TIF: {self.allowed_tif}")
        print(f"  Default: {self.default_order_type} / {self.default_tif}")

    def validate_order(self, order: Dict) -> Tuple[bool, str]:
        """
        Validate order against simple policy

        Returns:
            (is_valid, reason)
        """
        # Check order type
        order_type = order.get('order_type', self.default_order_type)
        if order_type not in self.allowed_order_types:
            return False, f"Order type {order_type} not allowed. Use {self.allowed_order_types}"

        # Check TIF
        tif = order.get('tif', self.default_tif)
        if tif not in self.allowed_tif:
            return False, f"TIF {tif} not allowed. Use {self.allowed_tif}"

        # No complex execution algorithms
        if 'algo' in order or 'execution_strategy' in order:
            return False, "Complex execution algorithms not allowed in PT.4.1"

        # No order splitting
        if 'split' in order or 'child_orders' in order:
            return False, "Order splitting not allowed in PT.4.1"

        return True, "OK"

    def simplify_order(self, order: Dict) -> Dict:
        """
        Simplify order to meet policy

        Returns:
            Simplified order
        """
        simple_order = {
            'symbol': order['symbol'],
            'side': order['side'],
            'quantity': order['quantity'],
            'notional': order['notional'],
            'order_type': self.default_order_type,
            'tif': self.default_tif
        }

        # Add limit price if available
        if 'limit_price' in order:
            simple_order['limit_price'] = order['limit_price']

        return simple_order
