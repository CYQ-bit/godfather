"""
Paper Trading Main Execution Script - Godfather V9.0 Phase PT.1.1
End-of-day paper trading simulation with fixed accounting, buffer, and slippage
"""
import sys
import os
import time
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

sys.path.append(str(Path(__file__).parent.parent))

from paper_trading.market_data_feed import MarketDataFeed
from paper_trading.signal_runner import SignalRunner
from paper_trading.portfolio_constructor import PortfolioConstructor
from paper_trading.paper_broker import PaperBroker
from paper_trading.execution_monitor import ExecutionMonitor
from paper_trading.risk_guard import RiskGuard
from paper_trading.drift_monitor import DriftMonitor
from paper_trading.reporting import ReportGenerator
from runtime_paths import get_price_lake_dir


def print_config():
    """Print Godfather V9.0 Phase PT.1.1a configuration"""
    print("=" * 80)
    print("【Godfather V9.0 - Phase PT.1.1a】")
    print("Paper Trading Infrastructure - Hot Fix Version")
    print("=" * 80)
    print()
    print("System Configuration:")
    print("  Godfather Version = V9.0")
    print("  Phase = PT.1.1a")
    print("  Real OHLCV = ON")
    print("  Synthetic price = OFF")
    print("  ML model = frozen (ML.2 8-window)")
    print("  Portfolio config = frozen from P.1.2")
    print()
    print("Frozen Portfolio Parameters:")
    print("  Rebalance frequency = every 5 days")
    print("  Hold buffer = 50%")
    print("  Top bucket = 20 stocks")
    print("  Sector neutrality = ON")
    print("  Max stock weight = 10%")
    print("  T+1 close execution = ON")
    print()
    print("PT.1.1 Fixes:")
    print("  ✅ Mark-to-market accounting = ON")
    print("  ✅ Buffer retention logic = ON")
    print("  ✅ Slippage decomposition = ON")
    print()
    print("PT.1.1a Hot Fixes:")
    print("  ✅ Pre-trade cash constraint = ON")
    print("  ✅ Risk guard threshold correction = ON")
    print("  ✅ Ex-first-turnover audit = ON")
    print()
    print("Execution Mode:")
    print("  Paper broker = ON")
    print("  Real broker routing = OFF")
    print("  Transaction cost = 10 bps")
    print()
    print("=" * 80)
    print()


def initialize_components():
    """Initialize all paper trading components"""
    print("=" * 80)
    print("【Initializing Components - Godfather V9.0 PT.1.1】")
    print("=" * 80)
    print()

    BASE_DIR = Path(__file__).parent.parent
    DATA_LAKE_PATH = get_price_lake_dir()
    ML2_PREDICTIONS_PATH = BASE_DIR / 'data' / 'ml2_results' / 'predictions_8window.parquet'
    OUTPUT_DIR = BASE_DIR / 'data' / 'paper_trading'

    # 1. Market Data Feed
    market_feed = MarketDataFeed(
        data_source_path=str(DATA_LAKE_PATH),
        mode='eod'
    )

    # 2. Signal Runner
    signal_runner = SignalRunner(
        predictions_path=str(ML2_PREDICTIONS_PATH),
        model_version="ML.2_8window",
        feature_version="B.2_frozen"
    )

    # 3. Portfolio Constructor (P.1.2 optimal config with fixed buffer)
    portfolio_constructor = PortfolioConstructor(
        n_stocks=20,
        max_stock_weight=0.10,
        sector_neutral=True,
        hold_buffer_percentile=0.50,
        rebalance_frequency=5
    )

    # 4. Paper Broker (with mark-to-market accounting)
    paper_broker = PaperBroker(
        transaction_cost_bps=10.0,
        initial_capital=1_000_000
    )

    # 5. Execution Monitor (with slippage decomposition)
    execution_monitor = ExecutionMonitor()

    # 6. Risk Guard
    risk_guard = RiskGuard(
        max_gross_exposure=1.0,
        max_net_exposure=1.0,
        min_net_exposure=0.9,
        max_single_stock_weight=0.10,
        max_sector_exposure=0.30,
        max_daily_loss=0.05,
        max_consecutive_loss_days=3,
        max_drawdown=0.20,
        max_unfilled_rate=0.10,
        max_execution_slippage_bps=50.0,
        max_implementation_shortfall_bps=500.0,
        max_turnover=1.0
    )

    # 7. Drift Monitor (baseline from P.1.3)
    baseline_metrics = {
        'sharpe': 2.2341,
        'avg_turnover': 0.4014,
        'max_drawdown': -0.2949,
        'score_mean': 0.0,
        'score_std': 1.0,
        'avg_cost_pct': 0.0024
    }

    drift_monitor = DriftMonitor(
        baseline_metrics=baseline_metrics,
        drift_threshold=0.20
    )

    # 8. Report Generator
    report_generator = ReportGenerator(
        output_dir=str(OUTPUT_DIR)
    )

    print()
    return {
        'market_feed': market_feed,
        'signal_runner': signal_runner,
        'portfolio_constructor': portfolio_constructor,
        'paper_broker': paper_broker,
        'execution_monitor': execution_monitor,
        'risk_guard': risk_guard,
        'drift_monitor': drift_monitor,
        'report_generator': report_generator,
        'output_dir': OUTPUT_DIR
    }


