"""
Phase P.1.2 Main Execution Script
Multi-dimensional experiments to reduce turnover and improve Sharpe

Experiments:
A. Rebalance frequency (1d, 5d, 10d)
B. Turnover penalty (0.0, 0.5, 1.0)
C. Hold buffer (0%, 25%, 50%)
D. Bucket width (Top20, Top30, Top50)
"""
import sys
import os
import time
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

sys.path.append(str(Path(__file__).parent.parent))

from portfolio_lab.market_data_loader import MarketDataLoader
from portfolio_lab.production_backtester_v2 import ProductionBacktesterV2


def print_config():
    """Print Phase P.1.2 configuration"""
    print("=" * 80)
    print("【Phase P.1.2 Configuration】")
    print("=" * 80)
    print()
    print("✅ Phase P.1.2 = ON")
    print("❌ B.2 Alpha Factory = frozen")
    print("✅ ML.2 predictions = reused")
    print("✅ Real OHLCV = ON")
    print("✅ T+1 close execution = ON")
    print("❌ Synthetic price = OFF")
    print()
    print("Experiment Grid:")
    print("  Rebalance frequency: [1d, 5d, 10d]")
    print("  Turnover penalty: [0.0, 0.5, 1.0]")
    print("  Hold buffer: [0%, 25%, 50%]")
    print("  Bucket width: [Top20, Top30, Top50]")
    print()
    print("Fixed Parameters:")
    print("  Sector neutrality: ON")
    print("  Max stock weight: 10%")
    print("  Transaction cost: 10 bps")
    print("  Initial capital: $1,000,000")
    print()
    print("=" * 80)
    print()


def load_data():
    """Load predictions and market data"""
    print("=" * 80)
    print("【Loading Data】")
    print("=" * 80)
    print()

    BASE_DIR = Path(__file__).parent.parent
    ML2_RESULTS_DIR = BASE_DIR / 'data' / 'ml2_results'
    DATA_LAKE_PATH = Path('${GODFATHER_DATA_LAKE_ROOT:-./data/data_lake}/prices')

    # Load predictions
    print("Loading ML.2 predictions...")
    predictions = pd.read_parquet(ML2_RESULTS_DIR / 'predictions_8window.parquet')
    predictions = predictions.rename(columns={
        'timestamp': 'date',
        'symbol': 'stock_code',
        'y_pred': 'prediction'
    })
    predictions['date'] = pd.to_datetime(predictions['date'])
    print(f"  Loaded {len(predictions)} predictions")
    print(f"  Date range: {predictions['date'].min()} to {predictions['date'].max()}")
    print()

    # Load market data
    print("Loading real OHLCV data...")
    loader = MarketDataLoader(str(DATA_LAKE_PATH))
    market_data = loader.load_all_prices()
    print()

    # Prepare for backtest
    price_data, stock_data = loader.prepare_for_backtest(
        market_data,
        start_date=predictions['date'].min(),
        end_date=predictions['date'].max()
    )

    # Add sector info
    sector_map = market_data[['symbol', 'sector']].drop_duplicates().set_index('symbol')['sector'].to_dict()
    predictions['sector'] = predictions['stock_code'].map(sector_map)
    predictions['sector'] = predictions['sector'].fillna('Unknown')

    print()
    return predictions, price_data, stock_data


def run_experiment_a(predictions, price_data, stock_data, output_dir):
    """Experiment A: Rebalance Frequency"""
    print("=" * 80)
    print("【Experiment A: Rebalance Frequency】")
    print("=" * 80)
    print()

    frequencies = [1, 5, 10]
    results = []

    for freq in frequencies:
        print(f"\nTesting {freq}-day rebalance frequency...")
        print("-" * 80)

        backtester = ProductionBacktesterV2(
            transaction_cost_bps=10.0,
            max_stock_weight=0.10,
            n_stocks=20,
            sector_neutral=True,
            initial_capital=1_000_000,
            rebalance_frequency=freq,
            turnover_penalty=0.0,
            hold_buffer_percentile=0.0
        )

        result = backtester.run_backtest(
            predictions,
            price_data,
            stock_data,
            verbose=False
        )

        metrics = result['metrics']
        results.append({
            'frequency': f'{freq}d',
            'annual_return': metrics.get('annualized_return', 0) * 100,
            'volatility': metrics.get('volatility', 0) * 100,
            'sharpe': metrics.get('sharpe_ratio', 0),
            'max_drawdown': metrics.get('max_drawdown', 0) * 100,
            'avg_turnover': metrics.get('avg_turnover', 0) * 100,
            'total_cost': result['trade_records']['cost'].sum() if len(result['trade_records']) > 0 else 0
        })

        print(result['report'])
        print()

    # Save results
    results_df = pd.DataFrame(results)
    results_df.to_csv(output_dir / 'experiment_a_frequency.csv', index=False)
    print("\n" + "=" * 80)
    print("Experiment A Summary:")
    print(results_df.to_string(index=False))
    print("=" * 80)
    print()

    return results_df


