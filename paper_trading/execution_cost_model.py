"""
Execution Cost Model - V9.9a (Dynamic)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class ExecutionCostModel:
    """执行成本模型 - 动态版本"""

    def __init__(self, regime_state='normal'):
        self.regime_state = regime_state

    def estimate_cost_breakdown(self, notional, shares, vol_20d=0.02):
        """估算执行成本明细 (bps)"""
        # Commission: $0.005/股，最低 $1/单
        commission_usd = max(1.0, shares * 0.005)
        commission_bps = (commission_usd / notional * 10000) if notional > 0 else 0

        # Spread proxy: max(3, min(20, vol_20d * 100 * 0.4))
        spread_bps = max(3, min(20, vol_20d * 100 * 0.4))

        # Overnight gap buffer: vol_20d / sqrt(252) * 0.6 * 10000
        overnight_gap_bps = vol_20d / (252 ** 0.5) * 0.6 * 10000

        # Preview→submit delay buffer
        delay_buffer_bps = 15.0

        # Impact (placeholder)
        impact_bps = 0.0

        total_bps = commission_bps + spread_bps + overnight_gap_bps + delay_buffer_bps + impact_bps

        return {
            'commission_bps': commission_bps,
            'spread_bps': spread_bps,
            'overnight_gap_bps': overnight_gap_bps,
            'delay_buffer_bps': delay_buffer_bps,
            'impact_bps': impact_bps,
            'total_bps': total_bps
        }

    def estimate_cost(self, notional, shares=100, vol_20d=0.02):
        """估算总成本 (bps)"""
        breakdown = self.estimate_cost_breakdown(notional, shares, vol_20d)
        return breakdown['total_bps']

    def get_min_alpha_threshold(self):
        """获取最小 alpha 阈值 (bps) - 校准版"""
        thresholds = {
            'low_vol_trending': 20,
            'normal': 35,
            'high_vol_stress': 55
        }
        return thresholds.get(self.regime_state, 35)

    def compute_net_alpha(self, expected_alpha_bps, notional, shares=100, vol_20d=0.02):
        """计算净 alpha"""
        cost_bps = self.estimate_cost(notional, shares, vol_20d)
        return expected_alpha_bps - cost_bps

    def should_trade(self, expected_alpha_bps, notional, shares=100, vol_20d=0.02):
        """判断是否应该交易"""
        net_alpha = self.compute_net_alpha(expected_alpha_bps, notional, shares, vol_20d)
        threshold = self.get_min_alpha_threshold()
        return net_alpha > threshold
