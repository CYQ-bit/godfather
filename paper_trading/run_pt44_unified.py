"""
PT.4.4 Unified Continuous Trading Entry - Godfather V9.0
Unified entry combining PT.4.2 trading logic + PT.4.3 safeguards
"""
import json
import sys
import os
import time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

from paper_trading.broker_connection import BrokerConnection
from paper_trading.broker_recon_adapter import BrokerReconAdapter
from paper_trading.ui_console import UIConsole
from paper_trading.telegram_reporter import TelegramReporter
from paper_trading.pre_trade_hard_gate import PreTradeHardGate
from paper_trading.manual_review_checkpoints import ManualReviewCheckpoints
from paper_trading.hard_stop_rules import HardStopRules
from paper_trading.signal_runner import SignalRunner
from paper_trading.portfolio_constructor import PortfolioConstructor
from paper_trading.order_sizing import build_delta_orders, load_tiny_capital_config
from paper_trading.position_sizing_v10 import apply_v10_adjustments
from paper_trading.execution_cost_model import ExecutionCostModel
from alpha_factory.regime_engine import load_regime_state
from alpha_factory.confidence_engine import ConfidenceEngine
from paper_trading.broker_local_sync import (
    load_combined_local_state,
    sync_local_state_from_broker,
    run_broker_local_recon,
    critical_recon_ok,
)
from runtime_paths import get_price_lake_dir, get_universe_path
import pandas as pd
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))

REPO_ROOT = Path(__file__).parent.parent
STATE_FILE = REPO_ROOT / 'data/paper_trading/state/pt42_complete_state.json'
UNIVERSE_PATH = get_universe_path()
PRICE_DIR = get_price_lake_dir()


def get_ny_time():
    """Get current time in America/New_York"""
    return datetime.now(ZoneInfo('America/New_York'))


def is_market_open():
    """Check if market is open"""
    ny_time = get_ny_time()

    if ny_time.weekday() >= 5:
        return False, "Weekend"

    from datetime import time
    market_open = time(9, 30)
    market_close = time(16, 0)
    current_time = ny_time.time()

    if current_time < market_open:
        return False, "Before market open"
    elif current_time >= market_close:
        return False, "After market close"

    return True, "Market open"


def check_idempotency(trading_date):
    """Check if already ran today"""
    run_log_file = (_REPO_ROOT / 'data/paper_trading/state/daily_run_log.json')

    if not run_log_file.exists():
        return True, None

    with open(run_log_file, 'r') as f:
        run_log = json.load(f)

    if trading_date in run_log:
        return False, run_log[trading_date]

    return True, None


def record_run(trading_date, run_id, status):
    """Record today's run"""
    run_log_file = (_REPO_ROOT / 'data/paper_trading/state/daily_run_log.json')
    run_log_file.parent.mkdir(parents=True, exist_ok=True)

    run_log = {}
    if run_log_file.exists():
        with open(run_log_file, 'r') as f:
            run_log = json.load(f)

    run_log[trading_date] = {
        'run_id': run_id,
        'status': status,
        'timestamp': datetime.now().isoformat()
    }

    with open(run_log_file, 'w') as f:
        json.dump(run_log, f, indent=2)


def load_local_state():
    """Load local trading state."""
    return load_combined_local_state()


def _normalize_holdings_dict(raw_holdings):
    """Normalize holdings to {symbol: float_qty} and drop zeroes."""
    normalized = {}

    for symbol, qty in (raw_holdings or {}).items():
        try:
            qty_float = float(qty)
        except (TypeError, ValueError):
            continue

        if abs(qty_float) > 1e-9:
            normalized[str(symbol)] = qty_float

    return normalized


def _format_holdings_sample(holdings, max_items=5):
    """Format a compact holdings preview for logs."""
    if not holdings:
        return "none"

    items = sorted(holdings.items())
    sample = ", ".join(f"{symbol}:{qty:g}" for symbol, qty in items[:max_items])
    if len(items) > max_items:
        sample += f", +{len(items) - max_items} more"
    return sample


