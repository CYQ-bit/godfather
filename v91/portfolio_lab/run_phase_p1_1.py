"""
Phase P.1.1 Main Execution Script
REAL OHLCV DATA VERSION - Replaces synthetic price generation

Key differences from P.1:
- Uses REAL market data from v8_empire data_lake
- NO synthetic price generation from target returns
- Proper T+1 execution validation
- Real transaction cost impact
- Accurate performance metrics
"""
import sys
import os
import time
import pandas as pd
import numpy as np
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from portfolio_lab.market_data_loader import MarketDataLoader
from portfolio_lab.production_backtester import ProductionBacktester


def print_config():
    """Print Phase P.1.1 configuration"""
    print("=" * 80)
    print("【Phase P.1.1 Configuration】")
    print("=" * 80)
    print()
    print("✅ Phase P.1.1 = ON")
    print("❌ Synthetic price = OFF")
    print("✅ Real OHLCV = ON")
    print("✅ T+1 close execution = ON")
    print("✅ Sector neutrality = ON")
    print("✅ Barra-lite monitoring = ON")
    print()
    print("Data Source:")
    print("  Path: ${GODFATHER_DATA_LAKE_ROOT:-./data/data_lake}/prices/")
    print("  Type: Real split-adjusted OHLCV")
    print("  Format: Per-symbol parquet files")
    print()
    print("Execution Assumptions:")
    print("  Signal generation: Day T")
    print("  Execution: Day T+1 close")
    print("  Transaction cost: 10 bps")
    print("  Max stock weight: 10%")
    print("  Number of stocks: 20")
    print("  Sector neutral: Yes")
    print()
    print("=" * 80)
    print()


