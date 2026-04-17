"""
PT.4.3 Scheduler Guard - Godfather V9.0
Time-based guard for launchd/cron scheduling
"""
import sys
from pathlib import Path
from datetime import datetime, time
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))


def get_ny_time():
    """Get current time in America/New_York"""
    return datetime.now(ZoneInfo('America/New_York'))


def is_trading_day():
    """Check if today is a trading day"""
    ny_time = get_ny_time()

    # Check if weekday (Mon-Fri)
    if ny_time.weekday() >= 5:
        return False, "Weekend"

    # TODO: Add holiday calendar check
    return True, "Trading day"


def is_in_run_window():
    """Check if current time is in valid run window"""
    ny_time = get_ny_time()
    current_time = ny_time.time()

    # Run window: 10:00 AM - 10:30 AM ET (after market open at 9:30)
    window_start = time(10, 0)
    window_end = time(10, 30)

    if window_start <= current_time <= window_end:
        return True, "In run window"
    elif current_time < window_start:
        return False, f"Before window (opens at 10:00 AM ET)"
    else:
        return False, f"After window (closed at 10:30 AM ET)"


def get_next_valid_run():
    """Calculate next valid run time"""
    ny_time = get_ny_time()

    # If weekend, next Monday 10:00 AM
    if ny_time.weekday() >= 5:
        days_until_monday = (7 - ny_time.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 1
        next_run = ny_time.replace(hour=10, minute=0, second=0, microsecond=0)
        from datetime import timedelta
        next_run = next_run + timedelta(days=days_until_monday)
        return next_run.strftime('%Y-%m-%d %H:%M:%S %Z')

    # If before window, today 10:00 AM
    if ny_time.time() < time(10, 0):
        next_run = ny_time.replace(hour=10, minute=0, second=0, microsecond=0)
        return next_run.strftime('%Y-%m-%d %H:%M:%S %Z')

    # If after window, next day 10:00 AM
    if ny_time.time() > time(10, 30):
        from datetime import timedelta
        next_run = ny_time.replace(hour=10, minute=0, second=0, microsecond=0)
        next_run = next_run + timedelta(days=1)
        return next_run.strftime('%Y-%m-%d %H:%M:%S %Z')

    return "Now"


def main():
    """Scheduler guard main"""
    print("="*80)
    print("【Godfather V9.0 - PT.4.3 Scheduler Guard】")
    print("="*80)
    print()

    ny_time = get_ny_time()
    print(f"Current time (NY): {ny_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print()

    # Check trading day
    is_trading, trading_reason = is_trading_day()
    print(f"Trading day check: {trading_reason}")

    if not is_trading:
        next_run = get_next_valid_run()
        print(f"Next valid run: {next_run}")
        print("\n⏸️  Skip: Not a trading day")
        sys.exit(0)

    # Check run window
    in_window, window_reason = is_in_run_window()
    print(f"Run window check: {window_reason}")

    if not in_window:
        next_run = get_next_valid_run()
        print(f"Next valid run: {next_run}")
        print("\n⏸️  Skip: Outside run window")
        sys.exit(0)

    print("\n✅ Conditions met - proceeding to PT.4.3")
    print()

    # Execute PT.4.3
    import subprocess
    result = subprocess.run(
        [sys.executable, 'paper_trading/run_pt43_safeguarded.py'],
        cwd=Path(__file__).parent.parent,
        capture_output=False
    )

    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