def load_current_holdings(broker, ui=None):
    """Load current holdings with broker positions preferred over local state."""
    broker_positions = broker.get_positions() or []
    broker_holdings = _normalize_holdings_dict({
        position['symbol']: position['qty'] for position in broker_positions
    })

    local_state = load_local_state()
    local_holdings = _normalize_holdings_dict(local_state.get('positions', {}))

    if broker_holdings:
        selected_holdings = broker_holdings
        selected_source = 'broker'
    elif local_holdings:
        selected_holdings = local_holdings
        selected_source = 'local_state'
    else:
        selected_holdings = {}
        selected_source = 'empty'

    if broker_holdings and local_holdings:
        consistency = 'MATCHED' if broker_holdings == local_holdings else 'MISMATCH'
    elif broker_holdings:
        consistency = 'BROKER_ONLY'
    elif local_holdings:
        consistency = 'LOCAL_ONLY'
    else:
        consistency = 'EMPTY'

    summary = {
        'broker_holdings': broker_holdings,
        'local_holdings': local_holdings,
        'selected_holdings': selected_holdings,
        'selected_source': selected_source,
        'consistency': consistency
    }

    if ui is not None:
        ui.section("Current Holdings")
        ui.status_table({
            'Broker Holdings': len(broker_holdings),
            'Local Holdings': len(local_holdings),
            'Selected Source': selected_source,
            'Consistency': consistency
        }, "Holdings Summary")
        ui.print(f"Broker holdings sample: {_format_holdings_sample(broker_holdings)}", "cyan")
        ui.print(f"Local holdings sample: {_format_holdings_sample(local_holdings)}", "cyan")
        ui.print(f"Delta input holdings: {_format_holdings_sample(selected_holdings)}", "green")

        if consistency == 'MISMATCH':
            ui.alert_panel("Broker/local holdings mismatch - using broker positions for delta", "warning")

    return selected_holdings, summary


def load_sector_map():
    """Load symbol -> sector mapping from the data lake."""
    sector_map = {}

    if UNIVERSE_PATH.exists():
        universe_df = pd.read_csv(UNIVERSE_PATH, usecols=['Symbol', 'GICS Sector'])
        sector_map.update({
            str(symbol).replace('.', '-'): str(sector)
            for symbol, sector in universe_df.itertuples(index=False)
            if pd.notna(symbol) and pd.notna(sector) and str(sector).strip()
        })

    if PRICE_DIR.exists():
        for price_file in sorted(PRICE_DIR.glob('*.parquet')):
            symbol = price_file.stem
            if symbol in sector_map:
                continue

            try:
                sector_df = pd.read_parquet(price_file, columns=['sector'])
            except Exception:
                continue

            if 'sector' not in sector_df.columns:
                continue

            non_null = sector_df['sector'].dropna()
            if not non_null.empty:
                sector_map[symbol] = str(non_null.iloc[-1])

    return sector_map


