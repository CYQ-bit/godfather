"""
Order Lifecycle Engine - Godfather V9.0 PT.4
Track order state transitions
"""
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from enum import Enum


class OrderStatus(Enum):
    """Order status states"""
    CREATED = "created"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class OrderLifecycleEngine:
    """Track order lifecycle events"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.lifecycle_dir = self.output_dir / 'lifecycle'
        self.lifecycle_dir.mkdir(parents=True, exist_ok=True)

        self.orders = {}  # order_id -> order state

        print(f"Initializing OrderLifecycleEngine (Godfather V9.0 - PT.4)...")
        print(f"  Output directory: {self.lifecycle_dir}")

    def create_order(self, order: Dict, date: str) -> str:
        """Create new order and assign ID"""
        order_id = str(uuid.uuid4())

        order_state = {
            'order_id': order_id,
            'date': date,
            'symbol': order['symbol'],
            'side': order['side'],
            'quantity': order['quantity'],
            'notional': order['notional'],
            'status': OrderStatus.CREATED.value,
            'events': [{
                'timestamp': datetime.now().isoformat(),
                'status': OrderStatus.CREATED.value,
                'message': 'Order created'
            }]
        }

        self.orders[order_id] = order_state
        return order_id

    def update_status(
        self,
        order_id: str,
        new_status: OrderStatus,
        message: str = "",
        fill_qty: float = None,
        fill_price: float = None
    ):
        """Update order status"""
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")

        order = self.orders[order_id]
        order['status'] = new_status.value

        event = {
            'timestamp': datetime.now().isoformat(),
            'status': new_status.value,
            'message': message
        }

        if fill_qty is not None:
            event['fill_qty'] = fill_qty
        if fill_price is not None:
            event['fill_price'] = fill_price

        order['events'].append(event)

    def get_order(self, order_id: str) -> Dict:
        """Get order state"""
        return self.orders.get(order_id)

    def get_orders_by_date(self, date: str) -> List[Dict]:
        """Get all orders for a date"""
        return [o for o in self.orders.values() if o['date'] == date]

    def save_daily_lifecycle(self, date: str):
        """Save daily lifecycle log"""
        daily_orders = self.get_orders_by_date(date)

        lifecycle_log = {
            'date': date,
            'total_orders': len(daily_orders),
            'orders': daily_orders,
            'summary': {
                'created': sum(1 for o in daily_orders if o['status'] == OrderStatus.CREATED.value),
                'accepted': sum(1 for o in daily_orders if o['status'] == OrderStatus.ACCEPTED.value),
                'rejected': sum(1 for o in daily_orders if o['status'] == OrderStatus.REJECTED.value),
                'filled': sum(1 for o in daily_orders if o['status'] == OrderStatus.FILLED.value),
                'partially_filled': sum(1 for o in daily_orders if o['status'] == OrderStatus.PARTIALLY_FILLED.value),
                'cancelled': sum(1 for o in daily_orders if o['status'] == OrderStatus.CANCELLED.value)
            }
        }

        lifecycle_file = self.lifecycle_dir / f'{date}_lifecycle.json'
        with open(lifecycle_file, 'w') as f:
            json.dump(lifecycle_log, f, indent=2)

        return lifecycle_log
