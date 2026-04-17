"""
PT.4.3 Watchtower Terminal - Godfather V9.0
Real-time observation tower with rich.live dashboard
"""
import json
import sys
import time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))

try:
    from rich.live import Live
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    print("❌ Rich not available - install with: pip3 install rich")
    sys.exit(1)


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


def load_json_safe(file_path):
    """Load JSON file safely"""
    try:
        if Path(file_path).exists():
            with open(file_path, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return None


def get_system_panel():
    """System status panel"""
    ny_time = get_ny_time()
    market_open, market_status = is_market_open()

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Item", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Version", "Godfather V9.0")
    table.add_row("Phase", "PT.4.3 Watchtower")
    table.add_row("NY Time", ny_time.strftime('%Y-%m-%d %H:%M:%S %Z'))

    status_style = "green" if market_open else "yellow"
    table.add_row("Market", f"[{status_style}]{market_status}[/{status_style}]")

    # Next run time
    next_run = "Tomorrow 10:00-10:30 ET" if ny_time.hour >= 10 else "Today 10:00-10:30 ET"
    table.add_row("Next Run", next_run)

    return Panel(table, title="[bold cyan]System[/bold cyan]", border_style="cyan")


def get_run_status_panel():
    """Run status panel"""
    run_log = load_json_safe('Path(__file__).resolve().parent.parent/data/paper_trading/state/daily_run_log.json')

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Item", style="cyan")
    table.add_column("Value", style="green")

    if run_log:
        trading_date = get_ny_time().strftime('%Y-%m-%d')
        latest_run = run_log.get(trading_date, {})

        if latest_run:
            table.add_row("Latest Run ID", latest_run.get('run_id', 'N/A'))
            table.add_row("Status", latest_run.get('status', 'N/A'))
            table.add_row("Timestamp", latest_run.get('timestamp', 'N/A')[:19])
            table.add_row("Idempotency", "[green]Protected[/green]")
        else:
            table.add_row("Latest Run ID", "N/A")
            table.add_row("Status", "Waiting")
            table.add_row("Idempotency", "[yellow]Ready[/yellow]")
    else:
        table.add_row("Latest Run ID", "N/A")
        table.add_row("Status", "Waiting")
        table.add_row("Idempotency", "[yellow]Ready[/yellow]")

    return Panel(table, title="[bold cyan]Run Status[/bold cyan]", border_style="cyan")


def get_portfolio_panel():
    """Portfolio panel"""
    state = load_json_safe('Path(__file__).resolve().parent.parent/data/paper_trading/state/pt42_complete_state.json')

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Item", style="cyan")
    table.add_column("Value", style="green")

    if state:
        cash = state.get('cash', 0)
        equity = state.get('equity', 0)
        positions = state.get('positions', {})

        table.add_row("Cash", f"${cash:,.2f}")
        table.add_row("Equity", f"${equity:,.2f}")
        table.add_row("Positions", str(len(positions)))

        if positions:
            holdings = []
            for symbol, qty in list(positions.items())[:3]:
                # Handle both dict and scalar position values
                if isinstance(qty, dict):
                    qty = qty.get('quantity', 0)
                holdings.append(f"{symbol}: {qty}")
            table.add_row("Holdings", ", ".join(holdings))
    else:
        table.add_row("Cash", "N/A")
        table.add_row("Equity", "N/A")
        table.add_row("Positions", "N/A")

    return Panel(table, title="[bold cyan]Portfolio[/bold cyan]", border_style="cyan")