def pre_market_recon(broker, ui):
    """Run pre-market reconciliation"""
    ui.section("Pre-Market Recon")

    # Pull broker state
    account = broker.get_account_info()
    if not account:
        ui.alert_panel("Failed to get account", "error")
        return False, None, None

    positions = broker.get_positions() or []
    open_orders = broker.list_open_orders() or []

    ui.status_table({
        'Cash': f"${account['cash']:,.2f}",
        'Equity': f"${account['equity']:,.2f}",
        'Positions': len(positions) if positions else 0,
        'Open Orders': len(open_orders) if open_orders else 0
    }, "Broker State")

    recon_report = run_broker_local_recon(broker)

    recon_ok = recon_report['overall_status'] == 'MATCHED'

    if recon_ok:
        ui.alert_panel("Pre-market recon: PASS", "success")
        return True, recon_report, account

    ui.alert_panel(f"Pre-market recon: {recon_report['overall_status']}", "error")
    ui.alert_panel("Pre-market recon mismatch - attempting broker->local auto repair", "warning")

    try:
        repair_report = sync_local_state_from_broker(broker, reason='pre_market_auto_repair')
    except Exception as exc:
        ui.alert_panel(f"Pre-market recon auto_repair_failed: {exc}", "error")
        return False, recon_report, account

    ui.status_table({
        'Before Positions': repair_report['before']['positions_count'],
        'Broker Positions': repair_report['broker']['positions_count'],
        'Before Fills': repair_report['before']['fills_count'],
        'Broker Fills': repair_report['broker']['fills_count'],
        'Fills Added': repair_report['fills_added'],
    }, "Auto Repair Summary")

    repaired_recon = run_broker_local_recon(broker)
    repaired_ok = repaired_recon['overall_status'] == 'MATCHED' or critical_recon_ok(repaired_recon)

    if repaired_ok:
        ui.alert_panel("Pre-market recon auto_repair_success", "success")
        return True, repaired_recon, account

    ui.alert_panel("Pre-market recon auto_repair_failed", "error")
    return False, repaired_recon, account


def generate_signals(ui, trading_date, sector_map=None):
    """Generate trading signals - Dual Model V10"""
    ui.section("Signal Generation (Dual Model)")

    # Load main predictions
    main_path = (_REPO_ROOT / 'data/ml2_results/main_predictions_v10.parquet')
    overlay_path = (_REPO_ROOT / 'data/ml2_results/recent_overlay_predictions.parquet')

    if not main_path.exists():
        ui.print("⚠️  No main predictions found - skipping", "yellow")
        return None, "no_predictions"

    try:
        # Load main model predictions
        main_df = pd.read_parquet(main_path)
        main_df['date'] = pd.to_datetime(main_df['timestamp']).dt.date.astype(str)

        # Use latest available date
        available_dates = main_df['date'].unique()
        if trading_date not in available_dates:
            latest_date = main_df['date'].max()
            ui.print(f"⚠️  Using latest: {latest_date}", "yellow")
            trading_date = latest_date

        main_pred_date = trading_date
        ui.print(f"MAIN_PREDICTION_DATE={main_pred_date}", "cyan")

        # Filter to trading date
        signals = main_df[main_df['date'] == trading_date].copy()
        signals['main_score'] = signals['y_pred']

        # Load and validate overlay predictions
        overlay_disabled = False
        if overlay_path.exists():
            overlay_df = pd.read_parquet(overlay_path)
            overlay_df['date'] = pd.to_datetime(overlay_df['timestamp']).dt.date.astype(str)
            overlay_latest = overlay_df['date'].max()

            ui.print(f"OVERLAY_REQUESTED_DATE={main_pred_date}", "cyan")
            ui.print(f"OVERLAY_ACTUAL_DATE={overlay_latest}", "cyan")

            if overlay_latest == main_pred_date:
                ui.print("OVERLAY_DATE_MATCH=YES", "green")
                overlay_today = overlay_df[overlay_df['date'] == main_pred_date][
                    ['symbol', 'overlay_score', 'overlay_confidence', 'overlay_filter_flag']
                ]
                signals = signals.merge(overlay_today, on='symbol', how='left')
                signals['overlay_confidence'] = signals['overlay_confidence'].fillna('mid')
                signals['overlay_filter_flag'] = signals['overlay_filter_flag'].fillna('ok')
                conf_mult = signals['overlay_confidence'].map({'high': 1.2, 'mid': 1.0, 'low': 0.7})
                signals['score_with_overlay'] = signals['main_score'] * conf_mult
                ui.print(f"✓ Overlay applied: {len(signals)} signals", "green")
            else:
                ui.print("OVERLAY_DATE_MATCH=NO", "yellow")
                ui.print("OVERLAY_DISABLED_FOR_TODAY=YES", "yellow")
                overlay_disabled = True
        else:
            ui.print("OVERLAY_DISABLED_FOR_TODAY=YES (file not found)", "yellow")
            overlay_disabled = True

        if overlay_disabled:
            signals['overlay_score'] = 0.0
            signals['overlay_confidence'] = 'mid'
            signals['overlay_filter_flag'] = 'ok'
            signals['score_with_overlay'] = signals['main_score']

        # Generate sector_neutral_score (z-score within sector)
        if sector_map:
            signals['sector'] = signals['symbol'].map(sector_map).fillna('Unknown')
            signals['sector_neutral_score'] = signals.groupby('sector')['score_with_overlay'].transform(
                lambda x: (x - x.mean()) / x.std() if x.std() > 0 else 0
            )
        else:
            signals['sector'] = 'Unknown'
            signals['sector_neutral_score'] = signals['score_with_overlay']

        # Add stock_code alias for portfolio_constructor compatibility
        signals['stock_code'] = signals['symbol']

        ui.status_table({
            'Signals': len(signals),
            'Overlay status': 'DISABLED' if overlay_disabled else 'ACTIVE',
            'Filtered bad': int((signals['overlay_filter_flag'] == 'bad').sum())
        }, "Dual Model")

        return signals, "success"

    except Exception as e:
        ui.print(f"❌ Error: {e}", "red")
        return None, "error"

    try:
        signal_runner = SignalRunner(
            predictions_path=str(predictions_path),
            model_version="ML.2_frozen",
            feature_version="B.2_frozen"
        )

        signal_runner.load_predictions()

        # Use latest available date if today's date not in predictions
        available_dates = signal_runner.predictions['date'].unique()
        if pd.to_datetime(trading_date) not in pd.to_datetime(available_dates):
            latest_date = signal_runner.predictions['date'].max()
            ui.print(f"⚠️  Using latest available predictions: {latest_date}", "yellow")
            trading_date = str(latest_date)[:10]

        signals = signal_runner.generate_signal(signal_date=trading_date, sector_map=sector_map)

        if signals is None or len(signals) == 0:
            ui.print("⚠️  No signals for today", "yellow")
            return None, "no_signals_today"

        if 'sector' in signals.columns:
            unknown_count = int((signals['sector'] == 'Unknown').sum())
            mapped_sector_count = int(signals.loc[signals['sector'] != 'Unknown', 'sector'].nunique())
            ui.status_table({
                'Mapped sectors': mapped_sector_count,
                'Unknown symbols': unknown_count
            }, "Sector Coverage")

        ui.print(f"✅ Generated {len(signals)} signals", "green")
        return signals, "success"

    except Exception as e:
        ui.print(f"❌ Signal generation failed: {e}", "red")
        return None, f"error: {e}"


