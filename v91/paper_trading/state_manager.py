"""
State Manager - Godfather V9.0 Phase PT.2
Persistent state management for continuous paper trading
"""
import json
import pandas as pd
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime


class StateManager:
    """
    Manage persistent state for continuous paper trading

    Features:
    - Save/load broker state (positions, cash, PnL)
    - Track processed dates
    - Run ID management
    - Checkpoint/resume support
    """

    def __init__(self, state_dir: str):
        """
        Initialize state manager

        Args:
            state_dir: Directory for state files
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.state_file = self.state_dir / 'broker_state.json'
        self.processed_dates_file = self.state_dir / 'processed_dates.json'
        self.run_log_file = self.state_dir / 'run_log.jsonl'

        print(f"Initializing StateManager (Godfather V9.0 - PT.2)...")
        print(f"  State directory: {self.state_dir}")

    def save_broker_state(
        self,
        cash: float,
        positions: Dict,
        position_costs: Dict,
        realized_pnl: float,
        total_transaction_costs: float,
        date: str
    ):
        """Save broker state to disk"""
        state = {
            'date': date,
            'timestamp': datetime.now().isoformat(),
            'cash': cash,
            'positions': positions,
            'position_costs': position_costs,
            'realized_pnl': realized_pnl,
            'total_transaction_costs': total_transaction_costs
        }

        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def load_broker_state(self) -> Optional[Dict]:
        """Load broker state from disk"""
        if not self.state_file.exists():
            return None

        with open(self.state_file, 'r') as f:
            return json.load(f)

    def mark_date_processed(self, date: str, run_id: str, status: str):
        """Mark a date as processed"""
        if self.processed_dates_file.exists():
            with open(self.processed_dates_file, 'r') as f:
                processed = json.load(f)
        else:
            processed = {}

        processed[date] = {
            'run_id': run_id,
            'status': status,
            'timestamp': datetime.now().isoformat()
        }

        with open(self.processed_dates_file, 'w') as f:
            json.dump(processed, f, indent=2)

    def is_date_processed(self, date: str) -> bool:
        """Check if date has been processed"""
        if not self.processed_dates_file.exists():
            return False

        with open(self.processed_dates_file, 'r') as f:
            processed = json.load(f)

        return date in processed

    def get_processed_dates(self) -> Dict:
        """Get all processed dates"""
        if not self.processed_dates_file.exists():
            return {}

        with open(self.processed_dates_file, 'r') as f:
            return json.load(f)

    def log_run(self, run_id: str, date: str, status: str, summary: Dict):
        """Append run log entry"""
        log_entry = {
            'run_id': run_id,
            'date': date,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'summary': summary
        }

        with open(self.run_log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

    def get_last_run_id(self) -> Optional[str]:
        """Get last run ID"""
        if not self.run_log_file.exists():
            return None

        with open(self.run_log_file, 'r') as f:
            lines = f.readlines()

        if len(lines) == 0:
            return None

        last_entry = json.loads(lines[-1])
        return last_entry['run_id']

    def reset_state(self):
        """Reset all state (use with caution)"""
        if self.state_file.exists():
            self.state_file.unlink()
        if self.processed_dates_file.exists():
            self.processed_dates_file.unlink()

        print("⚠️  State reset complete")
