"""
Phase P.1 Main Execution Script
Runs production-level portfolio backtest using ML.2 predictions
"""
import sys
import os
import time
import pandas as pd
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from portfolio_lab.production_backtester import ProductionBacktester


def load_ml2_predictions(predictions_path: str) -> pd.DataFrame:
    """Load ML.2 predictions"""
    print(f"Loading predictions from {predictions_path}...")
    df = pd.read_parquet(predictions_path)

    # Map column names to expected format
    column_mapping = {
        'timestamp': 'date',
        'symbol': 'stock_code',
        'y_pred': 'prediction'
    }

    df = df.rename(columns=column_mapping)

    # Ensure required columns
    required_cols = ['date', 'stock_code', 'prediction']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # Convert date to datetime if needed
    if not pd.api.types.is_datetime64_any_dtype(df['date']):
        df['date'] = pd.to_datetime(df['date'])

    print(f"  Loaded {len(df)} predictions")
    print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"  Unique stocks: {df['stock_code'].nunique()}")
    print(f"  Unique dates: {df['date'].nunique()}")

    return df


def load_price_data(data_dir: str) -> pd.DataFrame:
    """Load price data for execution simulation"""
    print(f"Loading price data from {data_dir}...")

    # Try to load from parquet first
    price_file = os.path.join(data_dir, 'price_data.parquet')
    if os.path.exists(price_file):
        df = pd.read_parquet(price_file)
    else:
        # Fall back to CSV
        price_file = os.path.join(data_dir, 'price_data.csv')
        if os.path.exists(price_file):
            df = pd.read_csv(price_file)
            df['date'] = pd.to_datetime(df['date'])
        else:
            raise FileNotFoundError(f"Price data not found in {data_dir}")

    print(f"  Loaded {len(df)} price records")
    print(f"  Date range: {df['date'].min()} to {df['date'].max()}")

    return df


def load_stock_data(data_dir: str) -> pd.DataFrame:
    """Load full stock data for risk model"""
    print(f"Loading stock data from {data_dir}...")

    # Try to load from parquet first
    stock_file = os.path.join(data_dir, 'stock_data.parquet')
    if os.path.exists(stock_file):
        df = pd.read_parquet(stock_file)
    else:
        # Fall back to CSV
        stock_file = os.path.join(data_dir, 'stock_data.csv')
        if os.path.exists(stock_file):
            df = pd.read_csv(stock_file)
            df['date'] = pd.to_datetime(df['date'])
        else:
            # If not available, use price data as fallback
            print("  Stock data not found, using price data as fallback...")
            df = load_price_data(data_dir)
            # Add dummy market_cap if not present
            if 'market_cap' not in df.columns:
                df['market_cap'] = df['close'] * df.get('volume', 1000000)

    print(f"  Loaded {len(df)} stock records")

    return df