def generate_target_portfolio(ui, signals, trading_date, current_holdings=None):
    """Generate target portfolio from signals"""
    ui.section("Target Portfolio Generation")

    if signals is None:
        ui.print("⚠️  No signals - skipping target generation", "yellow")
        return None, "no_signals"

    try:
        portfolio_constructor = PortfolioConstructor(
            n_stocks=20,
            max_stock_weight=0.10,
            sector_neutral=True,
            hold_buffer_percentile=0.50,
            rebalance_frequency=5
        )

        if current_holdings:
            portfolio_constructor.current_holdings = set(current_holdings.keys())

        # Check if rebalance day
        if not portfolio_constructor.should_rebalance(trading_date):
            ui.print("⚠️  Not a rebalance day", "yellow")
            return None, "not_rebalance_day"

        target_weights = portfolio_constructor.construct_target_portfolio(
            signal_data=signals,
            current_date=trading_date
        )

        if target_weights is None or len(target_weights) == 0:
            ui.print("⚠️  No target portfolio generated", "yellow")
            return None, "no_targets"

        ui.print(f"✅ Target portfolio: {len(target_weights)} stocks", "green")
        return target_weights, "success"

    except Exception as e:
        ui.print(f"❌ Target generation failed: {e}", "red")
        return None, f"error: {e}"


