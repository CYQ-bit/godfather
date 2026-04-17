"""
PT.4.4b Foreground Commander - Godfather V9.0
Continuous foreground command center with live status updates
"""
import json
import sys
import os
import time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
env_file = Path(__file__).parent.parent / '.env.godfather'
if env_file.exists():
    with open(env_file, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#') and '=' in line:
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

from paper_trading.broker_connection import BrokerConnection
from paper_trading.broker_recon_adapter import BrokerReconAdapter
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))

try:
    from rich.live import Live
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.console import Console
    from rich.text import Text
    from rich import box
    from rich.align import Align
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
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


def load_state_file(file_path):
    """Load JSON state file safely"""
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
    table.add_row("Phase", "PT.4.4b Foreground Commander")
    table.add_row("NY Time", ny_time.strftime('%Y-%m-%d %H:%M:%S %Z'))

    status_style = "green" if market_open else "yellow"
    table.add_row("Market", f"[{status_style}]{market_status}[/{status_style}]")

    return Panel(table, title="[bold cyan]System[/bold cyan]", border_style="cyan")


def get_run_status_panel():
    """Run status panel"""
    run_log = load_state_file('Path(__file__).resolve().parent.parent/data/paper_trading/state/daily_run_log.json')

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
        else:
            table.add_row("Latest Run ID", "N/A")
            table.add_row("Status", "Waiting")
    else:
        table.add_row("Latest Run ID", "N/A")
        table.add_row("Status", "Waiting")

    return Panel(table, title="[bold cyan]Run Status[/bold cyan]", border_style="cyan")


def get_portfolio_panel():
    """Portfolio panel"""
    state = load_state_file('Path(__file__).resolve().parent.parent/data/paper_trading/state/pt42_complete_state.json')

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
    dashboard = load_state_file('Path(__file__).resolve().parent.parent/data/paper_trading/dashboard/dashboard_summary.json')

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="green")

    if dashboard and 'recon' in dashboard:
        recon = dashboard['recon']
        checks = recon.get('checks', [])
        for check in checks:
            check_name = check.get('check', 'unknown')
            check_status = check.get('status', 'unknown')

            if check_status == 'MATCHED':
                table.add_row(check_name, "[green]✓ MATCHED[/green]")
            else:
                table.add_row(check_name, f"[red]✗ {check_status}[/red]")

        overall = recon.get('overall_status', 'UNKNOWN')
        overall_style = "green" if overall == 'MATCHED' else "red"
        table.add_row("", "")
        table.add_row("Overall", f"[{overall_style}]{overall}[/{overall_style}]")
    else:
        table.add_row("Orders", "N/A")
        table.add_row("Fills", "N/A")
        table.add_row("Positions", "N/A")
        table.add_row("Cash", "N/A")

    return Panel(table, title="[bold cyan]Recon[/bold cyan]", border_style="cyan")


def get_telegram_panel():
    """Telegram status panel"""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Item", style="cyan")
    table.add_column("Value", style="green")

    if bot_token and chat_id:
        table.add_row("Bot Token", f"{bot_token[:20]}...")
        table.add_row("Chat ID", chat_id)
        table.add_row("Status", "[green]✓ Enabled[/green]")
    else:
        table.add_row("Bot Token", "Not set" if not bot_token else f"{bot_token[:20]}...")
        table.add_row("Chat ID", "Not set" if not chat_id else chat_id)
        table.add_row("Status", "[yellow]⚠ Disabled[/yellow]")

    return Panel(table, title="[bold cyan]Telegram[/bold cyan]", border_style="cyan")


def get_broker_panel():
    """Broker/Execution panel"""
    fills = load_state_file('Path(__file__).resolve().parent.parent/data/paper_trading/state/fills_ledger.json')

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

    return Panel(table, title="[bold cyan]Broker[/bold cyan]", border_style="cyan")


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
        Layout(name="telegram"),
        Layout(name="broker")
    )

    # Header
    header_text = Text("Godfather V9.0 - PT.4.4b Foreground Commander", style="bold cyan", justify="center")
    layout["header"].update(Panel(header_text, border_style="cyan"))

    # Panels
    layout["system"].update(get_system_panel())
    layout["run"].update(get_run_status_panel())
    layout["portfolio"].update(get_portfolio_panel())
    layout["recon"].update(get_recon_panel())
    layout["telegram"].update(get_telegram_panel())
    layout["broker"].update(get_broker_panel())

    # Footer
    footer_text = Text("Press Ctrl+C to exit | Refresh: 30s", style="dim", justify="center")
    layout["footer"].update(Panel(footer_text, border_style="cyan"))

    return layout


def main():
    """Main foreground commander loop"""
    console = Console()

    console.print("\n[bold cyan]🚀 Starting PT.4.4b Foreground Commander...[/bold cyan]")
    console.print("[dim]Press Ctrl+C to exit[/dim]\n")

    time.sleep(2)

    try:
        with Live(generate_dashboard(), refresh_per_second=0.2, screen=True) as live:
            while True:
                time.sleep(30)  # Refresh every 30 seconds
                live.update(generate_dashboard())
    except KeyboardInterrupt:
        console.print("\n\n[bold green]✅ Foreground Commander stopped gracefully[/bold green]")
        sys.exit(0)


if __name__ == '__main__':
    main()
