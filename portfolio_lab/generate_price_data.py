"""
Generate price data from ml_alpha_matrix target returns
"""
import pandas as pd
import numpy as np
from pathlib import Path

def generate_price_data():
    """Generate price data from target returns in ml_alpha_matrix"""

    print("Loading ml_alpha_matrix...")
    df = pd.read_parquet('../data/feature_store/ml_alpha_matrix.parquet')

    print(f"Loaded {len(df)} rows")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

    # Keep only necessary columns
    price_df = df[['timestamp', 'symbol', 'target']].copy()
    price_df.columns = ['date', 'stock_code', 'return']

    # Convert to datetime
    price_df['date'] = pd.to_datetime(price_df['date'])

    # Sort by stock and date
    price_df = price_df.sort_values(['stock_code', 'date'])

    print("\nGenerating prices from returns...")

    # Generate prices for each stock
    price_list = []
    for stock_code, group in price_df.groupby('stock_code'):
        group = group.sort_values('date').copy()

        # Fill NaN returns with 0
        group['return'] = group['return'].fillna(0)

        # Generate cumulative prices (starting at 100)
        group['close'] = 100 * (1 + group['return']).cumprod()

        # Add volume (dummy for now)
        group['volume'] = 1_000_000

        # Add market cap (price * volume as proxy)
        group['market_cap'] = group['close'] * group['volume']

        price_list.append(group[['date', 'stock_code', 'close', 'volume', 'market_cap']])

    price_data = pd.concat(price_list, ignore_index=True)

    print(f"\nGenerated {len(price_data)} price records")
    print(f"Unique stocks: {price_data['stock_code'].nunique()}")
    print(f"Date range: {price_data['date'].min()} to {price_data['date'].max()}")

    # Save to parquet
    output_path = Path('../data/price_data.parquet')
    price_data.to_parquet(output_path)
    print(f"\nSaved to: {output_path}")

    # Also save stock_data (same as price_data for now)
    stock_output_path = Path('../data/stock_data.parquet')
    price_data.to_parquet(stock_output_path)
    print(f"Saved to: {stock_output_path}")

    return price_data

if __name__ == '__main__':
    generate_price_data()