def calculate_portfolio_delta(ui, target_weights, current_holdings, current_cash, account_equity, tiny_config=None, regime_state="unknown", confidence_df=None):
    """Calculate portfolio delta and generate orders"""
    ui.section("Portfolio Delta Calculation")

    if target_weights is None or len(target_weights) == 0:
        ui.print("⚠️  No target weights - no orders", "yellow")
        return [], "no_targets", {}
    tiny_config = tiny_config or load_tiny_capital_config()
    orders, delta_summary, sizing_summary = build_delta_orders(
        target_weights=target_weights,
        current_holdings=current_holdings if isinstance(current_holdings, dict) else {},
        current_cash=current_cash,
        account_equity=account_equity,
        tiny_config=tiny_config,
    )

    ui.status_table({
        'Tiny mode': 'ON' if sizing_summary.get('tiny_mode_enabled') else 'OFF',
        'Capital base': f"${sizing_summary.get('effective_capital_base', 0):,.2f}",
        'Daily buy cap': f"${sizing_summary.get('max_daily_order_notional', 0):,.2f}",
        'Per-name cap': (
            "n/a"
            if sizing_summary.get('max_single_stock_notional') is None
            else f"${sizing_summary.get('max_single_stock_notional', 0):,.2f}"
        ),
        'Buy budget used': f"${sizing_summary.get('buy_budget_used', 0):,.2f}",
        'Price source': sizing_summary.get('reference_price_source', 'unknown'),
    }, "Sizing Basis")

    # V9.9a: Filter small deltas and negative net alpha (calibrated)
    cost_model = ExecutionCostModel(regime_state=regime_state)
    min_delta_threshold = 75  # Calibrated from $50 to $75

    filtered_orders = []
    filtered_small = 0
    filtered_negative = 0
    total_turnover = 0

    for order in orders:
        notional = abs(order.get('notional', 0))
        shares = abs(order.get('quantity', 100))

        # Filter 1: Small delta (calibrated)
        if notional < min_delta_threshold:
            filtered_small += 1
            continue

        # Filter 2: Negative net alpha (dynamic cost model)
        expected_alpha_bps = order.get('expected_alpha_bps', 50)
        vol_20d = 0.02  # TODO: fetch real vol
        if not cost_model.should_trade(expected_alpha_bps, notional, shares, vol_20d):
            filtered_negative += 1
            continue

        filtered_orders.append(order)
        total_turnover += notional

    estimated_turnover_pct = (total_turnover / account_equity * 100) if account_equity > 0 else 0

    ui.status_table({
        'Original orders': len(orders),
        'Filtered small': filtered_small,
        'Filtered negative': filtered_negative,
        'Final orders': len(filtered_orders),
        'Est. turnover': f"{estimated_turnover_pct:.1f}%"
    }, "V9.9a Shortfall Repair (Calibrated)")

    orders = filtered_orders

    ui.status_table({
        'Retained': delta_summary.get('retained', 0),
        'Added': delta_summary.get('added', 0),
        'Dropped': delta_summary.get('dropped', 0),
        'Orders': delta_summary.get('total_orders', 0)
    }, "Delta Summary")

    if len(orders) == 0:
        ui.print("ℹ️  No delta - portfolio already at target", "dim")
        return orders, "no_delta", delta_summary

    ui.print(f"✅ Generated {len(orders)} orders from delta", "green")
    return orders, "success", delta_summary


