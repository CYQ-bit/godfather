"""
Order Lifecycle Shadow - Godfather V9.0 Phase PT.3a
Simulate real broker order status flow
"""
from typing import Dict, List
from datetime import datetime
from enum import Enum


class OrderStatus(Enum):
    """Order status types"""
    CREATED = "created"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    FILLED = "filled"
    PARTIAL_FILLED = "partial_filled"


class OrderLifecycleShadow:
    """Simulate broker order lifecycle"""

    def __init__(self, rejection_rate: float = 0.0):
        self.rejection_rate = rejection_rate
        self.lifecycle_history = []

        print(f"Initializing OrderLifecycleShadow (Godfather V9.0 - PT.3a)...")
        print(f"  Rejection rate: {rejection_rate*100:.1f}%")

    def simulate_lifecycle(
        self,
        shadow_payloads: List[Dict],
        integration_checks: Dict
    ) -> List[Dict]:
        """
        Simulate order lifecycle

        Args:
            shadow_payloads: Broker-ready payloads
            integration_checks: Integration check results

        Returns:
            List of lifecycle events
        """
        lifecycle_events = []

        for payload in shadow_payloads:
            # Initial status: created
            event = {
                'shadow_order_id': payload['shadow_order_id'],
                'symbol': payload['symbol'],
                'side': payload['side'],
                'qty': payload['qty'],
                'timestamp': datetime.now().isoformat(),
                'status': OrderStatus.CREATED.value,
                'message': 'Order created'
            }
            lifecycle_events.append(event.copy())

            # Check if should be rejected based on integration checks
            should_reject = False
            reject_reason = None

            # Check symbol mapping
            if payload['symbol'] in integration_checks['checks']['symbol_mapping'].get('invalid_symbols', []):
                should_reject = True
                reject_reason = 'Invalid symbol'

            # Check tradability
            elif payload['symbol'] in integration_checks['checks']['tradability'].get('missing_prices', []):
                should_reject = True
                reject_reason = 'Missing price data'

            # Simulate rejection
            if should_reject:
                event['status'] = OrderStatus.REJECTED.value
                event['message'] = reject_reason
                event['timestamp'] = datetime.now().isoformat()
                lifecycle_events.append(event.copy())
            else:
                # Accepted
                event['status'] = OrderStatus.ACCEPTED.value
                event['message'] = 'Order accepted by broker'
                event['timestamp'] = datetime.now().isoformat()
                lifecycle_events.append(event.copy())

                # Filled (in shadow mode, assume all accepted orders fill)
                event['status'] = OrderStatus.FILLED.value
                event['message'] = 'Order filled'
                event['fill_price'] = payload['limit_price']
                event['fill_qty'] = payload['qty']
                event['timestamp'] = datetime.now().isoformat()
                lifecycle_events.append(event.copy())

            self.lifecycle_history.extend(lifecycle_events)

        return lifecycle_events

    def get_lifecycle_summary(self) -> Dict:
        """Get lifecycle summary"""
        if len(self.lifecycle_history) == 0:
            return {'total': 0}

        status_counts = {}
        for event in self.lifecycle_history:
            status = event['status']
            status_counts[status] = status_counts.get(status, 0) + 1

        # Count unique orders
        unique_orders = set(event['shadow_order_id'] for event in self.lifecycle_history)

        # Count final statuses
        final_statuses = {}
        for order_id in unique_orders:
            order_events = [e for e in self.lifecycle_history if e['shadow_order_id'] == order_id]
            if len(order_events) > 0:
                final_status = order_events[-1]['status']
                final_statuses[final_status] = final_statuses.get(final_status, 0) + 1

        return {
            'total_events': len(self.lifecycle_history),
            'unique_orders': len(unique_orders),
            'status_counts': status_counts,
            'final_statuses': final_statuses
        }
