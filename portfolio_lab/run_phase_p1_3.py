"""
Phase P.1.3 Main Execution Script
Production-Grade Audit: Beta Stripping + Lag Curve + Capacity/Impact

Three Core Questions:
1. Is Sharpe 2.23 from alpha or market beta?
2. Is T+2 anomaly a bug or real signal persistence?
3. What is the strategy capacity limit?
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
from portfolio_lab.beta_audit import BetaAuditor
from portfolio_lab.lag_curve_audit import LagCurveAuditor
from portfolio_lab.capacity_audit import CapacityAuditor


def print_config():
    """Print Phase P.1.3 configuration"""
    print("=" * 80)
    print("【Phase P.1.3 — Production-Grade Audit】")
    print("=" * 80)
    print()
    print("✅ Phase P.1.3 = ON")
    print("✅ Beta Stripping Audit = ON")
    print("✅ Lag Curve Audit = ON")
    print("✅ Capacity/Impact Cost Audit = ON")
    print()
    print("Frozen Parameters (from P.1.2 optimal config):")
    print("  - Rebalance frequency: Every 5 days")
    print("  - Hold buffer: 50%")
    print("  - Portfolio size: Top 20 stocks")
    print("  - Execution: T+1 close")
    print("  - Transaction cost: 10 bps")
    print("  - Sector neutral: ON")
    print("  - Max stock weight: 10%")
    print()
    print("Three Core Questions:")
    print("  1. Is Sharpe 2.23 from alpha or market beta?")
    print("  2. Is T+2 anomaly a bug or real signal persistence?")
    print("  3. What is the strategy capacity limit?")
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
    return predictions, price_data, stock_data, market_data


def run_baseline_backtest(predictions, price_data, stock_data):
    """Run baseline backtest with P.1.2 optimal config"""
    print("=" * 80)
    print("【Running Baseline Backtest】")
    print("=" * 80)
    print()

    backtester = ProductionBacktesterV2(
        transaction_cost_bps=10.0,
        max_stock_weight=0.10,
        n_stocks=20,
        sector_neutral=True,
        initial_capital=1_000_000,
        rebalance_frequency=5,
        turnover_penalty=0.0,
        hold_buffer_percentile=0.50
    )

    result = backtester.run_backtest(
        predictions,
        price_data,
        stock_data,
        verbose=True
    )

    print("\n" + "=" * 80)
    print("【Baseline Results】")
    print("=" * 80)
    print(result['report'])
    print()

    return result, backtester


def run_module_a_beta_audit(result, price_data, predictions):
    """Module A: Beta Stripping Audit"""
    print("\n" + "=" * 80)
    print("【Module A: Beta Stripping Audit】")
    print("=" * 80)
    print()

    auditor = BetaAuditor()

    # 1. Construct market benchmark
    benchmark = auditor.construct_market_benchmark(
        price_data,
        method='equal_weight'
    )

    # 2. Calculate strategy beta
    strategy_returns = result['portfolio_returns'][['date', 'return']].copy()
    beta_result = auditor.calculate_beta(
        strategy_returns,
        benchmark,
        window=60
    )

    # 3. Create beta-hedged returns
    overall_beta = beta_result['beta'].iloc[0]
    hedged_returns = auditor.create_beta_hedged_returns(
        strategy_returns,
        benchmark,
        beta=overall_beta
    )

    # 4. Compare performance
    comparison = auditor.compare_performance(
        strategy_returns,
        benchmark,
        hedged_returns
    )

    return {
        'benchmark': benchmark,
        'beta_result': beta_result,
        'hedged_returns': hedged_returns,
        'comparison': comparison,
        'overall_beta': overall_beta
    }


def run_module_b_lag_curve(predictions, price_data, stock_data):
    """Module B: Lag Curve Audit"""
    print("\n" + "=" * 80)
    print("【Module B: Lag Curve Audit】")
    print("=" * 80)
    print()

    auditor = LagCurveAuditor()

    lag_result = auditor.run_lag_curve_test(
        predictions,
        price_data,
        stock_data,
        ProductionBacktesterV2,
        lags=[1, 2, 3, 5]
    )

    return lag_result


def run_module_c_capacity(predictions, price_data, stock_data):
    """Module C: Capacity/Impact Cost Audit"""
    print("\n" + "=" * 80)
    print("【Module C: Capacity/Impact Cost Audit】")
    print("=" * 80)
    print()

    auditor = CapacityAuditor()

    capacity_result = auditor.run_capacity_test(
        predictions,
        price_data,
        stock_data,
        ProductionBacktesterV2,
        capital_tiers=[1_000_000, 10_000_000, 50_000_000]
    )

    return capacity_result


def generate_final_report(
    baseline_result,
    beta_audit,
    lag_curve,
    capacity,
    output_dir
):
    """Generate comprehensive Phase P.1.3 report"""
    print("\n" + "=" * 80)
    print("【Phase P.1.3 Final Report】")
    print("=" * 80)
    print()

    report = []
    report.append("=" * 80)
    report.append("【Phase P.1.3 — Production-Grade Audit Report】")
    report.append("=" * 80)
    report.append("")

    # Section 0: Executive Summary
    report.append("【Executive Summary】")
    report.append("")

    baseline_metrics = baseline_result['metrics']
    baseline_sharpe = baseline_metrics.get('sharpe_ratio', 0)
    baseline_return = baseline_metrics.get('annualized_return', 0)

    report.append(f"Baseline Performance (P.1.2 Optimal Config):")
    report.append(f"  Annual Return: {baseline_return*100:.2f}%")
    report.append(f"  Sharpe Ratio: {baseline_sharpe:.4f}")
    report.append(f"  Max Drawdown: {baseline_metrics.get('max_drawdown', 0)*100:.2f}%")
    report.append("")

    # Section A: Beta Stripping Results
    report.append("【A. Beta Stripping Audit】")
    report.append("")

    overall_beta = beta_audit['overall_beta']
    comparison = beta_audit['comparison']

    strategy_metrics = comparison['strategy']
    benchmark_metrics = comparison['benchmark']
    hedged_metrics = comparison.get('hedged', {})

    report.append(f"Market Beta: {overall_beta:.4f}")
    report.append(f"Correlation to Market: {beta_audit['beta_result']['correlation'].iloc[0]:.4f}")
    report.append("")

    report.append("Performance Breakdown:")
    report.append(f"  Strategy (Long-Only): Sharpe {strategy_metrics.get('sharpe', 0):.4f}")
    report.append(f"  Market Benchmark: Sharpe {benchmark_metrics.get('sharpe', 0):.4f}")
    report.append(f"  Beta-Hedged (Alpha): Sharpe {hedged_metrics.get('sharpe', 0):.4f}")
    report.append("")

    # Assess alpha vs beta
    hedged_sharpe = hedged_metrics.get('sharpe', 0)
    if hedged_sharpe > 1.5:
        report.append("✅ STRONG ALPHA: Beta-hedged Sharpe > 1.5")
        report.append("   Strategy generates significant alpha independent of market")
        alpha_verdict = "PASS"
    elif hedged_sharpe > 1.0:
        report.append("✅ MODERATE ALPHA: Beta-hedged Sharpe > 1.0")
        report.append("   Strategy has genuine alpha but some beta exposure")
        alpha_verdict = "PASS"
    elif hedged_sharpe > 0.5:
        report.append("⚠️  WEAK ALPHA: Beta-hedged Sharpe 0.5-1.0")
        report.append("   Strategy has some alpha but heavily relies on market beta")
        alpha_verdict = "WARNING"
    else:
        report.append("❌ NO ALPHA: Beta-hedged Sharpe < 0.5")
        report.append("   Strategy performance primarily from market beta, not alpha")
        alpha_verdict = "FAIL"
    report.append("")

    # Section B: Lag Curve Results
    report.append("【B. Lag Curve Audit】")
    report.append("")

    lag_results = lag_curve['results']
    baseline_lag_sharpe = lag_curve['baseline_sharpe']

    report.append("Signal Decay Analysis:")
    for _, row in lag_results.iterrows():
        decay_pct = ((row['sharpe'] - baseline_lag_sharpe) / baseline_lag_sharpe * 100) if baseline_lag_sharpe != 0 else 0
        report.append(f"  {row['lag']}: Sharpe {row['sharpe']:.4f} (decay {decay_pct:+.1f}%)")
    report.append("")

    # Assess T+2 anomaly
    t1_sharpe = lag_results[lag_results['lag_days'] == 1]['sharpe'].iloc[0]
    t2_sharpe = lag_results[lag_results['lag_days'] == 2]['sharpe'].iloc[0]
    t1_to_t2_decay = ((t2_sharpe - t1_sharpe) / t1_sharpe * 100) if t1_sharpe != 0 else 0

    report.append(f"T+1 → T+2 Decay: {t1_to_t2_decay:+.1f}%")
    report.append("")

    if abs(t1_to_t2_decay) < 5:
        report.append("⚠️  T+2 ANOMALY CONFIRMED")
        report.append("   Signal shows minimal decay from T+1 to T+2")
        report.append("   Possible genuine signal persistence or implementation issue")
        lag_verdict = "WARNING"
    elif t1_to_t2_decay < -10:
        report.append("✅ NORMAL SIGNAL DECAY")
        report.append("   Signal decays as expected with execution delay")
        lag_verdict = "PASS"
    else:
        report.append("⚠️  UNUSUAL DECAY PATTERN")
        lag_verdict = "WARNING"
    report.append("")

    # Section C: Capacity Results
    report.append("【C. Capacity/Impact Cost Audit】")
    report.append("")

    capacity_results = capacity['results']

    report.append("Capacity Test Results:")
    for _, row in capacity_results.iterrows():
        capital_str = f"${row['capital']/1e6:.0f}M" if row['capital'] >= 1e6 else f"${row['capital']/1e3:.0f}K"
        degradation = row['adjusted_sharpe'] - row['baseline_sharpe']
        report.append(f"  {capital_str}: Adjusted Sharpe {row['adjusted_sharpe']:.4f} "
                     f"(degradation {degradation:+.4f}, impact cost {row['impact_cost_pct']*100:.2f}%)")
    report.append("")

    # Assess capacity
    baseline_cap_sharpe = capacity_results.iloc[0]['baseline_sharpe']
    max_degradation = min((capacity_results['adjusted_sharpe'] - baseline_cap_sharpe) / baseline_cap_sharpe * 100)

    if max_degradation > -10:
        report.append("✅ EXCELLENT CAPACITY: < 10% Sharpe degradation")
        report.append(f"   Strategy scales well up to ${capacity_results.iloc[-1]['capital']/1e6:.0f}M")
        capacity_verdict = "PASS"
    elif max_degradation > -20:
        report.append("✅ GOOD CAPACITY: < 20% Sharpe degradation")
        report.append(f"   Strategy viable up to ${capacity_results.iloc[-1]['capital']/1e6:.0f}M")
        capacity_verdict = "PASS"
    else:
        report.append("⚠️  LIMITED CAPACITY: > 20% Sharpe degradation")
        report.append("   Strategy capacity constrained by market impact")
        capacity_verdict = "WARNING"
    report.append("")

    # Section D: Final Assessment
    report.append("【D. Final Production Readiness Assessment】")
    report.append("")

    report.append("Three Core Questions Answered:")
    report.append("")
    report.append(f"1. Is Sharpe 2.23 from alpha or market beta?")
    report.append(f"   → {alpha_verdict}: Beta-hedged Sharpe = {hedged_sharpe:.4f}")
    report.append(f"   → Beta to market = {overall_beta:.4f}")
    report.append("")
    report.append(f"2. Is T+2 anomaly a bug or real signal persistence?")
    report.append(f"   → {lag_verdict}: T+1→T+2 decay = {t1_to_t2_decay:+.1f}%")
    report.append("")
    report.append(f"3. What is the strategy capacity limit?")
    report.append(f"   → {capacity_verdict}: Max degradation = {max_degradation:.1f}%")
    report.append("")

    # Overall verdict
    verdicts = [alpha_verdict, lag_verdict, capacity_verdict]
    passes = verdicts.count("PASS")
    warnings = verdicts.count("WARNING")
    fails = verdicts.count("FAIL")

    report.append("【Overall Verdict】")
    report.append("")
    report.append(f"Audits Passed: {passes}/3")
    report.append(f"Warnings: {warnings}/3")
    report.append(f"Failures: {fails}/3")
    report.append("")

    if passes == 3:
        report.append("✅ PRODUCTION READY")
        report.append("")
        report.append("Strategy is ready for paper trading:")
        report.append("  - Strong alpha independent of market beta")
        report.append("  - Signal decay is acceptable")
        report.append("  - Capacity supports target capital")
        report.append("")
        report.append("Recommended Next Steps:")
        report.append("  1. Set up paper trading infrastructure")
        report.append("  2. Implement real-time execution system")
        report.append("  3. Monitor live performance vs backtest")
        report.append("  4. Prepare risk management framework")
    elif passes >= 2 and fails == 0:
        report.append("⚠️  CONDITIONAL PASS")
        report.append("")
        report.append("Strategy shows promise but has concerns:")
        report.append("  - Address specific warnings above")
        report.append("  - Consider additional validation")
        report.append("  - Start with smaller capital allocation")
        report.append("")
        report.append("Recommended Next Steps:")
        report.append("  1. Investigate warning areas in detail")
        report.append("  2. Run extended out-of-sample test")
        report.append("  3. Consider paper trading with reduced size")
    else:
        report.append("❌ NOT PRODUCTION READY")
        report.append("")
        report.append("Strategy has significant issues:")
        report.append("  - Critical concerns identified above")
        report.append("  - Do not proceed to paper trading")
        report.append("")
        report.append("Recommended Next Steps:")
        report.append("  1. Address all failures and warnings")
        report.append("  2. Review implementation for bugs")
        report.append("  3. Consider alternative approaches")
        report.append("  4. Re-run full audit after fixes")

    report.append("")
    report.append("=" * 80)
    report.append("✅ Phase P.1.3 Audit Complete!")
    report.append("=" * 80)

    report_text = "\n".join(report)

    # Save report
    with open(output_dir / 'phase_p1_3_audit_report.txt', 'w') as f:
        f.write(report_text)

    print(report_text)

    return report_text


def main():
    """Main execution function"""
    start_time = time.time()

    print_config()

    # Setup output directory
    BASE_DIR = Path(__file__).parent.parent
    OUTPUT_DIR = BASE_DIR / 'data' / 'p1_3_audit'
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load data
    predictions, price_data, stock_data, market_data = load_data()

    # Run baseline backtest
    baseline_result, backtester = run_baseline_backtest(predictions, price_data, stock_data)

    # Run Module A: Beta Stripping
    beta_audit = run_module_a_beta_audit(baseline_result, price_data, predictions)

    # Run Module B: Lag Curve
    lag_curve = run_module_b_lag_curve(predictions, price_data, stock_data)

    # Run Module C: Capacity
    capacity = run_module_c_capacity(predictions, price_data, stock_data)

    # Generate final report
    generate_final_report(
        baseline_result,
        beta_audit,
        lag_curve,
        capacity,
        OUTPUT_DIR
    )

    # Final timing
    elapsed = time.time() - start_time
    print()
    print(f"Total audit runtime: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    print()


if __name__ == '__main__':
    main()