def execute_trading_phase(ui, broker, orders, trading_date, account, tiny_config):
    """Execute trading phase with gate/review/submit"""
    ui.section("Trading Phase")

    if len(orders) == 0:
        ui.print("ℹ️  No orders to execute", "dim")
        return 0, "no_orders", {'gate_status': 'PASS', 'gate_reasons': [], 'submitted_orders': [], 'sync': None}

    # Pre-trade gate
    ui.print("Running pre-trade gate...", "cyan")
    gate_status, gate_reasons = run_pre_trade_gate(orders, account, tiny_config)

    ui.status_table({
        'Gate Status': gate_status,
        'Checks': len(gate_reasons)
    }, "Gate Result")

    if gate_status == 'BLOCK':
        ui.print(f"❌ Gate BLOCKED: {', '.join(gate_reasons)}", "red")
        return 0, "gate_blocked", {
            'gate_status': gate_status,
            'gate_reasons': gate_reasons,
            'submitted_orders': [],
            'sync': None,
        }

    if gate_status == 'WARN':
        ui.print(f"⚠️  Gate WARN: {', '.join(gate_reasons)}", "yellow")

    ui.print(f"✅ Gate: {gate_status}", "green")

    # Manual review / auto-approve (paper + tiny = auto)
    broker_env = 'paper'  # Would read from config
    if broker_env == 'paper' and gate_status == 'PASS':
        ui.print("✅ Auto-approved (paper + tiny capital)", "green")
    else:
        ui.print("⚠️  Manual review required", "yellow")
        return 0, "awaiting_review", {
            'gate_status': gate_status,
            'gate_reasons': gate_reasons,
            'submitted_orders': [],
            'sync': None,
        }

    # Broker submission
    ui.print(f"Submitting {len(orders)} orders...", "cyan")
    submitted = 0
    submitted_orders = []

    for order in orders:
        response = broker.submit_order(order)
        if response:
            submitted += 1
            submitted_orders.append(response)
            ui.print(f"  ✅ {order['symbol']} {order['side']} {order['quantity']}", "green")
        else:
            ui.print(f"  ❌ {order['symbol']} failed", "red")

    sync_result = sync_post_trade_state(ui, broker, submitted_orders)
    exec_status = "success" if sync_result.get('status') == 'success' else "post_trade_sync_failed"

    return submitted, exec_status, {
        'gate_status': gate_status,
        'gate_reasons': gate_reasons,
        'submitted_orders': submitted_orders,
        'sync': sync_result,
    }


def sync_post_trade_state(ui, broker, submitted_orders):
    """Sync broker state back to local files after submit/fill."""
    if not submitted_orders:
        return {'status': 'no_submissions'}

    ui.print("Running post-trade broker->local sync...", "cyan")
    broker_order_ids = [o.get('broker_order_id') for o in submitted_orders if o.get('broker_order_id')]
    order_snapshots = []

    for attempt in range(1, 6):
        order_snapshots = []
        pending = 0
        for broker_order_id in broker_order_ids:
            order_details = broker.get_order(broker_order_id)
            if order_details:
                order_snapshots.append(order_details)
                if order_details.get('status') in {'created', 'accepted', 'unknown'}:
                    pending += 1

        ui.print(f"  Poll {attempt}/5: pending={pending}", "dim")
        if pending == 0:
            break
        time.sleep(2)

    try:
        sync_report = sync_local_state_from_broker(broker, reason='post_trade_broker_sync')
    except Exception as exc:
        ui.alert_panel(f"Post-trade broker->local sync failed: {exc}", "error")
        return {'status': 'failed', 'error': str(exc), 'order_snapshots': order_snapshots}

    ui.status_table({
        'Positions synced': sync_report['after']['positions_count'],
        'Cash synced': f"${sync_report['after']['cash']:,.2f}",
        'Fills synced': sync_report['after']['fills_count'],
        'Fills added': sync_report['fills_added'],
    }, "Post-Trade Sync")

    recon_report = run_broker_local_recon(broker)
    repaired = recon_report.get('overall_status') == 'MATCHED' or critical_recon_ok(recon_report)

    if repaired:
        ui.alert_panel("Post-trade broker->local sync: PASS", "success")
        return {
            'status': 'success',
            'sync_report': sync_report,
            'recon_report': recon_report,
            'order_snapshots': order_snapshots,
        }

    ui.alert_panel("Post-trade broker->local sync failed to fully reconcile", "error")
    return {
        'status': 'failed',
        'sync_report': sync_report,
        'recon_report': recon_report,
        'order_snapshots': order_snapshots,
    }


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_reduce_only_sell(order):
    """Return True when the SELL order only reduces an existing long position."""
    if str(order.get('side', '')).upper() != 'SELL':
        return False

    current_qty = _safe_float(order.get('current_shares'))
    quantity = _safe_float(order.get('quantity', order.get('qty')))
    delta_shares = _safe_float(order.get('delta_shares'))
    target_qty = _safe_float(order.get('target_shares'), current_qty + delta_shares)
    reason = str(order.get('reason', '')).lower()

    if current_qty > 0 and 0 < quantity <= current_qty and delta_shares < 0 and 0 <= target_qty <= current_qty:
        return True

    if current_qty > 0 and 0 < quantity <= current_qty and reason in {'hold_buffer_out', 'rebalance'}:
        return True

    return False


