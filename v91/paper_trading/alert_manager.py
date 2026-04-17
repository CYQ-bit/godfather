"""
Alert Enhancement - Godfather V9.0 Phase PT.2.3
Enhanced alerting with regime-aware escalation rules
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List


class AlertManager:
    """Enhanced alert management with regime-aware escalation"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.alerts_dir = self.output_dir / 'alerts'
        self.alerts_dir.mkdir(parents=True, exist_ok=True)

        self.alert_history = []
        self.consecutive_drift_warns = 0
        self.consecutive_impl_increases = 0
        self.consecutive_risk_warns = 0

        self.impl_shortfall_history = []

        print(f"Initializing AlertManager (Godfather V9.0 - PT.2.3)...")
        print(f"  Output directory: {self.alerts_dir}")
        print(f"  Regime-aware alerting: ON")

    def check_alerts(
        self,
        date: str,
        risk_results: Dict,
        drift_results: Dict,
        execution_summary: Dict,
        portfolio_summary: Dict,
        regime: str = 'normal'
    ) -> List[Dict]:
        """
        Check for alert conditions with regime awareness

        Args:
            date: Current date
            risk_results: Risk check results
            drift_results: Drift check results
            execution_summary: Execution summary
            portfolio_summary: Portfolio summary
            regime: Market regime (normal/high_vol/extreme/stress)

        Returns:
            List of alerts
        """
        alerts = []

        # Check drift WARN escalation
        if drift_results.get('drift_detected', False):
            self.consecutive_drift_warns += 1
            if self.consecutive_drift_warns >= 3:
                alerts.append({
                    'type': 'DRIFT_ESCALATION',
                    'severity': 'HIGH' if regime != 'stress' else 'MEDIUM',
                    'regime': regime,
                    'message': f'Consecutive drift WARNs: {self.consecutive_drift_warns}',
                    'date': date,
                    'action_taken': 'Observation only' if regime == 'stress' else 'Monitor closely'
                })
        else:
            self.consecutive_drift_warns = 0

        # Check implementation shortfall escalation
        impl_shortfall = execution_summary.get('implementation_shortfall_abs_mean_bps', 0)
        if impl_shortfall > 0:
            self.impl_shortfall_history.append(impl_shortfall)

            if len(self.impl_shortfall_history) >= 3:
                recent = self.impl_shortfall_history[-3:]
                if all(recent[i] > recent[i-1] for i in range(1, len(recent))):
                    self.consecutive_impl_increases += 1
                    if self.consecutive_impl_increases >= 2:
                        alerts.append({
                            'type': 'IMPL_SHORTFALL_ESCALATION',
                            'severity': 'MEDIUM' if regime != 'stress' else 'LOW',
                            'regime': regime,
                            'message': f'Implementation shortfall increasing: {recent[-3]:.1f} -> {recent[-2]:.1f} -> {recent[-1]:.1f} bps',
                            'date': date,
                            'action_taken': 'Expected in stress regime' if regime == 'stress' else 'Monitor execution'
                        })
                else:
                    self.consecutive_impl_increases = 0

        # Check turnover deviation
        if portfolio_summary.get('status') != 'No rebalance':
            turnover = portfolio_summary.get('expected_turnover', 0)
            baseline = 0.4014
            deviation = abs(turnover - baseline)

            if deviation > 0.30:  # 30 pct points
                alerts.append({
                    'type': 'TURNOVER_DEVIATION',
                    'severity': 'MEDIUM',
                    'message': f'Turnover deviation: {turnover*100:.1f}% vs baseline {baseline*100:.1f}% (deviation: {deviation*100:.1f} pct points)',
                    'date': date
                })

        # Check risk WARN escalation
        if risk_results.get('overall_status') == 'WARN':
            self.consecutive_risk_warns += 1
            if self.consecutive_risk_warns >= 2:
                alerts.append({
                    'type': 'RISK_ESCALATION',
                    'severity': 'HIGH',
                    'message': f'Consecutive risk WARNs: {self.consecutive_risk_warns}',
                    'date': date
                })
        else:
            self.consecutive_risk_warns = 0

        # Check HALT
        if risk_results.get('overall_status') == 'HALT':
            alerts.append({
                'type': 'HALT_TRIGGERED',
                'severity': 'CRITICAL',
                'message': 'Risk HALT triggered',
                'date': date
            })

            # Write incident file
            self._write_incident(date, risk_results)

        # Save alerts
        for alert in alerts:
            self.alert_history.append(alert)
            self._write_alert(alert)

        return alerts

    def _write_alert(self, alert: Dict):
        """Write alert to file"""
        alert_file = self.alerts_dir / f"{alert['date']}_{alert['type']}.json"
        with open(alert_file, 'w') as f:
            json.dump(alert, f, indent=2)

    def _write_incident(self, date: str, risk_results: Dict):
        """Write incident file for HALT"""
        incident = {
            'timestamp': datetime.now().isoformat(),
            'date': date,
            'type': 'HALT',
            'risk_results': risk_results
        }

        incident_file = self.alerts_dir / f"INCIDENT_{date}_HALT.json"
        with open(incident_file, 'w') as f:
            json.dump(incident, f, indent=2)

        print(f"🚨 INCIDENT FILE CREATED: {incident_file}")

    def get_alert_summary(self) -> Dict:
        """Get alert summary"""
        if len(self.alert_history) == 0:
            return {'total': 0}

        by_type = {}
        by_severity = {}

        for alert in self.alert_history:
            alert_type = alert['type']
            severity = alert['severity']

            by_type[alert_type] = by_type.get(alert_type, 0) + 1
            by_severity[severity] = by_severity.get(severity, 0) + 1

        return {
            'total': len(self.alert_history),
            'by_type': by_type,
            'by_severity': by_severity
        }

    def print_alert_summary(self):
        """Print alert summary"""
        summary = self.get_alert_summary()

        if summary['total'] == 0:
            print("✅ No alerts triggered")
            return

        print(f"\n{'='*80}")
        print(f"【Alert Summary】")
        print(f"{'='*80}\n")
        print(f"  Total alerts: {summary['total']}")
        print()

        if 'by_severity' in summary:
            print(f"  By severity:")
            for severity, count in summary['by_severity'].items():
                print(f"    {severity}: {count}")
            print()

        if 'by_type' in summary:
            print(f"  By type:")
            for alert_type, count in summary['by_type'].items():
                print(f"    {alert_type}: {count}")
            print()
