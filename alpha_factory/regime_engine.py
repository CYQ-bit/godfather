"""
Regime Engine v1 - V10.0
3-state vol regime 分类器
"""
import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
from alpha_factory.regime_features import compute_regime_features
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))


class RegimeEngine:
    """市场状态引擎"""

    STATES = {
        0: 'low_vol_trending',
        1: 'normal',
        2: 'high_vol_stress'
    }

    def __init__(self):
        self.state_history = []
        self.data_dir = (_REPO_ROOT / 'data/ai_engine')
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def classify_regime(self, features_row):
        """分类当前 regime"""
        vix_21d = features_row['vix_21d_mean']
        vix_5d_chg = features_row['vix_5d_change']
        vol_ratio = features_row['spy_vol_ratio']

        # 简单规则分类
        if vix_21d > 25 or vix_5d_chg > 5 or vol_ratio > 1.3:
            return 2  # high_vol_stress
        elif vix_21d < 15 and vol_ratio < 0.9:
            return 0  # low_vol_trending
        else:
            return 1  # normal

    def get_regime_adjustments(self, state):
        """获取 regime 对应的调节参数"""
        if state == 2:  # high_vol_stress
            return {
                'budget_multiplier': 0.5,
                'hold_buffer': 0.70
            }
        elif state == 0:  # low_vol_trending
            return {
                'budget_multiplier': 1.0,
                'hold_buffer': 0.50
            }
        else:  # normal
            return {
                'budget_multiplier': 1.0,
                'hold_buffer': 0.50
            }

    def run(self):
        """运行 regime 分类"""
        features_df = compute_regime_features()
        latest = features_df.iloc[-1]

        state = self.classify_regime(latest)
        state_name = self.STATES[state]
        adjustments = self.get_regime_adjustments(state)

        result = {
            'date': str(latest['date']),
            'state': state,
            'state_name': state_name,
            'budget_multiplier': adjustments['budget_multiplier'],
            'hold_buffer': adjustments['hold_buffer'],
            'features': {
                'vix_21d_mean': float(latest['vix_21d_mean']),
                'vix_5d_change': float(latest['vix_5d_change']),
                'spy_vol_ratio': float(latest['spy_vol_ratio'])
            },
            'timestamp': datetime.now().isoformat()
        }

        # 保存状态
        state_file = self.data_dir / 'daily_regime_state.json'
        with open(state_file, 'w') as f:
            json.dump(result, f, indent=2)

        # 追加历史
        history_file = self.data_dir / 'regime_history.csv'
        history_row = pd.DataFrame([{
            'date': result['date'],
            'state': state,
            'state_name': state_name,
            'budget_multiplier': adjustments['budget_multiplier'],
            'hold_buffer': adjustments['hold_buffer']
        }])

        if history_file.exists():
            history_df = pd.read_csv(history_file)
            history_df = pd.concat([history_df, history_row], ignore_index=True)
        else:
            history_df = history_row

        history_df.to_csv(history_file, index=False)

        return result


def load_regime_state():
    """加载最新 regime 状态"""
    state_file = (_REPO_ROOT / 'data/ai_engine/daily_regime_state.json')
    if state_file.exists():
        with open(state_file, 'r') as f:
            return json.load(f)
    return None
