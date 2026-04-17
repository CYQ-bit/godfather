"""
Drift Monitor Module - Godfather V9.0 Phase PT.2
Monitor live performance vs backtest baseline with enhanced metrics
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from datetime import datetime


class DriftMonitor:
    """
    Monitor drift between live/paper trading and backtest baseline

    PT.2 Features:
    - Ex-first-turnover tracking
    - Sector exposure drift
    - Implementation shortfall drift
    - Portfolio return path drift
    - Cash/gross/net exposure drift
    - Holding count drift
    - Enhanced alert thresholds
    """

    def __init__(
        self,
        baseline_metrics: Dict,
        drift_threshold: float = 0.20,
        turnover_threshold_pct: float = 20.0
    ):
        """
        Initialize drift monitor

        Args:
            baseline_metrics: Baseline metrics from P.1.2/P.1.3
            drift_threshold: Threshold for drift alerts (default 20%)
            turnover_threshold_pct: Turnover drift threshold in percentage points (default 20)
        """
        self.baseline_metrics = baseline_metrics
        self.drift_threshold = drift_threshold
        self.turnover_threshold_pct = turnover_threshold_pct

        self.live_history = {
            'scores': [],
            'turnover': [],
            'costs': [],
            'returns': [],
            'sector_exposure': [],
            'implementation_shortfall': [],
            'holding_count': []
        }

        print(f"Initializing DriftMonitor (Godfather V9.0 - PT.2)...")
        print(f"  Drift threshold: {self.drift_threshold*100:.0f}%")
        print(f"  Turnover threshold: {self.turnover_threshold_pct} pct points")
        print(f"  Baseline Sharpe: {baseline_metrics.get('sharpe', 0):.4f}")
        print(f"  Baseline turnover: {baseline_metrics.get('avg_turnover', 0)*100:.1f}%")

    def check_score_drift(
        self,
        live_scores: pd.Series
    ) -> Dict:
        """
        Check if score distribution has drifted

        Args:
            live_scores: Live signal scores

        Returns:
            Dictionary with drift metrics
        """
        self.live_history['scores'].append({
            'timestamp': datetime.now(),
            'mean': live_scores.mean(),
            'std': live_scores.std(),
            'min': live_scores.min(),
            'max': live_scores.max()
        })

        baseline_mean = self.baseline_metrics.get('score_mean', 0)
        baseline_std = self.baseline_metrics.get('score_std', 1)

        live_mean = live_scores.mean()
        live_std = live_scores.std()

        mean_drift = abs(live_mean - baseline_mean) / abs(baseline_mean) if baseline_mean != 0 else 0
        std_drift = abs(live_std - baseline_std) / baseline_std if baseline_std != 0 else 0

        drift_detected = mean_drift > self.drift_threshold or std_drift > self.drift_threshold

        return {
            'drift_detected': drift_detected,
            'mean_drift': mean_drift,
            'std_drift': std_drift,
            'live_mean': live_mean,
            'live_std': live_std,
            'baseline_mean': baseline_mean,
            'baseline_std': baseline_std
        }

    def check_turnover_drift(
        self,
        live_turnover: float,
        is_first_rebalance: bool = False
    ) -> Dict:
        """
        Check if turnover has drifted (PT.2: ex-first-turnover)

        Args:
            live_turnover: Live turnover
            is_first_rebalance: Whether this is the first rebalance

        Returns:
            Dictionary with drift metrics
        """
        self.live_history['turnover'].append({
            'timestamp': datetime.now(),
            'turnover': live_turnover,
            'is_first': is_first_rebalance
        })

        # Calculate ex-first-turnover
        non_first_turnovers = [t['turnover'] for t in self.live_history['turnover'] if not t['is_first']]

        if len(non_first_turnovers) == 0:
            return {
                'drift_detected': False,
                'message': 'No non-first rebalances yet'
            }

        avg_ex_first_turnover = np.mean(non_first_turnovers)
        baseline_turnover = self.baseline_metrics.get('avg_turnover', 0)

        # Use absolute percentage point difference
        turnover_diff_pct = abs(avg_ex_first_turnover - baseline_turnover) * 100

        drift_detected = turnover_diff_pct > self.turnover_threshold_pct

        return {
            'drift_detected': drift_detected,
            'turnover_diff_pct': turnover_diff_pct,
            'avg_ex_first_turnover': avg_ex_first_turnover,
            'baseline_turnover': baseline_turnover,
            'num_rebalances': len(non_first_turnovers)
        }

    def check_sector_exposure_drift(
        self,
        live_sector_exposure: Dict,
        max_sector_limit: float = 0.30
    ) -> Dict:
        """
        Check sector exposure drift (PT.2)

        Args:
            live_sector_exposure: Live sector exposure dict
            max_sector_limit: Maximum allowed sector exposure

        Returns:
            Dictionary with drift metrics
        """
        self.live_history['sector_exposure'].append({
            'timestamp': datetime.now(),
            'exposure': live_sector_exposure.copy()
        })

        violations = []
        max_exposure = 0
        max_sector = None

        for sector, weight in live_sector_exposure.items():
            if weight > max_sector_limit:
                violations.append(f"{sector}: {weight*100:.1f}% > {max_sector_limit*100:.1f}%")
            if weight > max_exposure:
                max_exposure = weight
                max_sector = sector

        drift_detected = len(violations) > 0

        return {
            'drift_detected': drift_detected,
            'violations': violations,
            'max_sector': max_sector,
            'max_exposure': max_exposure,
            'num_sectors': len(live_sector_exposure)
        }

    def check_implementation_shortfall_drift(
        self,
        live_impl_shortfall_bps: float,
        threshold_bps: float = 500.0
    ) -> Dict:
        """
        Check implementation shortfall drift (PT.2)

        Args:
            live_impl_shortfall_bps: Live implementation shortfall in bps
            threshold_bps: Alert threshold

        Returns:
            Dictionary with drift metrics
        """
        self.live_history['implementation_shortfall'].append({
            'timestamp': datetime.now(),
            'impl_shortfall_bps': live_impl_shortfall_bps
        })

        drift_detected = abs(live_impl_shortfall_bps) > threshold_bps

        return {
            'drift_detected': drift_detected,
            'impl_shortfall_bps': live_impl_shortfall_bps,
            'threshold_bps': threshold_bps
        }

    def check_holding_count_drift(
        self,
        live_holding_count: int,
        target_count: int = 20
    ) -> Dict:
        """
        Check holding count drift (PT.2)

        Args:
            live_holding_count: Live number of holdings
            target_count: Target number of holdings

        Returns:
            Dictionary with drift metrics
        """
        self.live_history['holding_count'].append({
            'timestamp': datetime.now(),
            'count': live_holding_count
        })

        drift_detected = live_holding_count != target_count

        return {
            'drift_detected': drift_detected,
            'live_count': live_holding_count,
            'target_count': target_count,
            'diff': live_holding_count - target_count
        }

    def check_exposure_drift(
        self,
        cash: float,
        holdings_value: float,
        total_value: float,
        min_net_exposure: float = 0.90,
        max_net_exposure: float = 1.00
    ) -> Dict:
        """
        Check cash/exposure drift (PT.2)

        Args:
            cash: Current cash
            holdings_value: Current holdings value
            total_value: Total portfolio value
            min_net_exposure: Minimum net exposure
            max_net_exposure: Maximum net exposure

        Returns:
            Dictionary with drift metrics
        """
        net_exposure = holdings_value / total_value if total_value > 0 else 0
        cash_pct = cash / total_value if total_value > 0 else 0

        violations = []
        if net_exposure < min_net_exposure:
            violations.append(f"Net exposure {net_exposure*100:.1f}% < {min_net_exposure*100:.1f}%")
        if net_exposure > max_net_exposure:
            violations.append(f"Net exposure {net_exposure*100:.1f}% > {max_net_exposure*100:.1f}%")
        if cash < 0:
            violations.append(f"Negative cash: ${cash:,.2f}")

        drift_detected = len(violations) > 0

        return {
            'drift_detected': drift_detected,
            'violations': violations,
            'net_exposure': net_exposure,
            'cash_pct': cash_pct,
            'cash': cash
        }

    def check_cost_drift(
        self,
        live_cost_pct: float
    ) -> Dict:
        """
        Check if transaction costs have drifted

        Args:
            live_cost_pct: Live cost as % of capital

        Returns:
            Dictionary with drift metrics
        """
        self.live_history['costs'].append({
            'timestamp': datetime.now(),
            'cost_pct': live_cost_pct
        })

        baseline_cost = self.baseline_metrics.get('avg_cost_pct', 0)
        cost_drift = abs(live_cost_pct - baseline_cost) / baseline_cost if baseline_cost != 0 else 0

        drift_detected = cost_drift > self.drift_threshold

        return {
            'drift_detected': drift_detected,
            'cost_drift': cost_drift,
            'live_cost_pct': live_cost_pct,
            'baseline_cost_pct': baseline_cost
        }

    def check_performance_drift(
        self,
        live_returns: pd.Series
    ) -> Dict:
        """
        Check if performance metrics have drifted

        Args:
            live_returns: Live daily returns

        Returns:
            Dictionary with drift metrics
        """
        if len(live_returns) < 20:
            return {
                'drift_detected': False,
                'message': 'Insufficient data for performance drift check'
            }

        # Calculate live metrics
        live_sharpe = (live_returns.mean() / live_returns.std() * np.sqrt(252)) if live_returns.std() > 0 else 0

        cumulative = (1 + live_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        live_max_dd = drawdown.min()

        baseline_sharpe = self.baseline_metrics.get('sharpe', 0)
        baseline_max_dd = self.baseline_metrics.get('max_drawdown', 0)

        sharpe_drift = abs(live_sharpe - baseline_sharpe) / abs(baseline_sharpe) if baseline_sharpe != 0 else 0
        dd_drift = abs(live_max_dd - baseline_max_dd) / abs(baseline_max_dd) if baseline_max_dd != 0 else 0

        drift_detected = sharpe_drift > self.drift_threshold or dd_drift > self.drift_threshold

        return {
            'drift_detected': drift_detected,
            'sharpe_drift': sharpe_drift,
            'dd_drift': dd_drift,
            'live_sharpe': live_sharpe,
            'live_max_dd': live_max_dd,
            'baseline_sharpe': baseline_sharpe,
            'baseline_max_dd': baseline_max_dd
        }

    def run_all_drift_checks(
        self,
        live_scores: Optional[pd.Series] = None,
        live_turnover: Optional[float] = None,
        is_first_rebalance: bool = False,
        live_cost_pct: Optional[float] = None,
        live_returns: Optional[pd.Series] = None,
        sector_exposure: Optional[Dict] = None,
        impl_shortfall_bps: Optional[float] = None,
        holding_count: Optional[int] = None,
        cash: Optional[float] = None,
        holdings_value: Optional[float] = None,
        total_value: Optional[float] = None
    ) -> Dict:
        """
        Run all drift checks (PT.2 enhanced)

        Returns:
            Dictionary with all drift results
        """
        print(f"\n{'='*80}")
        print(f"【Running Drift Checks - PT.2】")
        print(f"{'='*80}\n")

        results = {
            'timestamp': datetime.now().isoformat(),
            'checks': {},
            'drift_detected': False,
            'drift_status': 'OK'
        }

        # Score drift
        if live_scores is not None:
            score_drift = self.check_score_drift(live_scores)
            results['checks']['score'] = score_drift
            if score_drift['drift_detected']:
                results['drift_detected'] = True
                results['drift_status'] = 'WARN'
                print(f"⚠️  Score drift detected: mean {score_drift['mean_drift']*100:.1f}%, std {score_drift['std_drift']*100:.1f}%")

        # Turnover drift (ex-first)
        if live_turnover is not None:
            turnover_drift = self.check_turnover_drift(live_turnover, is_first_rebalance)
            results['checks']['turnover'] = turnover_drift
            if turnover_drift.get('drift_detected', False):
                results['drift_detected'] = True
                results['drift_status'] = 'WARN'
                print(f"⚠️  Turnover drift: {turnover_drift.get('turnover_diff_pct', 0):.1f} pct points from baseline")

        # Sector exposure drift
        if sector_exposure is not None:
            sector_drift = self.check_sector_exposure_drift(sector_exposure)
            results['checks']['sector_exposure'] = sector_drift
            if sector_drift['drift_detected']:
                results['drift_detected'] = True
                results['drift_status'] = 'WARN'
                print(f"⚠️  Sector exposure drift:")
                for v in sector_drift['violations']:
                    print(f"     {v}")

        # Implementation shortfall drift
        if impl_shortfall_bps is not None:
            impl_drift = self.check_implementation_shortfall_drift(impl_shortfall_bps)
            results['checks']['implementation_shortfall'] = impl_drift
            if impl_drift['drift_detected']:
                results['drift_detected'] = True
                results['drift_status'] = 'WARN'
                print(f"⚠️  Implementation shortfall: {impl_shortfall_bps:.1f} bps")

        # Holding count drift
        if holding_count is not None:
            holding_drift = self.check_holding_count_drift(holding_count)
            results['checks']['holding_count'] = holding_drift
            if holding_drift['drift_detected']:
                results['drift_detected'] = True
                results['drift_status'] = 'WARN'
                print(f"⚠️  Holding count: {holding_count} vs target {holding_drift['target_count']}")

        # Exposure drift
        if cash is not None and holdings_value is not None and total_value is not None:
            exposure_drift = self.check_exposure_drift(cash, holdings_value, total_value)
            results['checks']['exposure'] = exposure_drift
            if exposure_drift['drift_detected']:
                results['drift_detected'] = True
                results['drift_status'] = 'WARN'
                print(f"⚠️  Exposure drift:")
                for v in exposure_drift['violations']:
                    print(f"     {v}")

        # Cost drift
        if live_cost_pct is not None:
            cost_drift = self.check_cost_drift(live_cost_pct)
            results['checks']['cost'] = cost_drift
            if cost_drift['drift_detected']:
                results['drift_detected'] = True
                results['drift_status'] = 'WARN'
                print(f"⚠️  Cost drift: {cost_drift['cost_drift']*100:.1f}%")

        # Performance drift
        if live_returns is not None:
            perf_drift = self.check_performance_drift(live_returns)
            results['checks']['performance'] = perf_drift
            if perf_drift.get('drift_detected', False):
                results['drift_detected'] = True
                results['drift_status'] = 'WARN'
                print(f"⚠️  Performance drift: Sharpe {perf_drift['sharpe_drift']*100:.1f}%, DD {perf_drift['dd_drift']*100:.1f}%")

        if not results['drift_detected']:
            print(f"✅ No significant drift detected")

        return results

    def get_drift_summary(self) -> Dict:
        """
        Get summary of drift monitoring history

        Returns:
            Dictionary with drift history summary
        """
        return {
            'num_score_checks': len(self.live_history['scores']),
            'num_turnover_checks': len(self.live_history['turnover']),
            'num_cost_checks': len(self.live_history['costs']),
            'num_return_checks': len(self.live_history['returns']),
            'drift_threshold': self.drift_threshold
        }
