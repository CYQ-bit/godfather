"""
UI Console - Godfather V9.0
Rich terminal command center interface
"""
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("⚠️  Rich not available, falling back to plain output")


class UIConsole:
    """Rich terminal UI for Godfather V9.0"""

    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None

    def banner(self):
        """Display startup banner"""
        if not RICH_AVAILABLE:
            print("="*80)
            print("【Godfather V9.0 - Command Center】")
            print("="*80)
            return

        banner_text = Text()
        banner_text.append("Godfather V9.0\n", style="bold cyan")
        banner_text.append("PT.4.3 Safeguarded Continuous Tiny Paper", style="dim")

        panel = Panel(
            banner_text,
            title="[bold]Command Center[/bold]",
            border_style="cyan",
            box=box.DOUBLE
        )
        self.console.print(panel)
        self.console.print()

    def section(self, title: str):
        """Display section header"""
        if not RICH_AVAILABLE:
            print(f"\n{'='*80}")
            print(f"【{title}】")
            print(f"{'='*80}\n")
            return

        self.console.rule(f"[bold cyan]{title}[/bold cyan]")
        self.console.print()

    def status_table(self, items: dict, title: str = "Status"):
        """Display status table"""
        if not RICH_AVAILABLE:
            print(f"\n{title}:")
            for key, value in items.items():
                print(f"  {key}: {value}")
            print()
            return

        table = Table(title=title, box=box.ROUNDED, show_header=False)
        table.add_column("Item", style="cyan")
        table.add_column("Value", style="green")

        for key, value in items.items():
            table.add_row(key, str(value))

        self.console.print(table)
        self.console.print()

    def alert_panel(self, message: str, level: str = "info"):
        """Display alert panel"""
        if not RICH_AVAILABLE:
            icon = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "success": "✅"}.get(level, "•")
            print(f"{icon} {message}")
            return

        style_map = {
            "info": "blue",
            "warning": "yellow",
            "error": "red",
            "success": "green"
        }
        style = style_map.get(level, "white")

        panel = Panel(
            message,
            border_style=style,
            box=box.ROUNDED
        )
        self.console.print(panel)

    def final_summary(self, run_id: str, status: str, pnl: float = None, recon: dict = None):
        """Display final summary"""
        if not RICH_AVAILABLE:
            print("\n" + "="*80)
            print("【Final Summary】")
            print(f"  Run ID: {run_id}")
            print(f"  Status: {status}")
            if pnl is not None:
                print(f"  P&L: ${pnl:,.2f}")
            if recon:
                print(f"  Recon: {recon.get('overall_status', 'N/A')}")
            print("="*80)
            return

        table = Table(title="Final Summary", box=box.DOUBLE, show_header=False)
        table.add_column("Item", style="bold cyan")
        table.add_column("Value", style="bold green")

        table.add_row("Run ID", run_id)
        table.add_row("Status", status)

        if pnl is not None:
            pnl_style = "green" if pnl >= 0 else "red"
            table.add_row("P&L", f"[{pnl_style}]${pnl:,.2f}[/{pnl_style}]")

        if recon:
            recon_status = recon.get('overall_status', 'N/A')
            recon_style = "green" if recon_status == 'MATCHED' else "red"
            table.add_row("Recon", f"[{recon_style}]{recon_status}[/{recon_style}]")

        self.console.print(table)
        self.console.print()

    def print(self, message: str, style: str = None):
        """Print message with optional style"""
        if not RICH_AVAILABLE:
            print(message)
            return

        if style:
            self.console.print(message, style=style)
        else:
            self.console.print(message)
