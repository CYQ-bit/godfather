"""
Regime Classifier - Godfather V9.0 Phase PT.2.3
Classify market regime for adaptive risk thresholds with stress period detection
"""
import numpy as np
from typing import Dict, List
from enum import Enum
from datetime import datetime


class MarketRegime(Enum):
    """Market regime types"""
    NORMAL = "normal"
    HIGH_VOL = "high_vol"
    EXTREME = "extreme"
    STRESS = "stress"  # PT.2.3: Known stress periods (e.g., COVID March-May 2020)


class RegimeClassifier:
    """
    Classify market regime based on market conditions

    PT.2.3: Adaptive thresholds with stress period detection
    """

    def __init__(self):
        self.regime_history = []

        # PT.2.3: Known stress periods
        self.stress_periods = [
            ('2020-03-01', '2020-05-31', 'COVID-19 Initial Shock')
        ]

        print(f"Initializing RegimeClassifier (Godfather V9.0 - PT.2.3)...")
        print(f"  Regimes: NORMAL / HIGH_VOL / EXTREME / STRESS")
        print(f"  Stress periods: {len(self.stress_periods)}")

    def classify_regime(
        self,
        signal_date: str,
        market_move_abs_bps: float,
        impl_shortfall_abs_bps: float,
        turnover: float,
        baseline_turnover: float = 0.4014
    ) -> MarketRegime:
        """
        Classify current market regime

        Args:
            signal_date: Signal date (YYYY-MM-DD)
            market_move_abs_bps: Absolute market move in bps
            impl_shortfall_abs_bps: Absolute implementation shortfall in bps
            turnover: Current turnover
            baseline_turnover: Baseline turnover

        Returns:
            MarketRegime
        """
        # PT.2.3: Check if in known stress period first
        for start_date, end_date, reason in self.stress_periods:
            if start_date <= signal_date <= end_date:
                regime = MarketRegime.STRESS
                self.regime_history.append({
                    'regime': regime.value,
                    'score': 999,  # Special marker for stress
                    'reason': reason,
                    'market_move_abs_bps': market_move_abs_bps,
                    'impl_shortfall_abs_bps': impl_shortfall_abs_bps,
                    'turnover': turnover,
                    'signal_date': signal_date
                })
                return regime

        # Scoring system for non-stress periods
        score = 0

        # Market move scoring
        if market_move_abs_bps > 800:  # Extreme
            score += 3
        elif market_move_abs_bps > 500:  # High
            score += 2
        elif market_move_abs_bps > 300:  # Elevated
            score += 1

        # Implementation shortfall scoring
        if impl_shortfall_abs_bps > 1000:  # Extreme
            score += 3
        elif impl_shortfall_abs_bps > 700:  # High
            score += 2
        elif impl_shortfall_abs_bps > 400:  # Elevated
            score += 1

        # Turnover deviation scoring
        turnover_deviation = abs(turnover - baseline_turnover)
        if turnover_deviation > 0.40:  # 40 pct points
            score += 2
        elif turnover_deviation > 0.25:  # 25 pct points
            score += 1

        # Classify regime
        if score >= 6:
            regime = MarketRegime.EXTREME
        elif score >= 3:
            regime = MarketRegime.HIGH_VOL
        else:
            regime = MarketRegime.NORMAL

        self.regime_history.append({
            'regime': regime.value,
            'score': score,
            'reason': 'Market-based classification',
            'market_move_abs_bps': market_move_abs_bps,
            'impl_shortfall_abs_bps': impl_shortfall_abs_bps,
            'turnover': turnover,
            'signal_date': signal_date
        })

        return regime

    def get_regime_thresholds(self, regime: MarketRegime) -> Dict:
        """
        Get risk thresholds for given regime

        Args:
            regime: Market regime

        Returns:
            Dictionary of thresholds
        """
        if regime == MarketRegime.NORMAL:
            return {
                'max_impl_shortfall_bps': 500.0,
                'max_turnover_deviation_pct': 20.0,
                'max_consecutive_warns': 3,
                'max_consecutive_drift_warns': 3
            }
        elif regime == MarketRegime.HIGH_VOL:
            return {
                'max_impl_shortfall_bps': 800.0,
                'max_turnover_deviation_pct': 30.0,
                'max_consecutive_warns': 4,
                'max_consecutive_drift_warns': 4
            }
        elif regime == MarketRegime.STRESS:
            # PT.2.3: Stress regime - observation only, elevated thresholds
            return {
                'max_impl_shortfall_bps': 1500.0,
                'max_turnover_deviation_pct': 50.0,
                'max_consecutive_warns': 999,  # Effectively disabled
                'max_consecutive_drift_warns': 999,  # Effectively disabled
                'observation_only': True
            }
        else:  # EXTREME
            return {
                'max_impl_shortfall_bps': 1200.0,
                'max_turnover_deviation_pct': 40.0,
                'max_consecutive_warns': 5,
                'max_consecutive_drift_warns': 5
            }

    def should_enter_observation_mode(self, regime: MarketRegime) -> bool:
        """Check if should enter observation-only mode"""
        return regime in [MarketRegime.EXTREME, MarketRegime.STRESS]

    def get_regime_summary(self) -> Dict:
        """Get regime history summary"""
        if len(self.regime_history) == 0:
            return {'total': 0}

        regime_counts = {}
        for entry in self.regime_history:
            regime = entry['regime']
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

        return {
            'total': len(self.regime_history),
            'counts': regime_counts,
            'latest': self.regime_history[-1]['regime'] if len(self.regime_history) > 0 else None
        }