def main():
    """Main execution function"""
    start_time = time.time()

    print_config()

    # Configuration
    BASE_DIR = Path(__file__).parent.parent
    ML2_RESULTS_DIR = BASE_DIR / 'data' / 'ml2_results'
    DATA_LAKE_PATH = Path('${GODFATHER_DATA_LAKE_ROOT:-./data/data_lake}/prices')
    OUTPUT_DIR = BASE_DIR / 'data' / 'p1_1_results'

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Parameters
    TRANSACTION_COST_BPS = 10.0
    MAX_STOCK_WEIGHT = 0.10
    N_STOCKS = 20
    SECTOR_NEUTRAL = True
    INITIAL_CAPITAL = 1_000_000

    # Step 1: Load ML.2 predictions
    print("=" * 80)
    print("【Step 1: Load ML.2 Predictions】")
    print("=" * 80)
    print()

    predictions_file = ML2_RESULTS_DIR / 'predictions_8window.parquet'
    if not predictions_file.exists():
        print(f"ERROR: Predictions file not found: {predictions_file}")
        return

    predictions = pd.read_parquet(predictions_file)

    # Map column names
    predictions = predictions.rename(columns={
        'timestamp': 'date',
        'symbol': 'stock_code',
        'y_pred': 'prediction'
    })

    predictions['date'] = pd.to_datetime(predictions['date'])

    print(f"Loaded {len(predictions)} predictions")
    print(f"Date range: {predictions['date'].min()} to {predictions['date'].max()}")
    print(f"Unique stocks: {predictions['stock_code'].nunique()}")
    print(f"Unique dates: {predictions['date'].nunique()}")
    print()

    # Step 2: Load REAL market data
    print("=" * 80)
    print("【Step 2: Load REAL Market Data】")
    print("=" * 80)
    print()

    loader = MarketDataLoader(str(DATA_LAKE_PATH))
    market_data = loader.load_all_prices()
    print()

    # Step 3: Data quality audit
    print("=" * 80)
    print("【Step 3: Data Quality Audit】")
    print("=" * 80)

    audit_results = loader.audit_data_quality(market_data)

    # Save audit results
    audit_df = pd.DataFrame([audit_results])
    audit_df.to_csv(OUTPUT_DIR / 'data_quality_audit.csv', index=False)
    print(f"\nAudit results saved to: {OUTPUT_DIR / 'data_quality_audit.csv'}")
    print()

    # Step 4: T+1 executability check
    t1_check = loader.check_t1_executability(
        market_data,
        predictions['date']
    )

    # Save T+1 check results
    t1_df = pd.DataFrame([t1_check])
    t1_df.to_csv(OUTPUT_DIR / 't1_executability.csv', index=False)
    print(f"T+1 check saved to: {OUTPUT_DIR / 't1_executability.csv'}")
    print()

    # Step 5: Prepare clean data for backtest
    print("=" * 80)
    print("【Step 5: Prepare Data for Backtest】")
    print("=" * 80)
    print()

    price_data, stock_data = loader.prepare_for_backtest(
        market_data,
        start_date=predictions['date'].min(),
        end_date=predictions['date'].max()
    )

    # Save clean market data
    price_data.to_parquet(OUTPUT_DIR / 'market_prices_clean.parquet')
    print(f"Clean price data saved to: {OUTPUT_DIR / 'market_prices_clean.parquet'}")
    print()

    # Step 6: Add sector info to predictions
    print("=" * 80)
    print("【Step 6: Merge Sector Information】")
    print("=" * 80)
    print()

    # Get sector mapping from market data
    sector_map = market_data[['symbol', 'sector']].drop_duplicates().set_index('symbol')['sector'].to_dict()

    predictions['sector'] = predictions['stock_code'].map(sector_map)
    predictions['sector'] = predictions['sector'].fillna('Unknown')

    print(f"Mapped sectors for {predictions['sector'].notna().sum()} predictions")
    print(f"Unique sectors: {predictions['sector'].nunique()}")
    print()

    # Step 7: Initialize backtester
    print("=" * 80)
    print("【Step 7: Initialize Production Backtester】")
    print("=" * 80)
    print()

    backtester = ProductionBacktester(
        transaction_cost_bps=TRANSACTION_COST_BPS,
        max_stock_weight=MAX_STOCK_WEIGHT,
        n_stocks=N_STOCKS,
        sector_neutral=SECTOR_NEUTRAL,
        initial_capital=INITIAL_CAPITAL
    )
    print("Backtester initialized")
    print()

    # Step 8: Run backtest with REAL prices
    print("=" * 80)
    print("【Step 8: Run Backtest with REAL Market Data】")
    print("=" * 80)
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

    # Step 9: Save results
    print("=" * 80)
    print("【Step 9: Save Results】")
    print("=" * 80)
    print()

    results['portfolio_returns'].to_parquet(OUTPUT_DIR / 'portfolio_returns.parquet')
    results['trade_records'].to_parquet(OUTPUT_DIR / 'trade_records.parquet')
    results['target_weights'].to_parquet(OUTPUT_DIR / 'target_weights.parquet')
    results['processed_signals'].to_parquet(OUTPUT_DIR / 'processed_signals.parquet')
    results['risk_exposures'].to_parquet(OUTPUT_DIR / 'risk_exposures.parquet')

    # Save report
    with open(OUTPUT_DIR / 'backtest_report.txt', 'w') as f:
        f.write(results['report'])

    print(f"All results saved to: {OUTPUT_DIR}")
    print()

    # Step 10: Print comprehensive report
    print(results['report'])

    # Step 11: Generate P.1 vs P.1.1 comparison
    print("\n" + "=" * 80)
    print("【P.1 vs P.1.1 Comparison】")
    print("=" * 80)
    print()
    print("P.1 (Synthetic Price - INVALID):")
    print("  - Used target returns to generate synthetic prices")
    print("  - Annual return: 3885% (UNREALISTIC)")
    print("  - Sharpe: 34.32 (UNREALISTIC)")
    print("  - Result: INVALID for trading decisions")
    print()
    print("P.1.1 (Real Market Data - VALID):")
    print("  - Uses actual split-adjusted OHLCV from v8_empire")
    print("  - Proper T+1 execution simulation")
    print("  - Real transaction costs applied")
    print("  - Result: See report above")
    print()
    print("=" * 80)

    # Final timing
    elapsed = time.time() - start_time
    print()
    print(f"✅ Phase P.1.1 完成！")
    print(f"Total runtime: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    print()


if __name__ == '__main__':
    main()