def run_pre_trade_gate(orders, account, tiny_config):
    """Run pre-trade gate checks"""
    reasons = []

    # Check 1: Cash sufficient
    total_buy_notional = sum(o['notional'] for o in orders if o['side'] == 'BUY')
    if total_buy_notional > account['cash']:
        reasons.append(f"Insufficient cash: need ${total_buy_notional:,.0f}, have ${account['cash']:,.0f}")

    # Check 2: Daily notional cap (tiny capital)
    max_daily = tiny_config.get('limits', {}).get('max_daily_order_notional', 1000)
    if total_buy_notional > max_daily:
        reasons.append(f"Daily notional cap: ${total_buy_notional:,.0f} > ${max_daily:,.0f}")

    # Check 3: Single name cap (tiny capital)
    limits = tiny_config.get('limits', {})
    max_per_stock = limits.get('max_single_stock_notional', limits.get('max_per_stock_notional', 200))
    for order in orders:
        side = str(order.get('side', '')).upper()
        notional = _safe_float(order.get('notional'))
        symbol = order.get('symbol', 'UNKNOWN')

        if side == 'BUY' and notional > max_per_stock:
            reasons.append(f"{symbol}: ${notional:.0f} > ${max_per_stock:.0f}")
        elif side == 'SELL' and not _is_reduce_only_sell(order) and notional > max_per_stock:
            reasons.append(f"{symbol} non-reduce SELL: ${notional:.0f} > ${max_per_stock:.0f}")

    # Check 4: Duplicate orders
    symbols = [o['symbol'] for o in orders]
    if len(symbols) != len(set(symbols)):
        reasons.append("Duplicate orders detected")

    # Determine status
    if len(reasons) > 0:
        return 'BLOCK', reasons

    return 'PASS', []


