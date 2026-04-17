"""
Telegram Reporter - Godfather V9.1 Sandbox
Daily battle report via Telegram
"""
import os
import json
import requests
from pathlib import Path
from datetime import datetime


class TelegramReporter:
    """Telegram battle report sender"""

    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.report_prefix = os.getenv('GODFATHER_TELEGRAM_PREFIX', '[V9.1 Sandbox]')
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled:
            print("ℹ️  Telegram reporter disabled (missing token or chat_id)")

    def send_message(self, text: str) -> bool:
        """Send telegram message"""
        if not self.enabled:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': 'Markdown'
            }

            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                print("✅ Telegram message sent")
                return True
            else:
                print(f"⚠️  Telegram send failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"⚠️  Telegram error: {e}")
            return False

    def build_daily_report(self, run_id: str, status: str, recon_report: dict = None,
                          account_info: dict = None, orders_count: int = 0) -> str:
        """Build daily battle report"""
        report_lines = []

        report_lines.append(f"🤖 *{self.report_prefix} Godfather V9.1 Sandbox - Daily Battle Report*")
        report_lines.append("")
        report_lines.append(f"📅 Date: {datetime.now().strftime('%Y-%m-%d')}")
        report_lines.append(f"🆔 Run ID: `{run_id}`")
        report_lines.append(f"📊 Status: *{status}*")
        report_lines.append("")

        # Orders
        report_lines.append(f"📝 Orders: {orders_count}")
        report_lines.append("")

        # Account
        if account_info:
            cash = account_info.get('cash', 0)
            equity = account_info.get('equity', 0)
            report_lines.append("💰 Account:")
            report_lines.append(f"  Cash: ${cash:,.2f}")
            report_lines.append(f"  Equity: ${equity:,.2f}")
            report_lines.append("")

        # Recon
        if recon_report:
            overall = recon_report.get('overall_status', 'UNKNOWN')
            icon = "✅" if overall == 'MATCHED' else "❌"
            report_lines.append(f"{icon} Recon: *{overall}*")

            checks = recon_report.get('checks', [])
            for check in checks:
                check_name = check.get('check', 'unknown')
                check_status = check.get('status', 'unknown')
                check_icon = "✅" if check_status == 'MATCHED' else "❌"
                report_lines.append(f"  {check_icon} {check_name}: {check_status}")
            report_lines.append("")

        report_lines.append("---")
        report_lines.append(f"_{self.report_prefix} Godfather V9.1 Sandbox_")

        return "\n".join(report_lines)

    def send_daily_report(self, run_id: str, status: str, recon_report: dict = None,
                         account_info: dict = None, orders_count: int = 0) -> bool:
        """Send daily battle report"""
        if not self.enabled:
            print("ℹ️  Telegram report skipped (not configured)")
            return False

        report = self.build_daily_report(run_id, status, recon_report, account_info, orders_count)
        return self.send_message(report)

    def send_test_message(self) -> bool:
        """Send test message"""
        if not self.enabled:
            print("❌ Telegram not configured")
            return False

        test_msg = f"🤖 {self.report_prefix} Godfather V9.1 Sandbox - Test Message\n\nTelegram reporter is working!"
        return self.send_message(test_msg)
