"""
Position Sizing V10 - Regime + Confidence 联动
"""
import pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from alpha_factory.regime_engine import load_regime_state
from alpha_factory.confidence_engine import ConfidenceEngine


def apply_v10_adjustments(target_weights_df, regime=None, conf_df=None):
    """应用 V10 调节：regime + confidence (真实生效版)"""

    # 加载 regime 状态
    if regime is None:
        regime = load_regime_state()

    if regime is None:
        regime_mult = 1.0
        hold_buffer = 0.50
        regime_state = 'unknown'
    else:
        regime_mult = regime['budget_multiplier']
        hold_buffer = regime['hold_buffer']
        regime_state = regime['state_name']

    # 加载 confidence
    if conf_df is None:
        engine = ConfidenceEngine()
        _, conf_df = engine.run()

    # Merge
    result_df = target_weights_df.merge(
        conf_df[['symbol', 'confidence_bucket', 'confidence_score']],
        left_on='stock_code',
        right_on='symbol',
        how='left'
    )

    # Drop duplicate symbol column from merge, keep stock_code
    if 'symbol' in result_df.columns and 'stock_code' in result_df.columns:
        result_df = result_df.drop(columns=['symbol'])

    # 应用 confidence multiplier
    result_df['confidence_multiplier'] = result_df['confidence_bucket'].astype(str).map({
        'high': 1.3, 'mid': 1.0, 'low': 0.6
    }).fillna(1.0).astype(float)

    # 应用调节 (真实生效)
    result_df['weight_v10'] = (
        result_df['target_weight'].astype(float) *
        result_df['confidence_multiplier'] *
        float(regime_mult)
    )

    # 归一化
    total = result_df['weight_v10'].sum()
    if total > 0:
        result_df['weight_v10'] = result_df['weight_v10'] / total

    result_df['regime_state'] = regime_state
    result_df['regime_mult'] = regime_mult
    result_df['hold_buffer'] = hold_buffer

    return result_df


def build_v10_orders(target_weights_df, current_positions, capital):
    """构建 V10 订单"""
    adjusted_df = apply_v10_adjustments(target_weights_df)

    # 简化订单逻辑
    orders = []
    for _, row in adjusted_df.iterrows():
        target_value = row['weight_v10'] * capital
        current_value = current_positions.get(row['symbol'], 0)
        delta = target_value - current_value

        if abs(delta) > 100:  # 最小交易阈值
            orders.append({
                'symbol': row['symbol'],
                'target_weight': row['weight_v10'],
                'delta_value': delta,
                'confidence_bucket': row['confidence_bucket'],
                'regime_state': row['regime_state']
            })

    return orders, adjusted_df
