"""
Broker Reconciliation Adapter - Godfather V9.0
Connect Alpaca data to existing recon flow
"""
from typing import Dict, List, Tuple
from datetime import datetime


class BrokerReconAdapter:
    """Reconciliation adapter for Alpaca broker data"""

    def __init__(self, broker_connection):
        self.broker = broker_connection
        print("Initializing BrokerReconAdapter...")

    def reconcile_orders(self, local_orders: List[Dict]) -> Tuple[str, Dict]:
        """
        Reconcile orders between local and broker

        Returns:
            (status, report)
            status: MATCHED / MISMATCHED
        """
        broker_orders = self.broker.list_open_orders()
        if broker_orders is None:
            return 'ERROR', {'error': 'Failed to fetch broker orders'}

        local_count = len(local_orders)
        broker_count = len(broker_orders)

        matched = local_count == broker_count

        report = {
            'check': 'orders_recon',
            'status': 'MATCHED' if matched else 'MISMATCHED',
            'local_count': local_count,
            'broker_count': broker_count,
            'diff': broker_count - local_count
        }

        return report['status'], report

    def reconcile_positions(self, local_positions: Dict) -> Tuple[str, Dict]:
        """
        Reconcile positions between local and broker

        Args:
            local_positions: {symbol: qty}

        Returns:
            (status, report)
        """
        broker_positions = self.broker.get_positions()
        if broker_positions is None:
            return 'ERROR', {'error': 'Failed to fetch broker positions'}

        broker_pos_dict = {p['symbol']: p['qty'] for p in broker_positions}

        mismatches = []
        for symbol in set(list(local_positions.keys()) + list(broker_pos_dict.keys())):
            local_qty = local_positions.get(symbol, 0)
            broker_qty = broker_pos_dict.get(symbol, 0)

            if abs(local_qty - broker_qty) > 0.01:
                mismatches.append({
                    'symbol': symbol,
                    'local_qty': local_qty,
                    'broker_qty': broker_qty,
                    'diff': broker_qty - local_qty
                })

        status = 'MATCHED' if len(mismatches) == 0 else 'MISMATCHED'

        report = {
            'check': 'positions_recon',
            'status': status,
            'local_positions': len(local_positions),
            'broker_positions': len(broker_pos_dict),
            'mismatches': mismatches
        }

        return status, report

    def reconcile_cash(self, local_cash: float) -> Tuple[str, Dict]:
        """
        Reconcile cash between local and broker

        Returns:
            (status, report)
        """
        account_info = self.broker.get_account_info()
        if account_info is None:
            return 'ERROR', {'error': 'Failed to fetch broker account'}

        broker_cash = account_info['cash']
        diff = broker_cash - local_cash
        tolerance = 0.01

        matched = abs(diff) <= tolerance

        report = {
            'check': 'cash_recon',
            'status': 'MATCHED' if matched else 'MISMATCHED',
            'local_cash': local_cash,
            'broker_cash': broker_cash,
            'diff': diff,
            'tolerance': tolerance
        }

        return report['status'], report

    def reconcile_fills(self, local_fills: List[Dict]) -> Tuple[str, Dict]:
        """
        Reconcile fills between local and broker

        Args:
            local_fills: [{symbol, qty, price, side}]

        Returns:
            (status, report)
        """
        broker_fills = self.broker.get_fills()
        if broker_fills is None:
            return 'ERROR', {'error': 'Failed to fetch broker fills'}

        local_count = len(local_fills)
        broker_count = len(broker_fills)

        matched = local_count == broker_count

        report = {
            'check': 'fills_recon',
            'status': 'MATCHED' if matched else 'MISMATCHED',
            'local_fills': local_count,
            'broker_fills': broker_count,
            'diff': broker_count - local_count
        }

        return report['status'], report

    def run_full_recon(
        self,
        local_orders: List[Dict],
        local_positions: Dict,
        local_cash: float,
        local_fills: List[Dict]
    ) -> Dict:
        """
        Run full reconciliation

        Returns:
            Complete recon report
        """
        print("\n" + "="*80)
        print("【Broker Reconciliation】")
        print("="*80 + "\n")

        recon_report = {
            'timestamp': datetime.now().isoformat(),
            'checks': []
        }

        # Orders recon
        print("[1/4] Reconciling orders...")
        orders_status, orders_report = self.reconcile_orders(local_orders)
        recon_report['checks'].append(orders_report)
        print(f"  Status: {orders_status}")
        if orders_status == 'MISMATCHED':
            print(f"  Local: {orders_report['local_count']}, Broker: {orders_report['broker_count']}")

        # Positions recon
        print("\n[2/4] Reconciling positions...")
        pos_status, pos_report = self.reconcile_positions(local_positions)
        recon_report['checks'].append(pos_report)
        print(f"  Status: {pos_status}")
        if pos_status == 'MISMATCHED':
            print(f"  Mismatches: {len(pos_report['mismatches'])}")
            for m in pos_report['mismatches']:
                print(f"    {m['symbol']}: local={m['local_qty']}, broker={m['broker_qty']}")

        # Cash recon
        print("\n[3/4] Reconciling cash...")
        cash_status, cash_report = self.reconcile_cash(local_cash)
        recon_report['checks'].append(cash_report)
        print(f"  Status: {cash_status}")
        if cash_status == 'MISMATCHED':
            print(f"  Local: ${cash_report['local_cash']:,.2f}, Broker: ${cash_report['broker_cash']:,.2f}")
            print(f"  Diff: ${cash_report['diff']:,.2f}")

        # Fills recon
        print("\n[4/4] Reconciling fills...")
        fills_status, fills_report = self.reconcile_fills(local_fills)
        recon_report['checks'].append(fills_report)
        print(f"  Status: {fills_status}")
        if fills_status == 'MISMATCHED':
            print(f"  Local: {fills_report['local_fills']}, Broker: {fills_report['broker_fills']}")

        # Overall status
        all_statuses = [orders_status, pos_status, cash_status, fills_status]
        if 'ERROR' in all_statuses:
            overall_status = 'ERROR'
        elif 'MISMATCHED' in all_statuses:
            overall_status = 'MISMATCHED'
        else:
            overall_status = 'MATCHED'

        recon_report['overall_status'] = overall_status

        print("\n" + "="*80)
        print(f"Overall Status: {overall_status}")
        print("="*80 + "\n")

        return recon_report
