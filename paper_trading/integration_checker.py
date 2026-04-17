"""
Integration Checker - Godfather V9.0 Phase PT.3a
Pre-flight checks for live broker integration
"""
import pandas as pd
from typing import Dict, List, Set
from datetime import datetime


class IntegrationChecker:
    """Pre-flight checks for broker integration"""

    def __init__(self, market_feed):
        self.market_feed = market_feed
        self.check_results = []

        print(f"Initializing IntegrationChecker (Godfather V9.0 - PT.3a)...")
        print(f"  Checks: symbol mapping, trading calendar, tradability")

    def run_integration_checks(
        self,
        symbols: List[str],
        target_date: str,
        orders: List[Dict]
    ) -> Dict:
        """
        Run all integration checks

        Args:
            symbols: List of symbols
            target_date: Target trading date
            orders: Order list

        Returns:
            Check results
        """
        results = {
            'timestamp': datetime.now().isoformat(),
            'target_date': target_date,
            'checks': {}
        }

        # Check 1: Symbol mapping
        symbol_check = self._check_symbol_mapping(symbols)
        results['checks']['symbol_mapping'] = symbol_check

        # Check 2: Trading calendar
        calendar_check = self._check_trading_calendar(target_date)
        results['checks']['trading_calendar'] = calendar_check

        # Check 3: Tradability
        tradability_check = self._check_tradability(symbols, target_date)
        results['checks']['tradability'] = tradability_check

        # Check 4: Order field completeness
        field_check = self._check_order_fields(orders)
        results['checks']['order_fields'] = field_check

        # Overall status
        all_passed = all(
            check.get('status') == 'PASS'
            for check in results['checks'].values()
        )
        results['overall_status'] = 'PASS' if all_passed else 'FAIL'

        self.check_results.append(results)
        return results

    def _check_symbol_mapping(self, symbols: List[str]) -> Dict:
        """Check if symbols are valid US equities"""
        invalid_symbols = []

        for symbol in symbols:
            # US equities validation: alphanumeric + optional . or -
            # Examples: AAPL, BRK.B, BRK-A, MRNA
            if not symbol or len(symbol) > 10:
                invalid_symbols.append(symbol)
            elif not all(c.isalnum() or c in ['.', '-'] for c in symbol):
                invalid_symbols.append(symbol)

        return {
            'status': 'PASS' if len(invalid_symbols) == 0 else 'FAIL',
            'total_symbols': len(symbols),
            'invalid_symbols': invalid_symbols,
            'invalid_count': len(invalid_symbols)
        }

    def _check_trading_calendar(self, target_date: str) -> Dict:
        """Check if target date is a US trading day"""
        # US market: weekdays excluding major holidays
        # For now, simple weekday check (production would use NYSE calendar)
        try:
            date_obj = pd.to_datetime(target_date)
            is_weekday = date_obj.weekday() < 5

            return {
                'status': 'PASS' if is_weekday else 'WARN',
                'target_date': target_date,
                'is_weekday': is_weekday,
                'market': 'US',
                'message': 'OK' if is_weekday else 'Weekend - check NYSE calendar'
            }
        except Exception as e:
            return {
                'status': 'FAIL',
                'target_date': target_date,
                'error': str(e)
            }

    def _check_tradability(self, symbols: List[str], target_date: str) -> Dict:
        """Check if symbols are tradable (have prices)"""
        missing_prices = []
        abnormal_prices = []

        try:
            prices_df = self.market_feed.get_latest_prices(symbols, as_of_date=target_date)

            # Convert DataFrame to dict for lookup (using 'stock_code' as primary key)
            prices = dict(zip(prices_df['stock_code'], prices_df['close']))

            for symbol in symbols:
                if symbol not in prices:
                    missing_prices.append(symbol)
                elif prices[symbol] <= 0 or prices[symbol] > 10000:
                    abnormal_prices.append((symbol, prices[symbol]))

            return {
                'status': 'PASS' if len(missing_prices) == 0 and len(abnormal_prices) == 0 else 'FAIL',
                'total_symbols': len(symbols),
                'missing_prices': missing_prices,
                'missing_count': len(missing_prices),
                'abnormal_prices': abnormal_prices,
                'abnormal_count': len(abnormal_prices)
            }
        except Exception as e:
            return {
                'status': 'FAIL',
                'error': str(e)
            }

    def _check_order_fields(self, orders: List[Dict]) -> Dict:
        """Check order field completeness"""
        required_fields = ['stock_code', 'side', 'target_shares', 'reference_price', 'intended_trade_date']
        incomplete_orders = []

        for i, order in enumerate(orders):
            missing_fields = [f for f in required_fields if f not in order or order[f] is None]
            if len(missing_fields) > 0:
                incomplete_orders.append({
                    'order_index': i,
                    'missing_fields': missing_fields
                })

        return {
            'status': 'PASS' if len(incomplete_orders) == 0 else 'FAIL',
            'total_orders': len(orders),
            'incomplete_orders': incomplete_orders,
            'incomplete_count': len(incomplete_orders)
        }

    def get_check_summary(self) -> Dict:
        """Get integration check summary"""
        if len(self.check_results) == 0:
            return {'total': 0}

        total_checks = len(self.check_results)
        passed = sum(1 for r in self.check_results if r['overall_status'] == 'PASS')

        return {
            'total_checks': total_checks,
            'passed': passed,
            'failed': total_checks - passed,
            'pass_rate': passed / total_checks if total_checks > 0 else 0
        }