def run_single_day(
    components: dict,
    signal_date: str,
    sector_map: dict
) -> dict:
    """
    Run paper trading for a single day

    Args:
        components: Dictionary of initialized components
        signal_date: Signal generation date
        sector_map: Sector mapping

    Returns:
        Dictionary with daily results
    """
    print("\n" + "=" * 80)
    print(f"【Running Paper Trading for {signal_date}】")
    print("=" * 80)
    print()

    market_feed = components['market_feed']
    signal_runner = components['signal_runner']
    portfolio_constructor = components['portfolio_constructor']
    paper_broker = components['paper_broker']
    execution_monitor = components['execution_monitor']
    risk_guard = components['risk_guard']
    drift_monitor = components['drift_monitor']
    report_generator = components['report_generator']
    output_dir = components['output_dir']

    # Step 1: Generate signal
    print("Step 1: Generating signal...")
    signal_data = signal_runner.generate_signal(signal_date, sector_map)

    if len(signal_data) == 0:
        print("⚠️  No signal data available. Skipping this day.")
        return {'status': 'skipped', 'reason': 'no_signal'}

    signal_summary = signal_runner.get_signal_summary(signal_data)

    # Save signal
    signal_runner.save_signal(signal_data, output_dir / 'signals', signal_date)

    # Step 2: Construct target portfolio
    print("\nStep 2: Constructing target portfolio...")
    target_portfolio = portfolio_constructor.construct_target_portfolio(
        signal_data,
        signal_date
    )

    if len(target_portfolio) == 0:
        print("⏭️  No rebalance today.")

        # Still need to mark-to-market for non-rebalance days
        reference_prices = market_feed.get_latest_prices(
            list(paper_broker.positions.keys()) if len(paper_broker.positions) > 0 else [],
            as_of_date=signal_date
        )

        accounting_summary = paper_broker.get_accounting_summary(reference_prices) if len(reference_prices) > 0 else {
            'cash': paper_broker.cash,
            'holdings_value': 0,
            'total_value': paper_broker.cash,
            'unrealized_pnl': 0,
            'realized_pnl': paper_broker.realized_pnl,
            'total_pnl': paper_broker.realized_pnl,
            'total_transaction_costs': paper_broker.total_transaction_costs,
            'num_positions': 0,
            'return_pct': 0
        }

        portfolio_summary = {'status': 'No rebalance'}
        order_summary = {'status': 'No orders'}
        execution_summary = {'status': 'No fills'}
        risk_results = {'overall_status': 'OK', 'violations': []}
        drift_results = {'drift_detected': False}
    else:
        portfolio_summary = portfolio_constructor.get_portfolio_summary(target_portfolio)

        # Save target portfolio
        target_file = output_dir / 'targets' / f"{signal_date}.parquet"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_portfolio.to_parquet(target_file, index=False)
        print(f"✅ Target portfolio saved: {target_file}")

        # Step 3: Create orders
        print("\nStep 3: Creating orders...")
        signal_date_ts = pd.to_datetime(signal_date)
        intended_trade_date = market_feed.get_next_trading_day(signal_date)

        # Get reference prices (signal date close)
        all_symbols = list(set(signal_data['stock_code'].unique().tolist()) | set(paper_broker.positions.keys()))
        reference_prices = market_feed.get_latest_prices(
            all_symbols,
            as_of_date=signal_date
        )

        orders = paper_broker.create_orders(
            target_portfolio,
            signal_date,
            intended_trade_date,
            reference_prices
        )

        # Save orders
        if len(orders) > 0:
            orders_df = pd.DataFrame(orders)
            orders_file = output_dir / 'orders' / f"{signal_date}.parquet"
            orders_file.parent.mkdir(parents=True, exist_ok=True)
            orders_df.to_parquet(orders_file, index=False)
            print(f"✅ Orders saved: {orders_file}")

        # Step 4: Simulate fills at T+1
        print("\nStep 4: Simulating order fills at T+1...")
        fill_prices = market_feed.get_latest_prices(
            [o['stock_code'] for o in orders],
            as_of_date=str(intended_trade_date.date())
        )

        fills = paper_broker.simulate_fills(
            orders,
            fill_prices,
            str(intended_trade_date.date())
        )

        # Save fills
        if len(fills) > 0:
            fills_df = pd.DataFrame(fills)
            fills_file = output_dir / 'fills' / f"{signal_date}.parquet"
            fills_file.parent.mkdir(parents=True, exist_ok=True)
            fills_df.to_parquet(fills_file, index=False)
            print(f"✅ Fills saved: {fills_file}")

        order_summary = paper_broker.get_order_summary()

        # Step 5: Analyze execution quality
        print("\nStep 5: Analyzing execution quality...")
        execution_summary = execution_monitor.analyze_execution(
            orders,
            fills,
            signal_date,
            str(intended_trade_date.date())
        )

        # Step 6: Update portfolio constructor holdings
        print("\nStep 6: Updating holdings...")
        if len(fills) > 0:
            realized_symbols = pd.DataFrame([
                {'stock_code': symbol, 'shares': shares}
                for symbol, shares in paper_broker.positions.items()
                if shares > 0
            ])
            portfolio_constructor.update_holdings(realized_symbols)

        # Step 7: Mark-to-market accounting
        print("\nStep 7: Mark-to-market accounting...")
        current_prices = market_feed.get_latest_prices(
            list(paper_broker.positions.keys()) if len(paper_broker.positions) > 0 else [],
            as_of_date=str(intended_trade_date.date())
        )
        accounting_summary = paper_broker.get_accounting_summary(current_prices)

        # Step 8: Run risk checks
        print("\nStep 8: Running risk checks...")
        _, risk_results = risk_guard.run_all_checks(
            target_portfolio=target_portfolio,
            orders=orders,
            fills=fills,
            turnover=portfolio_summary.get('expected_turnover', 0),
            execution_summary=execution_summary
        )

        # Step 9: Run drift checks
        print("\nStep 9: Running drift checks...")
        drift_results = drift_monitor.run_all_drift_checks(
            live_scores=signal_data['sector_neutral_score'],
            live_turnover=portfolio_summary.get('expected_turnover', 0)
        )

    # Step 10: Generate daily report
    print("\nStep 10: Generating daily report...")
    report_text = report_generator.generate_daily_report(
        date=signal_date,
        signal_summary=signal_summary,
        portfolio_summary=portfolio_summary,
        order_summary=order_summary,
        accounting_summary=accounting_summary,
        execution_summary=execution_summary,
        risk_results=risk_results,
        drift_results=drift_results
    )

    print(report_text)

    return {
        'status': 'completed',
        'signal_summary': signal_summary,
        'portfolio_summary': portfolio_summary,
        'order_summary': order_summary,
        'accounting_summary': accounting_summary,
        'execution_summary': execution_summary,
        'risk_results': risk_results,
        'drift_results': drift_results
    }