def get_recon_panel():
    """Reconciliation panel"""
    dashboard = load_json_safe('Path(__file__).resolve().parent.parent/data/paper_trading/dashboard/dashboard_summary.json')

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="green")

    if dashboard and 'recon' in dashboard:
        recon = dashboard['recon']
        overall = recon.get('overall_status', 'UNKNOWN')

        checks = recon.get('checks', [])
        for check in checks:
            check_name = check.get('check', 'unknown')
            check_status = check.get('status', 'unknown')

            if check_status == 'MATCHED':
                table.add_row(check_name, "[green]✓ MATCHED[/green]")
            else:
                table.add_row(check_name, f"[red]✗ {check_status}[/red]")

        overall_style = "green" if overall == 'MATCHED' else "red"
        table.add_row("", "")
        table.add_row("Overall", f"[{overall_style}]{overall}[/{overall_style}]")
    else:
        table.add_row("Orders", "N/A")
        table.add_row("Fills", "N/A")
        table.add_row("Positions", "N/A")
        table.add_row("Cash", "N/A")
        table.add_row("Overall", "[yellow]Waiting[/yellow]")

    return Panel(table, title="[bold cyan]Recon[/bold cyan]", border_style="cyan")


def get_alerts_panel():
    """Alerts panel"""
    dashboard = load_json_safe('Path(__file__).resolve().parent.parent/data/paper_trading/dashboard/dashboard_summary.json')

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Item", style="cyan")
    table.add_column("Value", style="green")

    if dashboard and 'alerts' in dashboard:
        alerts = dashboard['alerts']

        risk_status = alerts.get('risk_status', 'N/A')
        drift_status = alerts.get('drift_status', 'N/A')
        halt_status = alerts.get('halt_status', 'N/A')

        table.add_row("Risk", risk_status)
        table.add_row("Drift", drift_status)
        table.add_row("HALT", halt_status)
    else:
        table.add_row("Risk", "N/A")
        table.add_row("Drift", "N/A")
        table.add_row("HALT", "N/A")

    return Panel(table, title="[bold cyan]Alerts[/bold cyan]", border_style="cyan")


def get_broker_panel():
    """Broker/Execution panel"""
    fills = load_json_safe('Path(__file__).resolve().parent.parent/data/paper_trading/state/fills_ledger.json')

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Item", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Broker", "Alpaca Paper")
    table.add_row("Connection", "[green]Ready[/green]")

    if fills and len(fills) > 0:
        latest_fill = fills[-1]
        symbol = latest_fill.get('symbol', 'N/A')
        side = latest_fill.get('side', 'N/A')
        qty = latest_fill.get('qty', 0)
        price = latest_fill.get('price', 0)

        table.add_row("Latest Fill", f"{symbol} {side} {qty}@${price:.2f}")
        table.add_row("Total Fills", str(len(fills)))
    else:
        table.add_row("Latest Fill", "N/A")
        table.add_row("Total Fills", "0")

    return Panel(table, title="[bold cyan]Broker/Execution[/bold cyan]", border_style="cyan")


def generate_dashboard():
    """Generate full dashboard layout"""
    layout = Layout()

    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3)
    )

    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right")
    )

    layout["left"].split_column(
        Layout(name="system"),
        Layout(name="run"),
        Layout(name="portfolio")
    )

    layout["right"].split_column(
        Layout(name="recon"),
        Layout(name="alerts"),
        Layout(name="broker")
    )

    # Header
    header_text = Text("Godfather V9.0 - PT.4.3 Watchtower Terminal", style="bold cyan", justify="center")
    layout["header"].update(Panel(header_text, border_style="cyan"))

    # Panels
    layout["system"].update(get_system_panel())
    layout["run"].update(get_run_status_panel())
    layout["portfolio"].update(get_portfolio_panel())
    layout["recon"].update(get_recon_panel())
    layout["alerts"].update(get_alerts_panel())
    layout["broker"].update(get_broker_panel())

    # Footer
    footer_text = Text("Press Ctrl+C to exit | Refresh: 5s", style="dim", justify="center")
    layout["footer"].update(Panel(footer_text, border_style="cyan"))

    return layout


def main():
    """Main watchtower loop"""
    print("🔭 Starting PT.4.3 Watchtower Terminal...")
    print("Press Ctrl+C to exit\n")

    try:
        with Live(generate_dashboard(), refresh_per_second=0.2, screen=True) as live:
            while True:
                time.sleep(5)
                live.update(generate_dashboard())
    except KeyboardInterrupt:
        print("\n\n✅ Watchtower terminal stopped gracefully")
        sys.exit(0)


if __name__ == '__main__':
    main()
