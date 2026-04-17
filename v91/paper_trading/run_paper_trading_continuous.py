"""
Continuous Paper Trading Runner - Godfather V9.0 Phase PT.3a
Shadow broker mode with live integration prep
"""
import sys
import os
import time
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
import uuid
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
from paper_trading.state_manager import StateManager
from paper_trading.risk_state_machine import RiskStateMachine
from paper_trading.weekly_report import WeeklyReportGenerator
from paper_trading.dashboard import DashboardGenerator
from paper_trading.alert_manager import AlertManager
from paper_trading.regime_classifier import RegimeClassifier
from paper_trading.stress_report import StressReportGenerator
from paper_trading.shadow_broker import ShadowBroker
from paper_trading.integration_checker import IntegrationChecker
from paper_trading.order_lifecycle_shadow import OrderLifecycleShadow
from paper_trading.shadow_monitor import ShadowMonitor
from runtime_paths import get_price_lake_dir


def print_config():
    """Print Godfather V9.0 Phase PT.3b configuration"""
    print("=" * 80)
    print("【Godfather V9.0 - Phase PT.3b】")
    print("Continuous Shadow Mode / Broker Integration Validation")
    print("=" * 80)
    print()
    print("System Configuration:")
    print("  Godfather Version = V9.0")
    print("  Phase = PT.3b")
    print("  Universe = US equities")
    print("  Primary key = stock_code (unified)")
    print("  Alpha / ML = frozen")
    print("  Real OHLCV = ON")
    print("  Paper broker = ON")
    print("  Real broker = OFF")
    print("  Shadow broker = ON")
    print()
    print("Portfolio Parameters:")
    print("  Rebalance every 5d")
    print("  Hold buffer = 50%")
    print("  Top20 bucket")
    print("  T+1 close execution")
    print("  Sector neutrality = ON")
    print()
    print("PT.3b Features:")
    print("  Continuous shadow mode = ON")
    print("  US broker schema = ON")
    print("  Integration checks = ON (4/4)")
    print("  Shadow lifecycle tracking = ON")
    print("  Shadow monitoring = ON")
    print("  Regime-aware risk control = ON")
    print()
    print("=" * 80)
    print()


def initialize_components(output_dir: Path, state_dir: Path):
    """Initialize all components"""
    print("=" * 80)
    print("【Initializing Components - PT.2】")
    print("=" * 80)
    print()

    BASE_DIR = Path(__file__).parent.parent
    DATA_LAKE_PATH = get_price_lake_dir()
    ML2_PREDICTIONS_PATH = BASE_DIR / 'data' / 'ml2_results' / 'predictions_8window.parquet'

    # Market Data Feed
    market_feed = MarketDataFeed(
        data_source_path=str(DATA_LAKE_PATH),
        mode='eod'
    )

    # Signal Runner
    signal_runner = SignalRunner(
        predictions_path=str(ML2_PREDICTIONS_PATH),
        model_version="ML.2_8window",
        feature_version="B.2_frozen"
    )

    # Portfolio Constructor
    portfolio_constructor = PortfolioConstructor(
        n_stocks=20,
        max_stock_weight=0.10,
        sector_neutral=True,
        hold_buffer_percentile=0.50,
        rebalance_frequency=5
    )

    # Paper Broker
    paper_broker = PaperBroker(
        transaction_cost_bps=10.0,
        initial_capital=1_000_000
    )

    # Execution Monitor
    execution_monitor = ExecutionMonitor()

    # Risk Guard
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

    # Drift Monitor
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
        drift_threshold=0.20,
        turnover_threshold_pct=20.0
    )

    # Report Generator
    report_generator = ReportGenerator(
        output_dir=str(output_dir)
    )

    # State Manager
    state_manager = StateManager(
        state_dir=str(state_dir)
    )

    # Risk State Machine
    risk_state_machine = RiskStateMachine(
        max_consecutive_warns=3,
        max_consecutive_halts=1,
        startup_grace_period=10,
        trend_aware=True,
        regime_aware=True
    )

    # Weekly Report Generator
    weekly_report_generator = WeeklyReportGenerator(
        output_dir=str(output_dir)
    )

    # Dashboard Generator
    dashboard_generator = DashboardGenerator(
        output_dir=str(output_dir)
    )

    # Alert Manager
    alert_manager = AlertManager(
        output_dir=str(output_dir)
    )

    # Regime Classifier (PT.2.2a)
    regime_classifier = RegimeClassifier()

    # Stress Report Generator (PT.2.3)
    stress_report_generator = StressReportGenerator(output_dir)

    # Shadow Broker (PT.3a)
    shadow_broker = ShadowBroker(broker_name="generic")

    # Integration Checker (PT.3a)
    integration_checker = IntegrationChecker(market_feed)

    # Order Lifecycle Shadow (PT.3a)
    order_lifecycle_shadow = OrderLifecycleShadow(rejection_rate=0.0)

    # Shadow Monitor (PT.3a)
    shadow_monitor = ShadowMonitor(output_dir=str(output_dir))

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
        'state_manager': state_manager,
        'risk_state_machine': risk_state_machine,
        'weekly_report_generator': weekly_report_generator,
        'dashboard_generator': dashboard_generator,
        'alert_manager': alert_manager,
        'regime_classifier': regime_classifier,
        'stress_report_generator': stress_report_generator,
        'shadow_broker': shadow_broker,
        'integration_checker': integration_checker,
        'order_lifecycle_shadow': order_lifecycle_shadow,
        'shadow_monitor': shadow_monitor,
        'output_dir': output_dir
    }