def main():
    """Main execution function"""
    start_time = time.time()

    print_config()

    # Initialize components
    components = initialize_components()

    # Load historical data
    print("=" * 80)
    print("【Loading Historical Data】")
    print("=" * 80)
    print()

    market_feed = components['market_feed']
    signal_runner = components['signal_runner']

    # Load predictions to get date range
    predictions = signal_runner.load_predictions()

    # Load market data
    market_data = market_feed.load_historical_data(
        start_date=str(predictions['date'].min().date()),
        end_date=str(predictions['date'].max().date())
    )

    # Get sector map
    sector_map = market_data.groupby('symbol')['sector'].first().to_dict()

    # Get trading calendar
    trading_calendar = market_feed.get_trading_calendar()

    # Validate data freshness
    latest_date = predictions['date'].max()
    is_fresh, message = market_feed.validate_data_freshness(
        str(latest_date.date()),
        tolerance_days=1
    )
    print(f"\nData freshness check: {message}")

    # Run paper trading for sample dates
    print("\n" + "=" * 80)
    print("【Running Paper Trading Simulation - Godfather V9.0 PT.1.1】")
    print("=" * 80)
    print()

    # Get rebalance dates (every 5 days) - run 10 rebalance cycles
    all_dates = sorted(predictions['date'].unique())
    rebalance_dates = [all_dates[i] for i in range(0, min(len(all_dates), 50), 5)][:10]

    print(f"Running paper trading for {len(rebalance_dates)} rebalance dates...")
    print(f"Dates: {[d.date() for d in rebalance_dates]}")
    print()

    daily_results = []

    for signal_date in rebalance_dates:
        result = run_single_day(
            components,
            str(signal_date.date()),
            sector_map
        )
        daily_results.append(result)

    # Generate summary
    print("\n" + "=" * 80)
    print("【Godfather V9.0 PT.1.1a - Execution Summary】")
    print("=" * 80)
    print()

    completed_results = [r for r in daily_results if r['status'] == 'completed']

    if len(completed_results) > 0:
        print(f"✅ Completed {len(completed_results)} trading days")
        print(f"   Skipped {len(daily_results) - len(completed_results)} days")
        print()

        # Aggregate statistics (excluding first rebalance for turnover)
        turnovers = [r['portfolio_summary'].get('expected_turnover', 0)
                    for r in completed_results
                    if r['portfolio_summary'].get('status') != 'No rebalance']

        if len(turnovers) > 1:
            # Ex-first-turnover calculation (PT.1.1a)
            ex_first_turnover = turnovers[1:]  # Exclude first rebalance
            avg_turnover_all = np.mean(turnovers)
            avg_turnover_ex_first = np.mean(ex_first_turnover)

            print(f"Turnover Analysis (PT.1.1a):")
            print(f"  Average Turnover (all): {avg_turnover_all*100:.1f}%")
            print(f"  Average Turnover (ex-first): {avg_turnover_ex_first*100:.1f}%")
            print(f"  Baseline Turnover (P.1.2): 40.1%")
            print(f"  Improvement vs baseline: {(0.401 - avg_turnover_ex_first)*100:.1f}%")
            print()
        elif len(turnovers) > 0:
            avg_turnover = np.mean(turnovers)
            print(f"Average Turnover: {avg_turnover*100:.1f}%")
            print(f"Baseline Turnover (P.1.2): 40.1%")
            print(f"Note: Only one rebalance, ex-first calculation not applicable")
            print()

        # Final accounting
        final_accounting = completed_results[-1]['accounting_summary']
        print(f"Final Portfolio Value: ${final_accounting['total_value']:,.2f}")
        print(f"Total Return: {final_accounting['return_pct']*100:.2f}%")
        print(f"Cash: ${final_accounting['cash']:,.2f}")
        print(f"Holdings: ${final_accounting['holdings_value']:,.2f}")
        print(f"Realized PnL: ${final_accounting['realized_pnl']:,.2f}")
        print(f"Unrealized PnL: ${final_accounting['unrealized_pnl']:,.2f}")
        print()

        # Cash constraint check
        if final_accounting.get('cash_constraint_triggered', False):
            print(f"⚠️  Cash constraint was triggered during simulation")
        else:
            print(f"✅ No cash constraint violations")
        print()

    # Final timing
    elapsed = time.time() - start_time
    print(f"Total runtime: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    print()

    print("=" * 80)
    print("✅ Godfather V9.0 - Phase PT.1.1a Complete!")
    print("=" * 80)


if __name__ == '__main__':
    main()
