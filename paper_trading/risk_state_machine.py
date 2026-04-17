"""
Risk State Machine - Godfather V9.0 Phase PT.2
Enhanced risk guard with OK/WARN/HALT state machine
"""
from enum import Enum
from typing import Dict, List, Tuple
from datetime import datetime


class RiskState(Enum):
    """Risk states"""
    OK = "OK"
    WARN = "WARN"
    HALT = "HALT"


class RiskStateMachine:
    """
    Risk state machine for continuous paper trading

    States:
    - OK: All checks passed, can continue trading
    - WARN: Some violations detected, can continue with caution
    - HALT: Critical violations, must stop trading

    PT.2 Features:
    - Consecutive violation tracking
    - State transition logic
    - Alert aggregation
    - Trading permission control
    """

    def __init__(
        self,
        max_consecutive_warns: int = 3,
        max_consecutive_halts: int = 1,
        startup_grace_period: int = 6,
        trend_aware: bool = True,
        regime_aware: bool = True,
        manual_override_file: str = None
    ):
        """
        Initialize risk state machine

        Args:
            max_consecutive_warns: Max consecutive WARNs before HALT
            max_consecutive_halts: Max consecutive HALTs before permanent stop
            startup_grace_period: Number of rebalances to observe before drift HALT
            trend_aware: Enable trend-aware HALT (don't HALT if improving)
            regime_aware: Enable regime-aware HALT (relax in high-vol)
            manual_override_file: Path to manual override config file
        """
        self.max_consecutive_warns = max_consecutive_warns
        self.max_consecutive_halts = max_consecutive_halts
        self.startup_grace_period = startup_grace_period
        self.trend_aware = trend_aware
        self.regime_aware = regime_aware
        self.manual_override_file = manual_override_file

        self.current_state = RiskState.OK
        self.consecutive_warns = 0
        self.consecutive_halts = 0
        self.rebalance_count = 0

        self.state_history = []
        self.alert_history = []

        # Metric history for trend detection
        self.metric_history = {
            'turnover': [],
            'retained': [],
            'impl_shortfall': []
        }

        print(f"Initializing RiskStateMachine (Godfather V9.0 - PT.2)...")
        print(f"  Max consecutive WARNs: {self.max_consecutive_warns}")
        print(f"  Max consecutive HALTs: {self.max_consecutive_halts}")
        print(f"  Startup grace period: {self.startup_grace_period} rebalances")
        print(f"  Trend-aware HALT: {self.trend_aware}")
        print(f"  Regime-aware HALT: {self.regime_aware}")

    def evaluate_risk_status(
        self,
        risk_results: Dict,
        drift_results: Dict
    ) -> Tuple[RiskState, List[str]]:
        """
        Evaluate overall risk status from risk and drift checks

        Args:
            risk_results: Results from RiskGuard
            drift_results: Results from DriftMonitor

        Returns:
            (risk_state, list of alerts)
        """
        alerts = []

        # Aggregate risk violations
        risk_status = risk_results.get('overall_status', 'OK')
        risk_violations = risk_results.get('violations', [])

        if len(risk_violations) > 0:
            alerts.extend([f"RISK: {v}" for v in risk_violations])

        # Aggregate drift violations
        drift_status = drift_results.get('drift_status', 'OK')
        drift_checks = drift_results.get('checks', {})

        for check_name, check_result in drift_checks.items():
            if check_result.get('drift_detected', False):
                violations = check_result.get('violations', [])
                if len(violations) > 0:
                    alerts.extend([f"DRIFT/{check_name}: {v}" for v in violations])
                else:
                    alerts.append(f"DRIFT/{check_name}: detected")

        # Determine state
        if risk_status == 'HALT':
            new_state = RiskState.HALT
        elif risk_status == 'WARN' or drift_status == 'WARN':
            new_state = RiskState.WARN
        else:
            new_state = RiskState.OK

        return new_state, alerts

    def track_metrics(self, metrics: Dict):
        """
        Track metrics for trend detection

        Args:
            metrics: Dict with turnover, retained, impl_shortfall
        """
        if 'turnover' in metrics:
            self.metric_history['turnover'].append(metrics['turnover'])
        if 'retained' in metrics:
            self.metric_history['retained'].append(metrics['retained'])
        if 'impl_shortfall' in metrics:
            self.metric_history['impl_shortfall'].append(metrics['impl_shortfall'])

    def detect_trend(self, metric_name: str, window: int = 3) -> str:
        """
        Detect trend in metric (improving/worsening/flat)

        Args:
            metric_name: Name of metric to check
            window: Number of recent observations to check

        Returns:
            'improving', 'worsening', 'flat', or 'insufficient_data'
        """
        history = self.metric_history.get(metric_name, [])

        if len(history) < 2:
            return 'insufficient_data'

        # Get recent window
        recent = history[-min(window, len(history)):]

        if len(recent) < 2:
            return 'insufficient_data'

        # For turnover and impl_shortfall: lower is better
        # For retained: higher is better
        if metric_name in ['turnover', 'impl_shortfall']:
            # Check if decreasing (improving)
            if all(recent[i] >= recent[i+1] for i in range(len(recent)-1)):
                return 'improving'
            elif all(recent[i] <= recent[i+1] for i in range(len(recent)-1)):
                return 'worsening'
            else:
                return 'flat'
        elif metric_name == 'retained':
            # Check if increasing (improving)
            if all(recent[i] <= recent[i+1] for i in range(len(recent)-1)):
                return 'improving'
            elif all(recent[i] >= recent[i+1] for i in range(len(recent)-1)):
                return 'worsening'
            else:
                return 'flat'

        return 'flat'

    def is_drift_improving(self) -> bool:
        """
        Check if drift metrics are improving

        Returns:
            True if any key metric is improving
        """
        turnover_trend = self.detect_trend('turnover')
        retained_trend = self.detect_trend('retained')

        # If either turnover decreasing or retained increasing, consider improving
        return turnover_trend == 'improving' or retained_trend == 'improving'

    def update_state(
        self,
        risk_results: Dict,
        drift_results: Dict,
        date: str,
        regime: str = 'normal',
        metrics: Dict = None
    ) -> Dict:
        """
        Update state machine based on risk and drift results

        Args:
            risk_results: Results from RiskGuard
            drift_results: Results from DriftMonitor
            date: Current date
            regime: Current market regime (normal/high_vol/extreme)
            metrics: Dict with turnover, retained, impl_shortfall for trend tracking

        Returns:
            State update summary
        """
        # Track metrics for trend detection
        if metrics:
            self.track_metrics(metrics)

        # Increment rebalance count
        self.rebalance_count += 1

        new_state, alerts = self.evaluate_risk_status(risk_results, drift_results)

        # Check if this is a hard risk violation (always HALT)
        risk_status = risk_results.get('overall_status', 'OK')
        is_hard_risk = risk_status == 'HALT'

        # Check if this is a drift violation
        drift_status = drift_results.get('drift_status', 'OK')
        is_drift_warn = drift_status == 'WARN' and not is_hard_risk

        # Apply startup grace period for drift violations
        in_grace_period = self.rebalance_count <= self.startup_grace_period
        if in_grace_period and is_drift_warn:
            new_state = RiskState.WARN
            alerts.append(f"GRACE_PERIOD: Rebalance {self.rebalance_count}/{self.startup_grace_period} - drift WARN allowed")

        # Apply trend-aware logic for drift violations
        if self.trend_aware and is_drift_warn and not in_grace_period:
            if self.is_drift_improving():
                new_state = RiskState.WARN
                alerts.append(f"TREND_AWARE: Drift metrics improving - WARN maintained")

        # Apply regime-aware logic
        if self.regime_aware and regime in ['high_vol', 'extreme']:
            if is_drift_warn and not is_hard_risk:
                # In high volatility, be more tolerant of drift
                alerts.append(f"REGIME_AWARE: {regime.upper()} regime - drift tolerance increased")

        # Update consecutive counters
        if new_state == RiskState.WARN:
            self.consecutive_warns += 1
            self.consecutive_halts = 0
        elif new_state == RiskState.HALT:
            self.consecutive_halts += 1
            self.consecutive_warns = 0
        else:  # OK
            self.consecutive_warns = 0
            self.consecutive_halts = 0

        # Check for escalation (only for non-grace-period, non-improving drift)
        escalated = False
        if self.consecutive_warns >= self.max_consecutive_warns:
            # Don't escalate if in grace period
            if in_grace_period:
                alerts.append(f"ESCALATION_BLOCKED: In grace period ({self.rebalance_count}/{self.startup_grace_period})")
            # Don't escalate if improving
            elif self.trend_aware and self.is_drift_improving():
                alerts.append(f"ESCALATION_BLOCKED: Drift metrics improving")
            # Otherwise escalate
            else:
                new_state = RiskState.HALT
                alerts.append(f"ESCALATION: {self.consecutive_warns} consecutive WARNs -> HALT")
                escalated = True

        # Update state
        prev_state = self.current_state
        self.current_state = new_state

        # Record history
        state_entry = {
            'date': date,
            'timestamp': datetime.now().isoformat(),
            'prev_state': prev_state.value,
            'new_state': new_state.value,
            'alerts': alerts,
            'consecutive_warns': self.consecutive_warns,
            'consecutive_halts': self.consecutive_halts,
            'rebalance_count': self.rebalance_count,
            'in_grace_period': in_grace_period,
            'regime': regime,
            'escalated': escalated
        }

        self.state_history.append(state_entry)
        self.alert_history.extend(alerts)

        return state_entry

    def can_trade(self) -> bool:
        """Check if trading is allowed in current state"""
        # Check manual override
        if self.manual_override_file:
            import json
            from pathlib import Path
            override_file = Path(self.manual_override_file)
            if override_file.exists():
                with open(override_file, 'r') as f:
                    override_config = json.load(f)
                    if override_config.get('manual_override_enabled'):
                        print(f"⚠️  Manual override active: {override_config.get('override_reason')}")
                        return True

        return self.current_state != RiskState.HALT

    def get_state_summary(self) -> Dict:
        """Get state machine summary"""
        return {
            'current_state': self.current_state.value,
            'consecutive_warns': self.consecutive_warns,
            'consecutive_halts': self.consecutive_halts,
            'can_trade': self.can_trade(),
            'total_state_changes': len(self.state_history),
            'total_alerts': len(self.alert_history)
        }

    def print_state(self):
        """Print current state"""
        print(f"\n{'='*80}")
        print(f"【Risk State Machine Status】")
        print(f"{'='*80}\n")
        print(f"  Current state: {self.current_state.value}")
        print(f"  Consecutive WARNs: {self.consecutive_warns}/{self.max_consecutive_warns}")
        print(f"  Consecutive HALTs: {self.consecutive_halts}/{self.max_consecutive_halts}")
        print(f"  Can trade: {'YES ✅' if self.can_trade() else 'NO ❌'}")
        print()