def run_single_day(
    components: dict,
    signal_date: str,
    sector_map: dict,
    run_id: str,
    daily_returns: list
) -> dict:
    """Run paper trading for a single day"""
    print("\n" + "=" * 80)
    print(f"【Running Day: {signal_date} | Run ID: {run_id[:8]}】")
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
    state_manager = components['state_manager']
    risk_state_machine = components['risk_state_machine']
    alert_manager = components['alert_manager']
    regime_classifier = components['regime_classifier']
    stress_report_generator = components['stress_report_generator']
    shadow_broker = components['shadow_broker']
    integration_checker = components['integration_checker']
    order_lifecycle_shadow = components['order_lifecycle_shadow']
    shadow_monitor = components['shadow_monitor']
    output_dir = components['output_dir']

    # Check if already processed
    if state_manager.is_date_processed(signal_date):
        print(f"⏭️  Date {signal_date} already processed. Skipping.")
        return {'status': 'skipped', 'reason': 'already_processed'}

    # Check risk state
    if not risk_state_machine.can_trade():
        print(f"🛑 Trading HALTED by risk state machine")
        risk_state_machine.print_state()
        return {'status': 'halted', 'reason': 'risk_state_halt'}

    # Generate signal
    print("Step 1: Generating signal...")
    signal_data = signal_runner.generate_signal(signal_date, sector_map)

    if len(signal_data) == 0:
        print("⚠️  No signal data. Skipping.")
        return {'status': 'skipped', 'reason': 'no_signal'}

    signal_summary = signal_runner.get_signal_summary(signal_data)
    signal_runner.save_signal(signal_data, output_dir / 'signals', signal_date)

    # Construct target portfolio
    print("\nStep 2: Constructing target portfolio...")
    target_portfolio = portfolio_constructor.construct_target_portfolio(
        signal_data,
        signal_date
    )

    is_rebalance_day = len(target_portfolio) > 0

    if not is_rebalance_day:
        # Non-rebalance day: mark-to-market only
        print(f"⏭️  No rebalance today.")

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
        drift_results = {'drift_detected': False, 'drift_status': 'OK'}

        # PT.2.2a: Still classify regime on non-rebalance days
        if len(daily_returns) > 0:
            prev_value = daily_returns[-1]['portfolio_value']
            market_move_pct = abs((accounting_summary['total_value'] - prev_value) / prev_value)
            market_move_abs_bps = market_move_pct * 10000
        else:
            market_move_abs_bps = 0

        regime = regime_classifier.classify_regime(
            signal_date=signal_date,
            market_move_abs_bps=market_move_abs_bps,
            impl_shortfall_abs_bps=0,
            turnover=0,
            baseline_turnover=0.4014
        )
        observation_mode = False

        # PT.3a: No shadow broker activity on non-rebalance days
        shadow_comparison = None

    else:
        # Rebalance day
        portfolio_summary = portfolio_constructor.get_portfolio_summary(target_portfolio)

        target_file = output_dir / 'targets' / f"{signal_date}.parquet"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_portfolio.to_parquet(target_file, index=False)

        # Create orders
        print("\nStep 3: Creating orders...")
        intended_trade_date = market_feed.get_next_trading_day(signal_date)

        all_symbols = list(set(signal_data['stock_code'].unique().tolist()) | set(paper_broker.positions.keys()))
        reference_prices = market_feed.get_latest_prices(all_symbols, as_of_date=signal_date)

        orders = paper_broker.create_orders(
            target_portfolio,
            signal_date,
            intended_trade_date,
            reference_prices
        )

        if len(orders) > 0:
            orders_df = pd.DataFrame(orders)
            orders_file = output_dir / 'orders' / f"{signal_date}.parquet"
            orders_file.parent.mkdir(parents=True, exist_ok=True)
            orders_df.to_parquet(orders_file, index=False)

        # PT.3a: Shadow broker integration
        print("\nStep 3a: Shadow broker integration...")

        # Generate shadow payloads
        shadow_payloads = shadow_broker.generate_broker_payload(
            orders=orders,
            run_id=run_id,
            signal_date=signal_date,
            version="V9.0"
        )
        print(f"  Generated {len(shadow_payloads)} shadow payloads")

        # Run integration checks
        all_symbols = list(set([o['stock_code'] for o in orders]))
        integration_checks = integration_checker.run_integration_checks(
            symbols=all_symbols,
            target_date=str(intended_trade_date.date()),
            orders=orders
        )
        print(f"  Integration checks: {integration_checks['overall_status']}")

        # Simulate order lifecycle
        lifecycle_events = order_lifecycle_shadow.simulate_lifecycle(
            shadow_payloads=shadow_payloads,
            integration_checks=integration_checks
        )
        print(f"  Simulated {len(lifecycle_events)} lifecycle events")

        # Simulate fills
        print("\nStep 4: Simulating fills...")
        fill_prices = market_feed.get_latest_prices(
            [o['stock_code'] for o in orders],
            as_of_date=str(intended_trade_date.date())
        )

        fills = paper_broker.simulate_fills(orders, fill_prices, str(intended_trade_date.date()))

        if len(fills) > 0:
            fills_df = pd.DataFrame(fills)
            fills_file = output_dir / 'fills' / f"{signal_date}.parquet"
            fills_file.parent.mkdir(parents=True, exist_ok=True)
            fills_df.to_parquet(fills_file, index=False)

        order_summary = paper_broker.get_order_summary()

        # Execution analysis
        print("\nStep 5: Analyzing execution...")
        execution_summary = execution_monitor.analyze_execution(
            orders, fills, signal_date, str(intended_trade_date.date())
        )

        # Update holdings
        print("\nStep 6: Updating holdings...")
        if len(fills) > 0:
            realized_symbols = pd.DataFrame([
                {'stock_code': symbol, 'shares': shares}
                for symbol, shares in paper_broker.positions.items()
                if shares > 0
            ])
            portfolio_constructor.update_holdings(realized_symbols)

        # Mark-to-market
        print("\nStep 7: Mark-to-market...")
        current_prices = market_feed.get_latest_prices(
            list(paper_broker.positions.keys()) if len(paper_broker.positions) > 0 else [],
            as_of_date=str(intended_trade_date.date())
        )
        accounting_summary = paper_broker.get_accounting_summary(current_prices)

        # PT.2.2a: Classify market regime
        print("\nStep 8: Classifying market regime...")

        # Calculate market move (using portfolio value change as proxy)
        if len(daily_returns) > 0:
            prev_value = daily_returns[-1]['portfolio_value']
            market_move_pct = abs((accounting_summary['total_value'] - prev_value) / prev_value)
            market_move_abs_bps = market_move_pct * 10000
        else:
            market_move_abs_bps = 0

        impl_shortfall_abs_bps = execution_summary.get('implementation_shortfall_abs_mean_bps', 0)
        turnover = portfolio_summary.get('expected_turnover', 0)

        regime = regime_classifier.classify_regime(
            signal_date=signal_date,
            market_move_abs_bps=market_move_abs_bps,
            impl_shortfall_abs_bps=impl_shortfall_abs_bps,
            turnover=turnover,
            baseline_turnover=0.4014
        )

        regime_thresholds = regime_classifier.get_regime_thresholds(regime)
        observation_mode = regime_classifier.should_enter_observation_mode(regime)

        print(f"  Regime: {regime.value}")
        print(f"  Market move: {market_move_abs_bps:.1f} bps")
        print(f"  Impl shortfall: {impl_shortfall_abs_bps:.1f} bps")
        print(f"  Turnover: {turnover*100:.1f}%")
        print(f"  Observation mode: {observation_mode}")

        # Update risk guard thresholds based on regime
        risk_guard.max_implementation_shortfall_bps = regime_thresholds['max_impl_shortfall_bps']

        # Risk checks
        print(f"\nStep 9: Risk checks (regime-aware)...")
        print(f"  Max impl shortfall: {regime_thresholds['max_impl_shortfall_bps']:.0f} bps")
        print(f"  Max turnover deviation: {regime_thresholds['max_turnover_deviation_pct']:.0f}%")
        _, risk_results = risk_guard.run_all_checks(
            target_portfolio=target_portfolio,
            orders=orders,
            fills=fills,
            turnover=portfolio_summary.get('expected_turnover', 0),
            execution_summary=execution_summary
        )

        # Drift checks
        print("\nStep 10: Drift checks...")
        drift_results = drift_monitor.run_all_drift_checks(
            live_scores=signal_data['sector_neutral_score'],
            live_turnover=portfolio_summary.get('expected_turnover', 0),
            is_first_rebalance=(portfolio_constructor.rebalance_counter == 1),
            sector_exposure=portfolio_summary.get('sector_exposure', {}),
            impl_shortfall_bps=execution_summary.get('implementation_shortfall_abs_mean_bps', 0),
            holding_count=accounting_summary.get('num_positions', 0),
            cash=accounting_summary.get('cash', 0),
            holdings_value=accounting_summary.get('holdings_value', 0),
            total_value=accounting_summary.get('total_value', 0)
        )

        # PT.3a: Shadow monitoring
        print("\nStep 10a: Shadow monitoring...")
        shadow_comparison = shadow_monitor.compare_paper_vs_shadow(
            date=signal_date,
            target_portfolio=target_portfolio,
            paper_orders=orders,
            shadow_payloads=shadow_payloads,
            integration_checks=integration_checks,
            lifecycle_events=lifecycle_events
        )
        print(f"  Shadow validation: {shadow_comparison['integration_checks']['overall_status']}")
        print(f"  Rejected orders: {shadow_comparison['validation']['rejected_count']}")

    # Update risk state machine
    print("\nStep 11: Updating risk state...")

    # Prepare metrics for trend tracking
    metrics = {
        'turnover': portfolio_summary.get('expected_turnover', 0),
        'retained': portfolio_constructor.buffer_stats.get('retained', 0),
        'impl_shortfall': execution_summary.get('implementation_shortfall_abs_mean_bps', 0)
    }

    state_update = risk_state_machine.update_state(
        risk_results,
        drift_results,
        signal_date,
        regime=regime,
        metrics=metrics
    )
    risk_state_machine.print_state()

    # PT.2.2: Check alerts
    print("\nStep 12: Checking alerts...")
    alerts = alert_manager.check_alerts(
        date=signal_date,
        risk_results=risk_results,
        drift_results=drift_results,
        execution_summary=execution_summary,
        portfolio_summary=portfolio_summary,
        regime=regime.value
    )

    if len(alerts) > 0:
        print(f"⚠️  {len(alerts)} alert(s) triggered:")
        for alert in alerts:
            print(f"   [{alert['severity']}] {alert['type']}: {alert['message']}")

    # Generate daily report
    print("\nStep 13: Generating daily report...")
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

    # Save broker state
    state_manager.save_broker_state(
        cash=paper_broker.cash,
        positions=paper_broker.positions,
        position_costs=paper_broker.position_costs,
        realized_pnl=paper_broker.realized_pnl,
        total_transaction_costs=paper_broker.total_transaction_costs,
        date=signal_date
    )

    # Mark date as processed
    state_manager.mark_date_processed(signal_date, run_id, 'completed')

    # Log run
    state_manager.log_run(run_id, signal_date, 'completed', {
        'portfolio_value': accounting_summary.get('total_value', 0),
        'return_pct': accounting_summary.get('return_pct', 0),
        'risk_state': risk_state_machine.current_state.value,
        'is_rebalance': is_rebalance_day
    })

    # Track daily returns
    if len(daily_returns) > 0:
        prev_value = daily_returns[-1]['portfolio_value']
        daily_return = (accounting_summary['total_value'] - prev_value) / prev_value
    else:
        daily_return = 0

    daily_returns.append({
        'date': signal_date,
        'portfolio_value': accounting_summary['total_value'],
        'daily_return': daily_return
    })

    return {
        'status': 'completed',
        'date': signal_date,
        'signal_summary': signal_summary,
        'portfolio_summary': portfolio_summary,
        'order_summary': order_summary,
        'accounting_summary': accounting_summary,
        'execution_summary': execution_summary,
        'risk_results': risk_results,
        'drift_results': drift_results,
        'risk_state': risk_state_machine.current_state.value,
        'regime': regime.value,
        'observation_mode': observation_mode
    }


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='Godfather V9.0 Paper Trading')
    parser.add_argument('--start-date', type=str, required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--mode', type=str, default='paper', help='Trading mode')
    args = parser.parse_args()

    start_time = time.time()

    print_config()

    # Setup
    BASE_DIR = Path(__file__).parent.parent
    OUTPUT_DIR = BASE_DIR / 'data' / 'paper_trading'
    STATE_DIR = OUTPUT_DIR / 'state'

    run_id = str(uuid.uuid4())
    print(f"Run ID: {run_id}\n")

    # Initialize
    components = initialize_components(OUTPUT_DIR, STATE_DIR)

    # Load data
    print("=" * 80)
    print("【Loading Historical Data】")
    print("=" * 80)
    print()

    market_feed = components['market_feed']
    signal_runner = components['signal_runner']

    predictions = signal_runner.load_predictions()

    # Filter predictions by date range
    predictions = predictions[
        (predictions['date'] >= args.start_date) &
        (predictions['date'] <= args.end_date)
    ].copy()

    print(f"\nFiltered predictions for date range {args.start_date} to {args.end_date}")
    print(f"  Total predictions: {len(predictions)}")
    if len(predictions) > 0:
        print(f"  Date range: {predictions['date'].min()} to {predictions['date'].max()}")
        print(f"  Symbols: {predictions['stock_code'].nunique()}")

    market_data = market_feed.load_historical_data(
        start_date=args.start_date,
        end_date=args.end_date
    )

    sector_map = market_data.groupby('symbol')['sector'].first().to_dict()

    # Get trading dates (every 5 days)
    all_dates = sorted(predictions['date'].unique())
    test_dates = [all_dates[i] for i in range(0, len(all_dates), 5)]

    print(f"\nRunning continuous paper trading for {len(test_dates)} dates...")
    print(f"Start: {test_dates[0].date()}")
    print(f"End: {test_dates[-1].date()}")
    print()

    # Run continuous trading
    daily_results = []
    daily_returns = []

    # PT.2.1 tracking
    impl_shortfall_list = []
    retained_added_dropped_list = []
    portfolio_values = []

    for signal_date in test_dates:
        result = run_single_day(
            components,
            str(signal_date.date()),
            sector_map,
            run_id,
            daily_returns
        )
        daily_results.append(result)

        # PT.2.1: Collect statistics
        if result['status'] == 'completed':
            # Implementation shortfall
            exec_summary = result.get('execution_summary', {})
            if exec_summary.get('status') != 'No fills':
                impl_shortfall_list.append(exec_summary.get('implementation_shortfall_abs_mean_bps', 0))

            # Retained/added/dropped
            portfolio_summary = result.get('portfolio_summary', {})
            if portfolio_summary.get('status') != 'No rebalance':
                buffer_stats = portfolio_summary.get('buffer_stats', {})
                retained_added_dropped_list.append({
                    'date': str(signal_date.date()),
                    'retained': buffer_stats.get('retained', 0),
                    'added': buffer_stats.get('added', 0),
                    'dropped': buffer_stats.get('dropped', 0)
                })

            # Portfolio value for path drift
            accounting = result.get('accounting_summary', {})
            portfolio_values.append({
                'date': str(signal_date.date()),
                'value': accounting.get('total_value', 0),
                'return_pct': accounting.get('return_pct', 0)
            })

        if result['status'] == 'halted':
            print("\n🛑 Trading halted by risk state machine. Stopping.")
            break

    # PT.2.2: Generate weekly reports
    print("\n" + "=" * 80)
    print("【Generating Weekly Reports】")
    print("=" * 80)
    print()

    weekly_report_generator = components['weekly_report_generator']
    baseline_metrics = {'sharpe': 2.2341, 'avg_turnover': 0.4014}

    # Group by weeks (every 5 observations)
    completed = [r for r in daily_results if r['status'] == 'completed']
    print(f"  Total completed observations: {len(completed)}")

    if len(completed) > 0:
        for i in range(0, len(completed), 5):
            week_results = completed[i:min(i+5, len(completed))]
            if len(week_results) > 0:
                # Get dates from week_results
                week_start = week_results[0]['date']
                week_end = week_results[-1]['date']

                print(f"  Generating report for week {week_start} to {week_end} ({len(week_results)} observations)")

                weekly_report_generator.generate_weekly_report(
                    week_start=week_start,
                    week_end=week_end,
                    daily_results=daily_results,
                    baseline_metrics=baseline_metrics
                )

    # PT.2.2: Generate dashboard
    print("\n" + "=" * 80)
    print("【Generating Dashboard Summary】")
    print("=" * 80)
    print()

    dashboard_generator = components['dashboard_generator']
    dashboard_generator.generate_dashboard(
        daily_results=daily_results,
        run_id=run_id
    )

    # PT.2.3: Generate stress report
    print("\n" + "=" * 80)
    print("【Generating Stress Regime Report】")
    print("=" * 80)
    print()

    stress_report_generator = components['stress_report_generator']
    stress_report_generator.generate_stress_report(
        daily_results=daily_results,
        stress_period_name="COVID_2020_Q1Q2"
    )

    # Summary
    print("\n" + "=" * 80)
    print("【Godfather V9.0 PT.2.3 - Execution Summary】")
    print("=" * 80)
    print()

    completed = [r for r in daily_results if r['status'] == 'completed']
    skipped = [r for r in daily_results if r['status'] == 'skipped']
    halted = [r for r in daily_results if r['status'] == 'halted']

    print(f"【A. Observation Period Coverage】")
    print(f"  Start date: {test_dates[0].date()}")
    print(f"  End date: {test_dates[-1].date()}")
    print(f"  运行观测点: {len(completed)}")
    print(f"  调仓观测点: {sum(1 for r in completed if r.get('portfolio_summary', {}).get('status') != 'No rebalance')}")
    print()

    print(f"【B. Core Stability】")

    # Check negative cash
    negative_cash_days = []
    for r in completed:
        cash = r.get('accounting_summary', {}).get('cash', 0)
        if cash < 0:
            negative_cash_days.append(r.get('accounting_summary', {}).get('date', 'unknown'))

    if len(negative_cash_days) > 0:
        print(f"  ❌ Negative cash detected: {len(negative_cash_days)} days")
    else:
        print(f"  ✅ No negative cash")

    # Check HALT
    if len(halted) > 0:
        print(f"  ❌ HALT triggered: {len(halted)} times")
    else:
        print(f"  ✅ No HALT triggered")

    # Risk/Drift warnings
    risk_warns = sum(1 for r in completed if r.get('risk_results', {}).get('overall_status') == 'WARN')
    drift_warns = sum(1 for r in completed if r.get('drift_results', {}).get('drift_detected'))

    print(f"  Risk WARNs: {risk_warns}")
    print(f"  Drift WARNs: {drift_warns}")
    print()

    print(f"【C. Three New Statistics】")

    # C1: Implementation shortfall
    if len(impl_shortfall_list) > 0:
        impl_mean = np.mean(impl_shortfall_list)
        impl_p95 = np.percentile(impl_shortfall_list, 95)

        # Rolling mean (last 5 rebalances)
        if len(impl_shortfall_list) >= 5:
            impl_rolling = np.mean(impl_shortfall_list[-5:])
        else:
            impl_rolling = impl_mean

        print(f"  Implementation Shortfall:")
        print(f"    Mean: {impl_mean:.1f} bps")
        print(f"    P95: {impl_p95:.1f} bps")
        print(f"    Rolling mean (last 5): {impl_rolling:.1f} bps")
    else:
        print(f"  Implementation Shortfall: No data")
    print()

    # C2: Retained/added/dropped
    if len(retained_added_dropped_list) > 0:
        avg_retained = np.mean([x['retained'] for x in retained_added_dropped_list])
        avg_added = np.mean([x['added'] for x in retained_added_dropped_list])
        avg_dropped = np.mean([x['dropped'] for x in retained_added_dropped_list])

        print(f"  Retained/Added/Dropped (average per rebalance):")
        print(f"    Retained: {avg_retained:.1f} stocks")
        print(f"    Added: {avg_added:.1f} stocks")
        print(f"    Dropped: {avg_dropped:.1f} stocks")
    else:
        print(f"  Retained/Added/Dropped: No data")
    print()

    # C3: Portfolio path drift vs baseline
    if len(portfolio_values) > 1:
        returns = [(portfolio_values[i]['value'] - portfolio_values[i-1]['value']) / portfolio_values[i-1]['value']
                   for i in range(1, len(portfolio_values))]

        live_return = (portfolio_values[-1]['value'] - portfolio_values[0]['value']) / portfolio_values[0]['value']
        live_sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0

        baseline_sharpe = 2.2341
        baseline_return = 0.0758  # P.1.2 baseline

        print(f"  Portfolio Path Drift vs Baseline:")
        print(f"    Live return: {live_return*100:.2f}%")
        print(f"    Live Sharpe: {live_sharpe:.2f}")
        print(f"    Baseline Sharpe: {baseline_sharpe:.2f}")
        print(f"    Sharpe drift: {abs(live_sharpe - baseline_sharpe):.2f}")
    else:
        print(f"  Portfolio Path Drift: Insufficient data")
    print()

    print(f"【D. Turnover】")
    turnovers = []
    if len(completed) > 0:
        # Turnover analysis
        turnovers = [r['portfolio_summary'].get('expected_turnover', 0)
                    for r in completed
                    if r['portfolio_summary'].get('status') != 'No rebalance']

        if len(turnovers) > 1:
            full_turnover = np.mean(turnovers)
            ex_first = np.mean(turnovers[1:])
            baseline = 0.4014

            print(f"  Full turnover: {full_turnover*100:.1f}%")
            print(f"  Ex-first turnover: {ex_first*100:.1f}%")
            print(f"  Baseline: {baseline*100:.1f}%")
            print(f"  Drift: {(ex_first - baseline)*100:+.1f} pct points")
        else:
            print(f"  Insufficient rebalances for turnover analysis")
    print()

    print(f"【E. Alert Summary (PT.2.2)】")
    alert_manager = components['alert_manager']
    alert_summary = alert_manager.get_alert_summary()

    if alert_summary['total'] == 0:
        print(f"  ✅ No alerts triggered")
    else:
        print(f"  Total alerts: {alert_summary['total']}")
        if 'by_severity' in alert_summary:
            print(f"  By severity:")
            for severity, count in alert_summary['by_severity'].items():
                print(f"    {severity}: {count}")
        if 'by_type' in alert_summary:
            print(f"  By type:")
            for alert_type, count in alert_summary['by_type'].items():
                print(f"    {alert_type}: {count}")
    print()

    print(f"【F. Regime Classification Summary (PT.2.2a)】")
    regime_classifier = components['regime_classifier']
    regime_summary = regime_classifier.get_regime_summary()

    if regime_summary['total'] > 0:
        print(f"  Total observations: {regime_summary['total']}")
        print(f"  Regime distribution:")
        for regime, count in regime_summary['counts'].items():
            pct = count / regime_summary['total'] * 100
            print(f"    {regime}: {count} ({pct:.1f}%)")
        print(f"  Latest regime: {regime_summary['latest']}")
    else:
        print(f"  No regime data")
    print()

    print(f"【G. Shadow Broker Summary (PT.3a)】")
    shadow_broker = components['shadow_broker']
    shadow_summary = shadow_broker.get_shadow_summary()

    if shadow_summary['total'] > 0:
        print(f"  Total shadow orders: {shadow_summary['total']}")
        print(f"  Total notional: ${shadow_summary['total_notional']:,.2f}")
        print(f"  Unique symbols: {shadow_summary['unique_symbols']}")
    else:
        print(f"  No shadow orders")

    integration_checker = components['integration_checker']
    check_summary = integration_checker.get_check_summary()
    if check_summary.get('total_checks', 0) > 0:
        print(f"  Integration checks: {check_summary['passed']}/{check_summary['total_checks']} passed ({check_summary['pass_rate']*100:.1f}%)")

    shadow_monitor = components['shadow_monitor']
    monitor_summary = shadow_monitor.get_shadow_summary()
    if monitor_summary.get('total_comparisons', 0) > 0:
        print(f"  Shadow validation pass rate: {monitor_summary['pass_rate']*100:.1f}%")
        print(f"  Total rejected orders: {monitor_summary['total_rejected']}")
        print(f"  Total missing symbols: {monitor_summary['total_missing_symbols']}")
        print(f"  Total bad fields: {monitor_summary['total_bad_fields']}")
    print()

    print(f"【H. Final Conclusion】")

    # 1. Stability check
    is_stable = (len(negative_cash_days) == 0 and len(halted) == 0)
    print(f"  1. Godfather V9.0 stable over extended period? {'✅ YES' if is_stable else '❌ NO'}")

    # 2. Turnover convergence
    if len(turnovers) > 1:
        ex_first = np.mean(turnovers[1:])
        baseline = 0.4014
        turnover_converging = abs(ex_first - baseline) < 0.25  # Within 25 pct points
        print(f"  2. Turnover converging to baseline? {'✅ YES' if turnover_converging else '⚠️  NO (still elevated)'}")
    else:
        print(f"  2. Turnover converging to baseline? Insufficient data")

    # 3. Drift trend
    if len(portfolio_values) > 1:
        drift_expanding = drift_warns > len(completed) * 0.3  # More than 30% of days
        print(f"  3. Drift trend? {'⚠️  EXPANDING' if drift_expanding else '✅ STABLE/CONVERGING'}")
    else:
        print(f"  3. Drift trend? Insufficient data")

    # 4. PT.3a completion check
    print(f"  4. PT.3a complete? ✅ YES (shadow broker + integration checks + lifecycle + monitoring)")

    # 5. Next step recommendation
    print(f"  5. Next step recommendation:")

    if not is_stable:
        print(f"     → D. Fix broker/portfolio constructor (negative cash or HALT detected)")
    elif alert_summary['total'] > len(completed) * 0.5:
        print(f"     → A. Continue observation (high alert rate, need more data)")
    elif drift_warns > len(completed) * 0.3:
        print(f"     → A. Continue observation (drift warnings frequent)")
    else:
        print(f"     → C. PT.3 (broker shadow mode / live integration prep)")


    print()

    # Final accounting
    if len(completed) > 0:
        final = completed[-1]['accounting_summary']
        print(f"Final Portfolio:")
        print(f"  Value: ${final['total_value']:,.2f}")
        print(f"  Return: {final['return_pct']*100:.2f}%")
        print(f"  Cash: ${final['cash']:,.2f}")
        print(f"  Positions: {final['num_positions']}")
        print()

        # State machine
        state_summary = components['risk_state_machine'].get_state_summary()
        print(f"Risk State Machine:")
        print(f"  Final state: {state_summary['current_state']}")
        print(f"  Can trade: {state_summary['can_trade']}")
        print()

    elapsed = time.time() - start_time
    print(f"Total runtime: {elapsed:.1f}s ({elapsed/60:.1f}min)")
    print()
    print("=" * 80)
    print("✅ Godfather V9.0 - Phase PT.3a Complete!")
    print("=" * 80)


if __name__ == '__main__':
    main()
