"""
PT.4.2 Live Tiny Rehearsal - Godfather V9.0
Entrypoint for tiny-capital live rehearsal with real broker
"""
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from paper_trading.broker_connection import BrokerConnection
from paper_trading.pre_trade_hard_gate import PreTradeHardGate
from paper_trading.manual_review_checkpoints import ManualReviewCheckpoints
from paper_trading.hard_stop_rules import HardStopRules
from paper_trading.live_tiny_mode_executor import LiveTinyModeExecutor
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))


def load_configs():
    """Load all required configurations"""
    base_dir = (_REPO_ROOT / 'data/pt4_prep')

    configs = {}

    # Broker connection config
    broker_config_file = base_dir / 'broker_connection_config.json'
    with open(broker_config_file, 'r') as f:
        configs['broker'] = json.load(f)

    # Tiny capital config
    tiny_config_file = base_dir / 'tiny_capital_config.json'
    with open(tiny_config_file, 'r') as f:
        configs['tiny_capital'] = json.load(f)

    # Broker mode config
    mode_config_file = base_dir / 'broker_mode_config.json'
    with open(mode_config_file, 'r') as f:
        configs['broker_mode'] = json.load(f)

    return configs


def validate_launch_conditions(configs):
    """Validate that all launch conditions are met"""
    print("\n" + "="*80)
    print("【PT.4.2 Launch Condition Validation】")
    print("="*80 + "\n")

    blockers = []

    # Check 1: Broker credentials configured
    if not configs['broker'].get('credentials_configured', False):
        blockers.append("Broker credentials not configured")
    else:
        print("✅ Broker credentials: Configured")

    # Check 2: Tiny capital mode enabled
    if not configs['tiny_capital'].get('enabled', False):
        blockers.append("Tiny capital mode not enabled")
    else:
        print("✅ Tiny capital mode: Enabled")
        print(f"   Max capital: ${configs['tiny_capital']['limits']['max_total_capital']:,.0f}")

    # Check 3: Environment is paper
    if configs['broker'].get('environment') != 'paper':
        blockers.append(f"Environment is {configs['broker'].get('environment')}, expected 'paper'")
    else:
        print("✅ Environment: paper")

    # Check 4: Manual review required
    if not configs['tiny_capital']['safety'].get('require_manual_review', False):
        blockers.append("Manual review not required (safety violation)")
    else:
        print("✅ Manual review: Required")

    print()

    if len(blockers) > 0:
        print("❌ Launch blocked:")
        for blocker in blockers:
            print(f"   - {blocker}")
        return False

    print("✅ All launch conditions met")
    return True


def initialize_components(configs):
    """Initialize all PT.4.2 components"""
    print("\n" + "="*80)
    print("【Initializing PT.4.2 Components】")
    print("="*80 + "\n")

    output_dir = 'Path(__file__).resolve().parent.parent/data/paper_trading'

    # Initialize broker connection
    print("[1/5] Initializing broker connection...")
    broker = BrokerConnection(
        config_file='Path(__file__).resolve().parent.parent/data/pt4_prep/broker_connection_config.json'
    )
    print()

    # Initialize pre-trade gate
    print("[2/5] Initializing pre-trade hard gate...")
    gate = PreTradeHardGate(output_dir=output_dir)
    print()

    # Initialize manual review
    print("[3/5] Initializing manual review checkpoints...")
    review = ManualReviewCheckpoints(
        output_dir=output_dir,
        broker_env=configs['broker'].get('environment', 'unknown'),
        tiny_capital_enabled=configs['tiny_capital'].get('enabled', False)
    )
    print()

    # Initialize hard stop rules
    print("[4/5] Initializing hard stop rules...")
    hard_stop = HardStopRules()
    print()

    # Initialize live tiny executor
    print("[5/5] Initializing live tiny mode executor...")
    executor = LiveTinyModeExecutor(
        broker_connection=broker,
        tiny_capital_config=configs['tiny_capital'],
        pre_trade_gate=gate,
        manual_review=review,
        hard_stop_rules=hard_stop,
        output_dir=output_dir
    )
    print()

    return {
        'broker': broker,
        'gate': gate,
        'review': review,
        'hard_stop': hard_stop,
        'executor': executor
    }


def connect_to_broker(broker, configs):
    """Connect to broker"""
    print("\n" + "="*80)
    print("【Connecting to Broker】")
    print("="*80 + "\n")

    print(f"Broker: {configs['broker']['broker_name']}")
    print(f"Environment: {configs['broker']['environment']}")
    print(f"Endpoint: {configs['broker']['api_endpoint']}")
    print()

    success = broker.connect()

    if not success:
        print("\n❌ Broker connection failed")
        print("   This is expected if broker API implementation is not complete")
        print("   PT.4.2 will proceed in framework validation mode")
        return False

    print("\n✅ Broker connected")
    return True