def main():
    """Main PT.4.4 unified entry"""
    ui = UIConsole()
    telegram = TelegramReporter()

    ui.banner()

    # Step 1: Time zone & market check
    ui.section("Time Zone & Market Status")
    ny_time = get_ny_time()
    trading_date = ny_time.strftime('%Y-%m-%d')

    ui.status_table({
        'Current Time (NY)': ny_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
        'Trading Date': trading_date
    })

    market_open, reason = is_market_open()
    ui.print(f"Market status: {reason}", "cyan")

    if not market_open:
        ui.alert_panel("Market not open - skipping", "warning")
        sys.exit(0)

    # Step 2: Idempotency check
    ui.section("Idempotency Check")
    can_run, prev_run = check_idempotency(trading_date)

    if not can_run:
        ui.alert_panel(f"Already ran today: {prev_run.get('run_id')}", "warning")
        sys.exit(0)

    ui.alert_panel("No previous run today", "success")

    # Step 3: Broker connection
    ui.section("Broker Connection")
    broker = BrokerConnection(
        config_file='Path(__file__).resolve().parent.parent/data/pt4_prep/broker_connection_config.json'
    )

    if not broker.connect():
        ui.alert_panel("Connection failed", "error")
        sys.exit(1)

    ui.alert_panel("Connected to Alpaca", "success")

    # Step 4: Pre-market recon
    recon_ok, recon_report, account = pre_market_recon(broker, ui)

    if not recon_ok:
        ui.alert_panel("Pre-market recon failed - aborting", "error")
        broker.disconnect()
        sys.exit(1)

    # Step 5: Signal generation
    current_holdings, holdings_summary = load_current_holdings(broker, ui)
    sector_map = load_sector_map()

    # Step 5: Signal generation
    signals, signal_status = generate_signals(ui, trading_date, sector_map=sector_map)

    # Step 6: Target generation
    target_weights, target_status = generate_target_portfolio(
        ui,
        signals,
        trading_date,
        current_holdings=current_holdings
    )

    # Step 6.5: V10 AI Engine Adjustments
    ui.section("V10 AI Engine Adjustments")
    regime = load_regime_state()
    if regime:
        ui.status_table({
            'Regime State': regime['state_name'],
            'Budget Multiplier': f"{regime['budget_multiplier']:.2f}",
            'Hold Buffer': f"{regime['hold_buffer']:.0%}"
        }, "Regime Engine")
    else:
        ui.print("⚠️  Regime data not found - using defaults", "yellow")

    conf_engine = ConfidenceEngine()
    conf_result, conf_df = conf_engine.run()
    ui.status_table({
        'Avg Confidence': f"{conf_result['avg_confidence']:.3f}",
        'High Conf': conf_result['high_conf_count'],
        'Low Conf': conf_result['low_conf_count']
    }, "Confidence Engine")

    # Apply V10 adjustments (真实生效)
    target_weights_v10 = apply_v10_adjustments(target_weights, regime=regime, conf_df=conf_df)

    # 使用 V10 调整后的权重 (keep stock_code column name)
    target_weights = target_weights_v10.rename(columns={'weight_v10': 'target_weight'})[['stock_code', 'target_weight']]

    ui.alert_panel("V10 adjustments applied (regime + confidence)", "success")

    # Step 7: Portfolio delta
    current_cash = account['cash']
    account_equity = account['equity']

    # Load tiny capital config
    tiny_config_file = (_REPO_ROOT / 'data/pt4_prep/tiny_capital_config.json')
    if tiny_config_file.exists():
        with open(tiny_config_file, 'r') as f:
            tiny_config = json.load(f)
    else:
        tiny_config = {'limits': {'max_daily_order_notional': 1000, 'max_per_stock_notional': 200}}

    orders, delta_status, delta_summary = calculate_portfolio_delta(
        ui,
        target_weights,
        current_holdings,
        current_cash,
        account_equity,
        tiny_config=tiny_config,
        regime_state=regime['state_name'] if regime else 'unknown',
        confidence_df=target_weights_v10,
    )

    # Step 8: Trading execution
    orders_submitted, exec_status, execution_context = execute_trading_phase(
        ui,
        broker,
        orders,
        trading_date,
        account,
        tiny_config,
    )

    final_recon_report = recon_report
    run_status = 'completed'
    summary_status = 'COMPLETED'

    sync_result = execution_context.get('sync')
    if sync_result and sync_result.get('recon_report'):
        final_recon_report = sync_result['recon_report']

    if exec_status == 'post_trade_sync_failed':
        run_status = 'post_trade_sync_failed'
        summary_status = 'POST_TRADE_SYNC_FAILED'

    # Record run
    run_id = f"pt44_{trading_date}_{ny_time.strftime('%H%M%S')}"
    record_run(trading_date, run_id, run_status)

    broker.disconnect()

    # Final summary
    ui.final_summary(
        run_id=run_id,
        status=summary_status,
        recon=final_recon_report
    )

    # Send Telegram report
    telegram.send_daily_report(
        run_id=run_id,
        status=summary_status,
        recon_report=final_recon_report,
        account_info=account,
        orders_count=orders_submitted
    )

    ui.alert_panel(f"PT.4.4 cycle completed: {run_id}", "success")
    ui.print(f"\nSignal: {signal_status} | Target: {target_status} | Delta: {delta_status} | Exec: {exec_status}", "dim")


if __name__ == '__main__':
    main()
