"""
Broker Mode Switch - Godfather V9.0 PT.4.1
Switch between shadow and live tiny mode
"""
import json
from pathlib import Path
from enum import Enum


class BrokerMode(Enum):
    """Broker execution modes"""
    SHADOW = "shadow"
    LIVE_TINY = "live_tiny"


class BrokerModeSwitch:
    """Manage broker mode switching"""

    def __init__(self, config_file: str):
        self.config_file = Path(config_file)
        self.config = self._load_config()

    def _load_config(self):
        """Load broker mode config"""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                return json.load(f)
        else:
            # Default to shadow mode
            return {
                'current_mode': BrokerMode.SHADOW.value,
                'live_enabled': False,
                'require_manual_approval': True
            }

    def get_current_mode(self) -> BrokerMode:
        """Get current broker mode"""
        mode_str = self.config.get('current_mode', 'shadow')
        return BrokerMode(mode_str)

    def can_use_live_mode(self) -> bool:
        """Check if live mode is enabled"""
        return self.config.get('live_enabled', False)

    def switch_to_live_tiny(self, approved_by: str, reason: str) -> bool:
        """
        Switch to live tiny mode
        Requires manual approval
        """
        if not self.can_use_live_mode():
            print("❌ Live mode not enabled in config")
            return False

        if self.config.get('require_manual_approval', True):
            print(f"⚠️  Switching to LIVE_TINY mode")
            print(f"   Approved by: {approved_by}")
            print(f"   Reason: {reason}")

        self.config['current_mode'] = BrokerMode.LIVE_TINY.value
        self.config['last_switch_timestamp'] = str(Path(__file__).stat().st_mtime)
        self.config['last_switch_by'] = approved_by
        self.config['last_switch_reason'] = reason

        self._save_config()
        return True

    def switch_to_shadow(self, reason: str = "Manual switch") -> bool:
        """Switch back to shadow mode"""
        print(f"Switching to SHADOW mode: {reason}")

        self.config['current_mode'] = BrokerMode.SHADOW.value
        self.config['last_switch_timestamp'] = str(Path(__file__).stat().st_mtime)
        self.config['last_switch_reason'] = reason

        self._save_config()
        return True

    def _save_config(self):
        """Save config to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
