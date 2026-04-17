"""
PT.4.4 Scheduler Guard - Godfather V9.0
Time-based guard for launchd scheduling
"""
import sys
from pathlib import Path
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))


def get_ny_time():
    """Get current time in America/New_York"""
    return datetime.now(ZoneInfo('America/New_York'))


def is_trading_day():
    """Check if today is a trading day"""
    ny_time = get_ny_time()
    
    # Weekend check
    if ny_time.weekday() >= 5:
        return False, "Weekend"
    
    # TODO: Add holiday calendar check
    return True, "Trading day"


def is_in_run_window():
    """Check if current time is in run window (10:00-10:30 AM ET)"""
    ny_time = get_ny_time()
    current_time = ny_time.time()
    
    window_start = time(10, 0)
    window_end = time(10, 30)
    
    if current_time < window_start:
        return False, f"Before window (opens at 10:00 AM ET)"
    elif current_time >= window_end:
        return False, f"After window (closed at 10:30 AM ET)"
    
    return True, "In window"


def main():
    """Main scheduler guard"""
    print("="*80)
    print("【Godfather V9.0 - PT.4.4 Scheduler Guard】")
    print("="*80)
    print()
    
    ny_time = get_ny_time()
    print(f"Current time (NY): {ny_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print()
    
    # Check trading day
    is_trading, trading_reason = is_trading_day()
    print(f"Trading day check: {trading_reason}")
    
    if not is_trading:
        next_run = "Monday 10:00-10:30 ET" if ny_time.weekday() >= 5 else "Next trading day 10:00-10:30 ET"
        print(f"Next valid run: {next_run}")
        print()
        print("⏸️  Skip: Not a trading day")
        sys.exit(0)
    
    # Check run window
    in_window, window_reason = is_in_run_window()
    print(f"Run window check: {window_reason}")
    
    if not in_window:
        next_run_date = ny_time.strftime('%Y-%m-%d') if ny_time.time() < time(10, 0) else (ny_time + timedelta(days=1)).strftime('%Y-%m-%d')
        print(f"Next valid run: {next_run_date} 10:00:00 EDT")
        print()
        print("⏸️  Skip: Outside run window")
        sys.exit(0)
    
    # All checks passed - run PT.4.4
    print()
    print("✅ All checks passed - executing PT.4.4 unified entry")
    print("="*80)
    print()
    
    # Import and run PT.4.4
    from paper_trading.run_pt44_unified import main as pt44_main
    pt44_main()


if __name__ == '__main__':
    main()