def run_experiment_b(predictions, price_data, stock_data, output_dir):
    """Experiment B: Turnover Penalty"""
    print("=" * 80)
    print("【Experiment B: Turnover Penalty】")
    print("=" * 80)
    print()

    penalties = [0.0, 0.5, 1.0]
    results = []

    for penalty in penalties:
        print(f"\nTesting turnover penalty = {penalty}...")
        print("-" * 80)

        backtester = ProductionBacktesterV2(
            transaction_cost_bps=10.0,
            max_stock_weight=0.10,
            n_stocks=20,
            sector_neutral=True,
            initial_capital=1_000_000,
            rebalance_frequency=5,  # Use 5d as baseline
            turnover_penalty=penalty,
            hold_buffer_percentile=0.0
        )

        result = backtester.run_backtest(
            predictions,
            price_data,
            stock_data,
            verbose=False
        )

        metrics = result['metrics']
        results.append({
            'penalty': penalty,
            'annual_return': metrics.get('annualized_return', 0) * 100,
            'volatility': metrics.get('volatility', 0) * 100,
            'sharpe': metrics.get('sharpe_ratio', 0),
            'max_drawdown': metrics.get('max_drawdown', 0) * 100,
            'avg_turnover': metrics.get('avg_turnover', 0) * 100,
            'total_cost': result['trade_records']['cost'].sum() if len(result['trade_records']) > 0 else 0
        })

        print(result['report'])
        print()

    # Save results
    results_df = pd.DataFrame(results)
    results_df.to_csv(output_dir / 'experiment_b_penalty.csv', index=False)
    print("\n" + "=" * 80)
    print("Experiment B Summary:")
    print(results_df.to_string(index=False))
    print("=" * 80)
    print()

    return results_df


def run_experiment_c(predictions, price_data, stock_data, output_dir):
    """Experiment C: Hold Buffer"""
    print("=" * 80)
    print("【Experiment C: Hold Buffer / No-Trade Band】")
    print("=" * 80)
    print()

    buffers = [0.0, 0.25, 0.50]
    buffer_names = ['No buffer', 'Narrow (25%)', 'Wide (50%)']
    results = []

    for buffer, name in zip(buffers, buffer_names):
        print(f"\nTesting hold buffer = {name}...")
        print("-" * 80)

        backtester = ProductionBacktesterV2(
            transaction_cost_bps=10.0,
            max_stock_weight=0.10,
            n_stocks=20,
            sector_neutral=True,
            initial_capital=1_000_000,
            rebalance_frequency=5,
            turnover_penalty=0.0,
            hold_buffer_percentile=buffer
        )

        result = backtester.run_backtest(
            predictions,
            price_data,
            stock_data,
            verbose=False
        )

        metrics = result['metrics']
        results.append({
            'buffer': name,
            'annual_return': metrics.get('annualized_return', 0) * 100,
            'volatility': metrics.get('volatility', 0) * 100,
            'sharpe': metrics.get('sharpe_ratio', 0),
            'max_drawdown': metrics.get('max_drawdown', 0) * 100,
            'avg_turnover': metrics.get('avg_turnover', 0) * 100,
            'total_cost': result['trade_records']['cost'].sum() if len(result['trade_records']) > 0 else 0
        })

        print(result['report'])
        print()

    results_df = pd.DataFrame(results)
    results_df.to_csv(output_dir / 'experiment_c_buffer.csv', index=False)
    print("\n" + "=" * 80)
    print("Experiment C Summary:")
    print(results_df.to_string(index=False))
    print("=" * 80)
    print()

    return results_df


def run_experiment_d(predictions, price_data, stock_data, output_dir):
    """Experiment D: Bucket Width"""
    print("=" * 80)
    print("【Experiment D: Portfolio Bucket Width】")
    print("=" * 80)
    print()

    buckets = [20, 30, 50]
    results = []

    for n_stocks in buckets:
        print(f"\nTesting Top {n_stocks} stocks...")
        print("-" * 80)

        backtester = ProductionBacktesterV2(
            transaction_cost_bps=10.0,
            max_stock_weight=0.10,
            n_stocks=n_stocks,
            sector_neutral=True,
            initial_capital=1_000_000,
            rebalance_frequency=5,
            turnover_penalty=0.0,
            hold_buffer_percentile=0.25
        )

        result = backtester.run_backtest(
            predictions,
            price_data,
            stock_data,
            verbose=False
        )

        metrics = result['metrics']
        results.append({
            'bucket': f'Top{n_stocks}',
            'annual_return': metrics.get('annualized_return', 0) * 100,
            'volatility': metrics.get('volatility', 0) * 100,
            'sharpe': metrics.get('sharpe_ratio', 0),
            'max_drawdown': metrics.get('max_drawdown', 0) * 100,
            'avg_turnover': metrics.get('avg_turnover', 0) * 100,
            'total_cost': result['trade_records']['cost'].sum() if len(result['trade_records']) > 0 else 0
        })

        print(result['report'])
        print()

    results_df = pd.DataFrame(results)
    results_df.to_csv(output_dir / 'experiment_d_bucket.csv', index=False)
    print("\n" + "=" * 80)
    print("Experiment D Summary:")
    print(results_df.to_string(index=False))
    print("=" * 80)
    print()

    return results_df


