"""
PT.4.2 Continuous Tiny Paper Observation - Godfather V9.0
Daily automated trading with tiny capital
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
from paper_trading.broker_recon_adapter import BrokerReconAdapter
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent.parent)))


def load_configs():
    """Load configurations"""
    base_dir = (_REPO_ROOT / 'data/pt4_prep')

    with open(base_dir / 'broker_connection_config.json', 'r') as f:
        broker_config = json.load(f)

    with open(base_dir / 'tiny_capital_config.json', 'r') as f:
        tiny_config = json.load(f)

    return broker_config, tiny_config


def initialize_components(broker_config, tiny_config):
    """Initialize all components"""
    output_dir = 'str(Path(__file__).resolve().parent.parent)/data/paper_trading'

    broker = BrokerConnection(
        config_file='str(Path(__file__).resolve().parent.parent)/data/pt4_prep/broker_connection_config.json'
    )

    gate = PreTradeHardGate(output_dir=output_dir)

    review = ManualReviewCheckpoints(
        output_dir=output_dir,
        broker_env=broker_config.get('environment', 'unknown'),
        tiny_capital_enabled=tiny_config.get('enabled', False)
    )

    hard_stop = HardStopRules()

    executor = LiveTinyModeExecutor(
        broker_connection=broker,
        tiny_capital_config=tiny_config,
        pre_trade_gate=gate,
        manual_review=review,
        hard_stop_rules=hard_stop,
        output_dir=output_dir
    )

    recon_adapter = BrokerReconAdapter(broker)

    return broker, executor, recon_adapter


def run_daily_cycle():
    """Run one daily trading cycle"""
    print("="*80)
    print(f"【Godfather V9.0 - Daily Cycle - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}】")
    print("="*80)
    print()

    # Load configs
    broker_config, tiny_config = load_configs()

    # Initialize
    broker, executor, recon_adapter = initialize_components(broker_config, tiny_config)

    # Connect
    if not broker.connect():
        print("❌ Broker connection failed")
        return False

    print("✅ Connected to broker")
    print()

    # TODO: Get orders from strategy (currently using sample)
    date = datetime.now().strftime('%Y-%m-%d')
    orders = []  # Would come from Alpha Factory + ML.2

    if len(orders) == 0:
        print("ℹ️  No orders today")
        broker.disconnect()
        return True

    # Execute orders
    print(f"Executing {len(orders)} orders...")

    run_report = executor.execute_live_tiny_run(
        date=date,
        orders=orders,
        current_cash=5000.0,
        current_holdings={},
        portfolio_value=5000.0,
        market_data={},
        tradable_symbols=set()
    )

    print(f"Run status: {run_report['final_status']}")

    # Run EOD recon
    print("\nRunning EOD reconciliation...")

    # Load local state
    state_file = (_REPO_ROOT / 'data/paper_trading/state/pt42_complete_state.json')
    if state_file.exists():
        with open(state_file, 'r') as f:
            local_state = json.load(f)

        recon_report = recon_adapter.run_full_recon(
            local_orders=[],
            local_positions=local_state.get('positions', {}),
            local_cash=local_state.get('cash', 0),
            local_fills=local_state.get('fills', [])
        )

        print(f"Recon status: {recon_report['overall_status']}")

    broker.disconnect()
    return True


def main():
    """Main continuous observation entry"""
    print("="*80)
    print("【Godfather V9.0 - Continuous Tiny Paper Observation】")
    print("="*80)
    print()
    print("Mode: Continuous")
    print("Capital: $5,000 tiny cap")
    print("Environment: Paper")
    print("Auto-approve: Enabled")
    print()

    try:
        success = run_daily_cycle()

        if success:
            print("\n✅ Daily cycle completed")
        else:
            print("\n❌ Daily cycle failed")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