def add_sector_info(predictions: pd.DataFrame, sector_mapping: dict = None) -> pd.DataFrame:
    """Add sector information to predictions"""
    if 'sector' in predictions.columns:
        return predictions

    print("Adding sector information...")

    if sector_mapping is None:
        # Create dummy sector mapping based on stock code patterns
        # In production, this should come from actual sector data
        unique_stocks = predictions['stock_code'].unique()
        n_sectors = min(10, len(unique_stocks) // 5)  # ~5 stocks per sector

        sector_mapping = {}
        for i, stock in enumerate(unique_stocks):
            sector_id = i % n_sectors
            sector_mapping[stock] = f"Sector_{sector_id:02d}"

    predictions['sector'] = predictions['stock_code'].map(sector_mapping)

    # Fill any missing sectors
    predictions['sector'] = predictions['sector'].fillna('Sector_Unknown')

    print(f"  Assigned {predictions['sector'].nunique()} sectors")

    return predictions


def main():
    """Main execution function"""
    start_time = time.time()

    print("=" * 80)
    print("【Phase P.1 — Production-Level Portfolio & Risk Pipeline】")
    print("=" * 80)
    print()

    # Configuration
    BASE_DIR = Path(__file__).parent.parent
    ML2_RESULTS_DIR = BASE_DIR / 'data' / 'ml2_results'
    DATA_DIR = BASE_DIR / 'data'
    OUTPUT_DIR = BASE_DIR / 'data' / 'p1_results'

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Parameters
    TRANSACTION_COST_BPS = 10.0  # 10 bps
    MAX_STOCK_WEIGHT = 0.10      # 10% max per stock
    N_STOCKS = 20                # Hold 20 stocks
    SECTOR_NEUTRAL = True        # Apply sector neutralization
    INITIAL_CAPITAL = 1_000_000  # $1M

    print("Configuration:")
    print(f"  Transaction Cost: {TRANSACTION_COST_BPS} bps")
    print(f"  Max Stock Weight: {MAX_STOCK_WEIGHT * 100}%")
    print(f"  Number of Stocks: {N_STOCKS}")
    print(f"  Sector Neutral: {SECTOR_NEUTRAL}")
    print(f"  Initial Capital: ${INITIAL_CAPITAL:,.0f}")
    print()

    # Step 1: Load ML.2 predictions
    predictions_file = ML2_RESULTS_DIR / 'predictions_8window.parquet'
    if not predictions_file.exists():
        print(f"ERROR: Predictions file not found: {predictions_file}")
        print("Please run ML.2 first to generate predictions.")
        return

    predictions = load_ml2_predictions(str(predictions_file))
    print()

    # Step 2: Add sector information
    predictions = add_sector_info(predictions)
    print()

    # Step 3: Load price data
    try:
        price_data = load_price_data(str(DATA_DIR))
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Using predictions data as price data fallback...")
        # Create minimal price data from predictions
        price_data = predictions[['date', 'stock_code']].copy()
        price_data['close'] = 100.0  # Dummy price
        price_data['volume'] = 1000000  # Dummy volume
    print()

    # Step 4: Load stock data
    try:
        stock_data = load_stock_data(str(DATA_DIR))
    except Exception as e:
        print(f"WARNING: {e}")
        print("Using price data as stock data fallback...")
        stock_data = price_data.copy()
        if 'market_cap' not in stock_data.columns:
            stock_data['market_cap'] = stock_data['close'] * stock_data.get('volume', 1000000)
    print()

    # Step 5: Initialize backtester
    print("Initializing production backtester...")
    backtester = ProductionBacktester(
        transaction_cost_bps=TRANSACTION_COST_BPS,
        max_stock_weight=MAX_STOCK_WEIGHT,
        n_stocks=N_STOCKS,
        sector_neutral=SECTOR_NEUTRAL,
        initial_capital=INITIAL_CAPITAL
    )
    print()

    # Step 6: Run backtest
    print("Running production backtest...")
    print()

    try:
        results = backtester.run_backtest(
            predictions=predictions,
            price_data=price_data,
            stock_data=stock_data
        )
    except Exception as e:
        print(f"ERROR during backtest: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 7: Save results
    print("Saving results...")
    results['portfolio_returns'].to_parquet(OUTPUT_DIR / 'portfolio_returns.parquet')
    results['trade_records'].to_parquet(OUTPUT_DIR / 'trade_records.parquet')
    results['target_weights'].to_parquet(OUTPUT_DIR / 'target_weights.parquet')
    results['processed_signals'].to_parquet(OUTPUT_DIR / 'processed_signals.parquet')
    results['risk_exposures'].to_parquet(OUTPUT_DIR / 'risk_exposures.parquet')

    # Save report
    with open(OUTPUT_DIR / 'backtest_report.txt', 'w') as f:
        f.write(results['report'])

    print(f"  Results saved to: {OUTPUT_DIR}")
    print()

    # Step 8: Print report
    print(results['report'])

    # Final timing
    elapsed = time.time() - start_time
    print()
    print(f"Total runtime: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    print()


if __name__ == '__main__':
    main()
