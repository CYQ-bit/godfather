"""
Market Data Loader - Phase P.1.1
Loads REAL OHLCV data from v8_empire data_lake
Replaces synthetic price generation with actual market data
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Tuple
import warnings
warnings.filterwarnings('ignore')


class MarketDataLoader:
    """
    Loads and validates real OHLCV market data

    Data source: v8_empire/data_lake/prices/*.parquet
    - Real split-adjusted prices
    - Real volume data
    - Real sector classifications
    """

    def __init__(self, data_lake_path: str):
        """
        Args:
            data_lake_path: Path to v8_empire data_lake/prices directory
        """
        self.data_lake_path = Path(data_lake_path)

    def load_all_prices(self) -> pd.DataFrame:
        """
        Load all symbol price files and consolidate into single DataFrame

        Returns:
            DataFrame with columns: [timestamp, symbol, open, high, low, close, volume, sector]
        """
        print("Loading real OHLCV data from v8_empire data_lake...")
        print(f"Source: {self.data_lake_path}")

        price_files = list(self.data_lake_path.glob("*.parquet"))
        print(f"Found {len(price_files)} symbol files")

        all_data = []
        failed_symbols = []

        for i, file_path in enumerate(price_files):
            try:
                df = pd.read_parquet(file_path)
                all_data.append(df)

                if (i + 1) % 100 == 0:
                    print(f"  Loaded {i + 1}/{len(price_files)} files...")

            except Exception as e:
                failed_symbols.append((file_path.stem, str(e)))

        if failed_symbols:
            print(f"WARNING: Failed to load {len(failed_symbols)} symbols:")
            for sym, err in failed_symbols[:5]:
                print(f"  {sym}: {err}")

        # Consolidate all data
        print("Consolidating data...")
        df = pd.concat(all_data, ignore_index=True)

        # Standardize column names
        df = df.rename(columns={'timestamp': 'date'})

        # Ensure datetime
        df['date'] = pd.to_datetime(df['date'])

        # Sort by symbol and date
        df = df.sort_values(['symbol', 'date'])

        print(f"\nLoaded {len(df)} total records")
        print(f"Unique symbols: {df['symbol'].nunique()}")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"Columns: {df.columns.tolist()}")

        return df

    def audit_data_quality(self, df: pd.DataFrame) -> Dict:
        """
        Comprehensive data quality audit

        Args:
            df: Market data DataFrame

        Returns:
            Dictionary with audit results
        """
        print("\n" + "=" * 80)
        print("【Price Data Quality Audit】")
        print("=" * 80)

        audit = {}

        # 1. Duplicate check
        print("\n1. Duplicate Check:")
        duplicates = df.duplicated(subset=['symbol', 'date']).sum()
        audit['duplicates'] = duplicates
        print(f"   Duplicate symbol-date pairs: {duplicates}")

        if duplicates > 0:
            print("   WARNING: Removing duplicates...")
            df = df.drop_duplicates(subset=['symbol', 'date'], keep='last')

        # 2. Missing values
        print("\n2. Missing Values:")
        for col in ['open', 'high', 'low', 'close', 'volume']:
            missing = df[col].isna().sum()
            missing_pct = missing / len(df) * 100
            audit[f'missing_{col}'] = missing
            print(f"   {col}: {missing} ({missing_pct:.2f}%)")

        # 3. Invalid prices
        print("\n3. Invalid Prices:")
        invalid_prices = (df['close'] <= 0).sum()
        audit['invalid_prices'] = invalid_prices
        print(f"   Close <= 0: {invalid_prices}")

        # 4. Extreme price jumps
        print("\n4. Extreme Price Jumps:")
        df_sorted = df.sort_values(['symbol', 'date'])
        df_sorted['price_change'] = df_sorted.groupby('symbol')['close'].pct_change()
        extreme_jumps = (df_sorted['price_change'].abs() > 0.5).sum()
        audit['extreme_jumps'] = extreme_jumps
        print(f"   Daily changes > 50%: {extreme_jumps}")

        # 5. OHLC consistency
        print("\n5. OHLC Consistency:")
        ohlc_violations = (
            (df['high'] < df['low']) |
            (df['close'] > df['high']) |
            (df['close'] < df['low']) |
            (df['open'] > df['high']) |
            (df['open'] < df['low'])
        ).sum()
        audit['ohlc_violations'] = ohlc_violations
        print(f"   OHLC violations: {ohlc_violations}")

        # 6. Date coverage
        print("\n6. Date Coverage:")
        date_range = (df['date'].max() - df['date'].min()).days
        unique_dates = df['date'].nunique()
        audit['date_range_days'] = date_range
        audit['unique_dates'] = unique_dates
        print(f"   Date range: {date_range} days")
        print(f"   Unique trading dates: {unique_dates}")
        print(f"   Coverage: {unique_dates / date_range * 100:.1f}%")

        # 7. Symbol coverage
        print("\n7. Symbol Coverage:")
        symbol_counts = df.groupby('symbol').size()
        audit['min_records_per_symbol'] = symbol_counts.min()
        audit['max_records_per_symbol'] = symbol_counts.max()
        audit['avg_records_per_symbol'] = symbol_counts.mean()
        print(f"   Min records per symbol: {symbol_counts.min()}")
        print(f"   Max records per symbol: {symbol_counts.max()}")
        print(f"   Avg records per symbol: {symbol_counts.mean():.1f}")

        # 8. Sector coverage
        print("\n8. Sector Coverage:")
        if 'sector' in df.columns:
            sector_counts = df['sector'].value_counts()
            audit['n_sectors'] = len(sector_counts)
            print(f"   Number of sectors: {len(sector_counts)}")
            print("   Top 5 sectors:")
            for sector, count in sector_counts.head(5).items():
                print(f"     {sector}: {count} records")
        else:
            audit['n_sectors'] = 0
            print("   No sector information available")

        # 9. Volume analysis
        print("\n9. Volume Analysis:")
        zero_volume = (df['volume'] == 0).sum()
        audit['zero_volume'] = zero_volume
        print(f"   Zero volume days: {zero_volume} ({zero_volume / len(df) * 100:.2f}%)")

        print("\n" + "=" * 80)

        return audit

    def check_t1_executability(
        self,
        df: pd.DataFrame,
        signal_dates: pd.Series
    ) -> Dict:
        """
        Check if T+1 execution is possible for all signal dates

        Args:
            df: Market data DataFrame
            signal_dates: Series of signal generation dates

        Returns:
            Dictionary with executability statistics
        """
        print("\n" + "=" * 80)
        print("【T+1 Executability Check】")
        print("=" * 80)

        results = {
            'total_signals': len(signal_dates),
            'executable': 0,
            'missing_t1': 0,
            'coverage_rate': 0.0
        }

        # Get all available trading dates
        trading_dates = sorted(df['date'].unique())
        trading_dates_set = set(trading_dates)

        executable_count = 0
        missing_count = 0

        for signal_date in signal_dates.unique():
            # Find next trading day (T+1)
            future_dates = [d for d in trading_dates if d > signal_date]

            if len(future_dates) > 0:
                executable_count += 1
            else:
                missing_count += 1

        results['executable'] = executable_count
        results['missing_t1'] = missing_count
        results['coverage_rate'] = executable_count / len(signal_dates.unique()) * 100

        print(f"\nTotal unique signal dates: {len(signal_dates.unique())}")
        print(f"Executable (T+1 exists): {executable_count}")
        print(f"Missing T+1: {missing_count}")
        print(f"Coverage rate: {results['coverage_rate']:.2f}%")

        print("=" * 80)

        return results

    def prepare_for_backtest(
        self,
        df: pd.DataFrame,
        start_date: str = None,
        end_date: str = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Prepare clean data for backtesting

        Args:
            df: Raw market data
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Tuple of (price_data, stock_data)
        """
        print("\nPreparing data for backtest...")

        # Remove duplicates
        df = df.drop_duplicates(subset=['symbol', 'date'], keep='last')

        # Remove invalid prices
        df = df[df['close'] > 0]

        # Filter date range if specified
        if start_date:
            df = df[df['date'] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df['date'] <= pd.to_datetime(end_date)]

        # Rename for compatibility
        price_data = df.rename(columns={'symbol': 'stock_code'}).copy()

        # Add market_cap proxy (close * volume)
        price_data['market_cap'] = price_data['close'] * price_data['volume']

        # stock_data is same as price_data for now
        stock_data = price_data.copy()

        print(f"Final dataset: {len(price_data)} records")
        print(f"Date range: {price_data['date'].min()} to {price_data['date'].max()}")
        print(f"Symbols: {price_data['stock_code'].nunique()}")

        return price_data, stock_data