def generate_final_report(exp_a, exp_b, exp_c, exp_d, output_dir):
    """Generate comprehensive final report"""
    print("\n" + "=" * 80)
    print("【Phase P.1.2 Final Report】")
    print("=" * 80)
    print()

    report = []
    report.append("=" * 80)
    report.append("【Phase P.1.2 — Turnover Reduction & Frequency Alignment】")
    report.append("=" * 80)
    report.append("")
    report.append("【A. Rebalance Frequency Experiment】")
    report.append("")
    report.append(exp_a.to_string(index=False))
    report.append("")
    best_freq = exp_a.loc[exp_a['sharpe'].idxmax()]
    report.append(f"✅ Best frequency: {best_freq['frequency']}")
    report.append(f"   Sharpe: {best_freq['sharpe']:.4f}")
    report.append(f"   Turnover: {best_freq['avg_turnover']:.2f}%")
    report.append("")
    report.append("【B. Turnover Penalty Experiment】")
    report.append("")
    report.append(exp_b.to_string(index=False))
    report.append("")
    best_penalty = exp_b.loc[exp_b['sharpe'].idxmax()]
    report.append(f"✅ Best penalty: {best_penalty['penalty']}")
    report.append(f"   Sharpe: {best_penalty['sharpe']:.4f}")
    report.append(f"   Turnover: {best_penalty['avg_turnover']:.2f}%")
    report.append("")
    report.append("【C. Hold Buffer Experiment】")
    report.append("")
    report.append(exp_c.to_string(index=False))
    report.append("")
    best_buffer = exp_c.loc[exp_c['sharpe'].idxmax()]
    report.append(f"✅ Best buffer: {best_buffer['buffer']}")
    report.append(f"   Sharpe: {best_buffer['sharpe']:.4f}")
    report.append(f"   Turnover: {best_buffer['avg_turnover']:.2f}%")
    report.append("")
    report.append("【D. Bucket Width Experiment】")
    report.append("")
    report.append(exp_d.to_string(index=False))
    report.append("")
    best_bucket = exp_d.loc[exp_d['sharpe'].idxmax()]
    report.append(f"✅ Best bucket: {best_bucket['bucket']}")
    report.append(f"   Sharpe: {best_bucket['sharpe']:.4f}")
    report.append("")
    report.append("【E. Optimal Configuration】")
    report.append(f"Rebalance Frequency: {best_freq['frequency']}")
    report.append(f"Turnover Penalty: {best_penalty['penalty']}")
    report.append(f"Hold Buffer: {best_buffer['buffer']}")
    report.append(f"Bucket Width: {best_bucket['bucket']}")
    report.append("")
    report.append("【F. P.1.1 vs P.1.2 Comparison】")
    report.append("P.1.1: Sharpe 0.0946, Turnover 199.5%")
    report.append(f"P.1.2: Sharpe {best_freq['sharpe']:.4f}, Turnover {best_freq['avg_turnover']:.2f}%")
    report.append("")
    report.append("=" * 80)

    report_text = "\n".join(report)
    with open(output_dir / 'phase_p1_2_final_report.txt', 'w') as f:
        f.write(report_text)
    print(report_text)
    return report_text


def main():
    start_time = time.time()
    print_config()
    BASE_DIR = Path(__file__).parent.parent
    OUTPUT_DIR = BASE_DIR / 'data' / 'p1_2_results'
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    predictions, price_data, stock_data = load_data()
    exp_a = run_experiment_a(predictions, price_data, stock_data, OUTPUT_DIR)
    exp_b = run_experiment_b(predictions, price_data, stock_data, OUTPUT_DIR)
    exp_c = run_experiment_c(predictions, price_data, stock_data, OUTPUT_DIR)
    exp_d = run_experiment_d(predictions, price_data, stock_data, OUTPUT_DIR)
    generate_final_report(exp_a, exp_b, exp_c, exp_d, OUTPUT_DIR)
    elapsed = time.time() - start_time
    print(f"\nTotal runtime: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")


if __name__ == '__main__':
    main()