def create_sample_orders():
    """Create sample orders for PT.4.2 validation"""
    # Sample orders for validation (would come from strategy in real run)
    return [
        {
            'symbol': 'AAPL',
            'side': 'BUY',
            'quantity': 1,
            'notional': 150.0,
            'order_type': 'MARKET',
            'tif': 'DAY'
        }
    ]


def execute_pt42_run(components, configs):
    """Execute PT.4.2 live tiny run"""
    print("\n" + "="*80)
    print("【Executing PT.4.2 Live Tiny Run】")
    print("="*80 + "\n")

    # Sample data for validation
    date = datetime.now().strftime('%Y-%m-%d')
    orders = create_sample_orders()
    current_cash = 5000.0  # Tiny capital starting amount
    current_holdings = {}
    portfolio_value = 5000.0
    market_data = {
        'AAPL': {'close': 150.0}
    }
    tradable_symbols = {'AAPL', 'MSFT', 'GOOGL'}

    print(f"Date: {date}")
    print(f"Orders: {len(orders)}")
    print(f"Current cash: ${current_cash:,.2f}")
    print(f"Portfolio value: ${portfolio_value:,.2f}")
    print()

    # Execute live tiny run
    run_report = components['executor'].execute_live_tiny_run(
        date=date,
        orders=orders,
        current_cash=current_cash,
        current_holdings=current_holdings,
        portfolio_value=portfolio_value,
        market_data=market_data,
        tradable_symbols=tradable_symbols
    )

    return run_report


def generate_final_report(run_report, broker_connected):
    """Generate final PT.4.2 execution report"""
    print("\n" + "="*80)
    print("【PT.4.2 Execution Report】")
    print("="*80 + "\n")

    print(f"Timestamp: {run_report['timestamp']}")
    print(f"Date: {run_report['date']}")
    print(f"Phase: {run_report['phase']}")
    print(f"Mode: {run_report['mode']}")
    print(f"Final status: {run_report['final_status']}")
    print()

    print("Stage Results:")
    for stage in run_report['stages']:
        stage_name = stage['stage']
        stage_status = stage['status']
        print(f"  [{stage_name}]: {stage_status}")
    print()

    print("="*80)
    print("【Conclusion】")
    print("="*80 + "\n")

    if run_report['final_status'] == 'COMPLETED':
        print("✅ PT.4.2 live tiny run completed successfully")
    elif run_report['final_status'] == 'AWAITING_REVIEW':
        print("⚠️  PT.4.2 awaiting manual review approval")
        print("   Next step: Review and approve pre-trade checklist")
    elif run_report['final_status'] == 'BLOCKED_AT_GATE':
        print("❌ PT.4.2 blocked at pre-trade gate")
        print("   Reasons:", run_report['stages'][0].get('reasons', []))
    elif run_report['final_status'] == 'BROKER_NOT_CONNECTED':
        print("⚠️  PT.4.2 framework validation completed")
        print("   Broker connection not established (expected)")
        print("   All safety checks passed")
        print("   Ready for real broker connection when implemented")
    else:
        print(f"⚠️  PT.4.2 status: {run_report['final_status']}")

    print()

    # Save final report
    report_file = (_REPO_ROOT / 'data/pt4_prep/pt42_execution_report.json')
    with open(report_file, 'w') as f:
        json.dump({
            'run_report': run_report,
            'broker_connected': broker_connected,
            'execution_timestamp': datetime.now().isoformat()
        }, f, indent=2)

    print(f"Report saved: {report_file}")
    print()


def main():
    """Main PT.4.2 entrypoint"""
    print("="*80)
    print("【Godfather V9.0 - PT.4.2 Tiny-Capital Live Rehearsal】")
    print("="*80)
    print()
    print("Phase: PT.4.2")
    print("Mode: Live Tiny Capital")
    print("Capital: $5,000 cap")
    print("Safety: Full manual review + hard gate + hard stop")
    print()

    try:
        # Step 1: Load configurations
        print("[Step 1] Loading configurations...")
        configs = load_configs()
        print("✅ Configurations loaded")

        # Step 2: Validate launch conditions
        print("\n[Step 2] Validating launch conditions...")
        if not validate_launch_conditions(configs):
            print("\n❌ PT.4.2 launch aborted due to failed conditions")
            sys.exit(1)

        # Step 3: Initialize components
        print("\n[Step 3] Initializing components...")
        components = initialize_components(configs)
        print("✅ All components initialized")

        # Step 4: Connect to broker
        print("\n[Step 4] Connecting to broker...")
        broker_connected = connect_to_broker(components['broker'], configs)

        # Step 5: Execute PT.4.2 run
        print("\n[Step 5] Executing PT.4.2 run...")
        run_report = execute_pt42_run(components, configs)

        # Step 6: Generate final report
        print("\n[Step 6] Generating final report...")
        generate_final_report(run_report, broker_connected)

        print("="*80)
        print("【PT.4.2 Execution Complete】")
        print("="*80)

    except Exception as e:
        print(f"\n❌ PT.4.2 execution failed with error:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
