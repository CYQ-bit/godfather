"""
Broker Connection - Godfather V9.0 PT.4.2
Alpaca Broker Execution Adapter
"""
import json
import requests
from pathlib import Path
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime


class BrokerConnectionStatus(Enum):
    """Broker connection status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class BrokerConnection:
    """
    Alpaca Broker Execution Adapter
    """

    def __init__(self, config_file: str):
        self.config_file = Path(config_file)
        self.config = self._load_config()
        self.status = BrokerConnectionStatus.DISCONNECTED
        self.account_id = None
        self.headers = None
        self.order_id_map = {}  # local_order_id -> broker_order_id

        print("Initializing BrokerConnection (Godfather V9.0 - Alpaca Adapter)...")
        print(f"  Broker: {self.config.get('broker_name', 'N/A')}")
        print(f"  Environment: {self.config.get('environment', 'N/A')}")

    def _load_config(self) -> Dict:
        """Load broker config"""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                return json.load(f)
        else:
            return {
                'broker_name': 'PLACEHOLDER',
                'environment': 'paper',
                'api_endpoint': 'PLACEHOLDER',
                'account_id': 'PLACEHOLDER',
                'credentials_configured': False
            }

    def connect(self) -> bool:
        """
        Connect to Alpaca broker

        Returns:
            Success status
        """
        if not self.config.get('credentials_configured', False):
            print("❌ Broker credentials not configured")
            self.status = BrokerConnectionStatus.ERROR
            return False

        self.status = BrokerConnectionStatus.CONNECTING

        self.headers = {
            'APCA-API-KEY-ID': self.config['api_key'],
            'APCA-API-SECRET-KEY': self.config['api_secret']
        }

        try:
            response = requests.get(
                f"{self.config['api_endpoint']}/v2/account",
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                account_data = response.json()
                self.account_id = account_data['account_number']
                self.status = BrokerConnectionStatus.CONNECTED
                print(f"✅ Connected to Alpaca")
                print(f"  Account: {self.account_id[:4]}***{self.account_id[-4:]}")
                print(f"  Status: {account_data.get('status', 'N/A')}")
                return True
            else:
                print(f"❌ Connection failed: {response.status_code}")
                self.status = BrokerConnectionStatus.ERROR
                return False

        except Exception as e:
            print(f"❌ Connection error: {e}")
            self.status = BrokerConnectionStatus.ERROR
            return False

    def submit_order(self, order: Dict) -> Optional[Dict]:
        """
        Submit order to Alpaca

        Args:
            order: {symbol, side, quantity, order_type, tif, local_order_id}

        Returns:
            {broker_order_id, status, timestamp, symbol, side, qty}
        """
        if self.status != BrokerConnectionStatus.CONNECTED:
            print("❌ Not connected to broker")
            return None

        try:
            payload = {
                'symbol': order['symbol'],
                'qty': order['quantity'],
                'side': order['side'].lower(),
                'type': 'market',
                'time_in_force': 'day'
            }

            response = requests.post(
                f"{self.config['api_endpoint']}/v2/orders",
                headers=self.headers,
                json=payload,
                timeout=10
            )

            if response.status_code in [200, 201]:
                broker_order = response.json()
                broker_order_id = broker_order['id']

                # Map local_order_id to broker_order_id
                if 'local_order_id' in order:
                    self.order_id_map[order['local_order_id']] = broker_order_id

                result = {
                    'broker_order_id': broker_order_id,
                    'status': broker_order.get('status', 'unknown'),
                    'timestamp': broker_order.get('created_at', datetime.now().isoformat()),
                    'symbol': broker_order.get('symbol'),
                    'side': broker_order.get('side'),
                    'qty': broker_order.get('qty')
                }

                print(f"✅ Order submitted: {result['symbol']} {result['side']} {result['qty']}")
                print(f"  Broker order ID: {broker_order_id}")
                print(f"  Status: {result['status']}")

                return result
            else:
                print(f"❌ Order submission failed: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"❌ Order submission error: {e}")
            return None

    def get_order(self, broker_order_id: str) -> Optional[Dict]:
        """
        Get order details from Alpaca

        Returns:
            {broker_order_id, status, symbol, side, qty, filled_qty, filled_avg_price}
        """
        if self.status != BrokerConnectionStatus.CONNECTED:
            return None

        try:
            response = requests.get(
                f"{self.config['api_endpoint']}/v2/orders/{broker_order_id}",
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                order = response.json()
                return {
                    'broker_order_id': order['id'],
                    'status': self._map_order_status(order['status']),
                    'symbol': order['symbol'],
                    'side': order['side'],
                    'qty': order['qty'],
                    'filled_qty': order.get('filled_qty', '0'),
                    'filled_avg_price': order.get('filled_avg_price'),
                    'created_at': order.get('created_at'),
                    'updated_at': order.get('updated_at')
                }
            else:
                return None

        except Exception as e:
            print(f"❌ Get order error: {e}")
            return None

    def _map_order_status(self, alpaca_status: str) -> str:
        """Map Alpaca status to local lifecycle"""
        status_map = {
            'new': 'created',
            'accepted': 'accepted',
            'pending_new': 'created',
            'accepted_for_bidding': 'accepted',
            'stopped': 'rejected',
            'rejected': 'rejected',
            'suspended': 'rejected',
            'calculated': 'accepted',
            'partially_filled': 'partially_filled',
            'filled': 'filled',
            'done_for_day': 'filled',
            'canceled': 'cancelled',
            'expired': 'cancelled',
            'replaced': 'cancelled',
            'pending_cancel': 'cancelled',
            'pending_replace': 'accepted'
        }
        return status_map.get(alpaca_status, 'unknown')

    def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel order"""
        if self.status != BrokerConnectionStatus.CONNECTED:
            return False

        try:
            response = requests.delete(
                f"{self.config['api_endpoint']}/v2/orders/{broker_order_id}",
                headers=self.headers,
                timeout=10
            )
            return response.status_code in [200, 204]
        except Exception as e:
            print(f"❌ Cancel order error: {e}")
            return False

    def list_open_orders(self) -> Optional[List[Dict]]:
        """List all open orders"""
        if self.status != BrokerConnectionStatus.CONNECTED:
            return None

        try:
            response = requests.get(
                f"{self.config['api_endpoint']}/v2/orders",
                headers=self.headers,
                params={'status': 'open'},
                timeout=10
            )

            if response.status_code == 200:
                orders = response.json()
                return [{
                    'broker_order_id': o['id'],
                    'status': self._map_order_status(o['status']),
                    'symbol': o['symbol'],
                    'side': o['side'],
                    'qty': o['qty']
                } for o in orders]
            return None

        except Exception as e:
            print(f"❌ List orders error: {e}")
            return None

    def get_positions(self) -> Optional[List[Dict]]:
        """
        Get current positions from Alpaca

        Returns:
            [{symbol, qty, avg_entry_price, market_value, unrealized_pl}]
        """
        if self.status != BrokerConnectionStatus.CONNECTED:
            return None

        try:
            response = requests.get(
                f"{self.config['api_endpoint']}/v2/positions",
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                positions = response.json()
                return [{
                    'symbol': p['symbol'],
                    'qty': float(p['qty']),
                    'avg_entry_price': float(p['avg_entry_price']),
                    'market_value': float(p['market_value']),
                    'unrealized_pl': float(p.get('unrealized_pl', 0)),
                    'side': 'long' if float(p['qty']) > 0 else 'short'
                } for p in positions]
            return None

        except Exception as e:
            print(f"❌ Get positions error: {e}")
            return None

    def get_account_info(self) -> Optional[Dict]:
        """
        Get account info from Alpaca

        Returns:
            {cash, buying_power, equity, portfolio_value}
        """
        if self.status != BrokerConnectionStatus.CONNECTED:
            return None

        try:
            response = requests.get(
                f"{self.config['api_endpoint']}/v2/account",
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                account = response.json()
                return {
                    'cash': float(account['cash']),
                    'buying_power': float(account['buying_power']),
                    'equity': float(account['equity']),
                    'portfolio_value': float(account['portfolio_value']),
                    'status': account['status']
                }
            return None

        except Exception as e:
            print(f"❌ Get account error: {e}")
            return None

    def get_fills(self) -> Optional[List[Dict]]:
        """
        Get fills/activities from Alpaca

        Returns:
            [{activity_type, symbol, qty, price, side, transaction_time}]
        """
        if self.status != BrokerConnectionStatus.CONNECTED:
            return None

        try:
            response = requests.get(
                f"{self.config['api_endpoint']}/v2/account/activities/FILL",
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                activities = response.json()
                return [{
                    'activity_type': a.get('activity_type', 'FILL'),
                    'symbol': a.get('symbol'),
                    'qty': float(a.get('qty', 0)),
                    'price': float(a.get('price', 0)),
                    'side': a.get('side'),
                    'transaction_time': a.get('transaction_time'),
                    'order_id': a.get('order_id')
                } for a in activities]
            return None

        except Exception as e:
            print(f"❌ Get fills error: {e}")
            return None

    def disconnect(self):
        """Disconnect from broker"""
        self.status = BrokerConnectionStatus.DISCONNECTED
        self.session = None
        print("Disconnected from broker")
