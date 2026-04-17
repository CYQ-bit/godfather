"""
Market Data Feed Module - Phase PT.1
Real-time market data input for paper trading
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import warnings


class MarketDataFeed:
    """
    Unified market data feed for paper trading

    Features:
    - Real OHLCV data ingestion
    - Trading calendar validation
    - Latest price queries
    - Data freshness checks
    - Future data prevention
    """

    def __init__(self, data_source_path: str, mode: str = 'eod'):
        """
        Initialize market data feed

        Args:
            data_source_path: Path to market data (v8_empire data_lake)
            mode: 'eod' (end-of-day) or 'intraday' (future)
        """
        self.data_source_path = Path(data_source_path)
        self.mode = mode
        self.data_cache = {}
        self.last_update_time = None
        self.trading_calendar = None

        print(f"Initializing MarketDataFeed...")
        print(f"  Source: {self.data_source_path}")
        print(f"  Mode: {self.mode}")

    def load_historical_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Load historical OHLCV data

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with [date, symbol, open, high, low, close, volume, sector]
        """
        print(f"\nLoading historical market data...")
        print(f"  Date range: {start_date} to {end_date}")

        # Load all parquet files
        symbol_files = list(self.data_source_path.glob("*.parquet"))
        print(f"  Found {len(symbol_files)} symbol files")

        all_data = []
        for i, file in enumerate(symbol_files):
            if (i + 1) % 100 == 0:
                print(f"  Loaded {i + 1}/{len(symbol_files)} files...")

            df = pd.read_parquet(file)
            df['symbol'] = file.stem
            all_data.append(df)

        # Consolidate
        market_data = pd.concat(all_data, ignore_index=True)

        # Rename timestamp to date for consistency
        if 'timestamp' in market_data.columns:
            market_data = market_data.rename(columns={'timestamp': 'date'})

        market_data['date'] = pd.to_datetime(market_data['date'])

        # Filter date range
        if start_date:
            market_data = market_data[market_data['date'] >= start_date]
        if end_date:
            market_data = market_data[market_data['date'] <= end_date]

        print(f"\nLoaded {len(market_data)} records")
        print(f"  Symbols: {market_data['symbol'].nunique()}")
        print(f"  Date range: {market_data['date'].min()} to {market_data['date'].max()}")

        self.data_cache['historical'] = market_data
        self.last_update_time = datetime.now()

        return market_data

    def get_latest_prices(
        self,
        symbols: List[str],
        as_of_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get latest prices for given symbols

        Args:
            symbols: List of symbols
            as_of_date: As-of date (YYYY-MM-DD), defaults to latest available

        Returns:
            DataFrame with [symbol, date, close, volume]
        """
        if 'historical' not in self.data_cache:
            raise ValueError("Historical data not loaded. Call load_historical_data() first.")

        data = self.data_cache['historical']

        # Filter to requested symbols
        data = data[data['symbol'].isin(symbols)]

        # Get latest date
        if as_of_date:
            as_of_date = pd.to_datetime(as_of_date)
            data = data[data['date'] <= as_of_date]

        # Get latest price for each symbol
        latest = data.sort_values('date').groupby('symbol').tail(1)

        # Use stock_code as primary key for consistency
        result = latest[['symbol', 'date', 'close', 'volume']].reset_index(drop=True)
        result = result.rename(columns={'symbol': 'stock_code'})

        return result

    def get_trading_calendar(self) -> pd.DatetimeIndex:
        """
        Get trading calendar (all unique trading dates)

        Returns:
            DatetimeIndex of trading dates
        """
        if 'historical' not in self.data_cache:
            raise ValueError("Historical data not loaded. Call load_historical_data() first.")

        data = self.data_cache['historical']
        trading_dates = pd.DatetimeIndex(sorted(data['date'].unique()))

        self.trading_calendar = trading_dates
        return trading_dates

    def is_trading_day(self, date: str) -> bool:
        """
        Check if given date is a trading day

        Args:
            date: Date string (YYYY-MM-DD)

        Returns:
            True if trading day, False otherwise
        """
        if self.trading_calendar is None:
            self.get_trading_calendar()

        date = pd.to_datetime(date)
        return date in self.trading_calendar

    def get_next_trading_day(self, date: str) -> pd.Timestamp:
        """
        Get next trading day after given date

        Args:
            date: Date string (YYYY-MM-DD)

        Returns:
            Next trading day
        """
        if self.trading_calendar is None:
            self.get_trading_calendar()

        date = pd.to_datetime(date)
        future_dates = self.trading_calendar[self.trading_calendar > date]

        if len(future_dates) == 0:
            raise ValueError(f"No trading days after {date}")

        return future_dates[0]

    def get_previous_trading_day(self, date: str) -> pd.Timestamp:
        """
        Get previous trading day before given date

        Args:
            date: Date string (YYYY-MM-DD)

        Returns:
            Previous trading day
        """
        if self.trading_calendar is None:
            self.get_trading_calendar()

        date = pd.to_datetime(date)
        past_dates = self.trading_calendar[self.trading_calendar < date]

        if len(past_dates) == 0:
            raise ValueError(f"No trading days before {date}")

        return past_dates[-1]

    def validate_data_freshness(
        self,
        expected_date: str,
        tolerance_days: int = 1
    ) -> Tuple[bool, str]:
        """
        Validate that data is fresh and up-to-date

        Args:
            expected_date: Expected latest date
            tolerance_days: Tolerance in days

        Returns:
            (is_fresh, message)
        """
        if 'historical' not in self.data_cache:
            return False, "No data loaded"

        data = self.data_cache['historical']
        latest_date = data['date'].max()
        expected_date = pd.to_datetime(expected_date)

        days_behind = (expected_date - latest_date).days

        if days_behind <= tolerance_days:
            return True, f"Data is fresh (latest: {latest_date.date()})"
        else:
            return False, f"Data is stale (latest: {latest_date.date()}, expected: {expected_date.date()}, {days_behind} days behind)"

    def prevent_future_data_leak(
        self,
        signal_date: str,
        data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Ensure no future data leaks into signal generation

        Args:
            signal_date: Signal generation date
            data: Data to filter

        Returns:
            Filtered data with no future information
        """
        signal_date = pd.to_datetime(signal_date)

        if 'date' in data.columns:
            future_mask = data['date'] > signal_date
            if future_mask.any():
                warnings.warn(f"Detected {future_mask.sum()} future data points. Filtering...")
                data = data[~future_mask].copy()

        return data

    def get_data_summary(self) -> Dict:
        """
        Get summary of loaded data

        Returns:
            Dictionary with data statistics
        """
        if 'historical' not in self.data_cache:
            return {"status": "No data loaded"}

        data = self.data_cache['historical']

        return {
            "status": "Data loaded",
            "total_records": len(data),
            "symbols": data['symbol'].nunique(),
            "date_range": f"{data['date'].min().date()} to {data['date'].max().date()}",
            "trading_days": len(data['date'].unique()),
            "last_update": self.last_update_time.strftime("%Y-%m-%d %H:%M:%S") if self.last_update_time else None,
            "columns": list(data.columns)
        }
