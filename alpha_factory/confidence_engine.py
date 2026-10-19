"""
Confidence Engine v1 - V10.0
基于 main_predictions_v10.parquet（当日模型预测）构建置信度层
"""
import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))


class ConfidenceEngine:
    """置信度引擎"""

    def __init__(self):
        self.pred_file = (_REPO_ROOT / 'data/ml2_results/main_predictions_v10.parquet')
        self.data_dir = (_REPO_ROOT / 'data/ai_engine')
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def compute_confidence(self, pred_df):
        """计算置信度分数"""
        # 按 symbol 分组计算 std
        conf_df = pred_df.groupby('symbol')['y_pred'].agg(['std', 'count']).reset_index()
        conf_df = conf_df[conf_df['count'] >= 2]  # 至少2个窗口

        if len(conf_df) == 0:
            # Fallback: 使用 y_pred 绝对值作为置信度代理
            conf_df = pred_df.groupby('symbol')['y_pred'].mean().abs().reset_index()
            conf_df.columns = ['symbol', 'confidence_score']
        else:
            conf_df['confidence_score'] = 1 / (conf_df['std'] + 1e-6)
            conf_df = conf_df[['symbol', 'confidence_score']]

        # 归一化到 [0, 1]
        min_conf = conf_df['confidence_score'].quantile(0.01)
        max_conf = conf_df['confidence_score'].quantile(0.99)
        conf_df['confidence_norm'] = (conf_df['confidence_score'] - min_conf) / (max_conf - min_conf + 1e-9)
        conf_df['confidence_norm'] = conf_df['confidence_norm'].clip(0, 1)

        # 分桶
        conf_df['confidence_bucket'] = pd.cut(
            conf_df['confidence_norm'],
            bins=[0, 0.33, 0.67, 1.0],
            labels=['low', 'mid', 'high'],
            include_lowest=True,
        )

        return conf_df

    def get_confidence_multiplier(self, bucket):
        """获取置信度权重乘数"""
        multipliers = {'high': 1.3, 'mid': 1.0, 'low': 0.6}
        return multipliers.get(bucket, 1.0)

    def run(self):
        """运行置信度计算"""
        pred_df = pd.read_parquet(self.pred_file)
        pred_df = self.compute_confidence(pred_df)

        # 统计
        bucket_counts = pred_df['confidence_bucket'].value_counts().to_dict()
        avg_conf = float(pred_df['confidence_norm'].mean())

        result = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'avg_confidence': avg_conf,
            'high_conf_count': int(bucket_counts.get('high', 0)),
            'mid_conf_count': int(bucket_counts.get('mid', 0)),
            'low_conf_count': int(bucket_counts.get('low', 0)),
            'timestamp': datetime.now().isoformat()
        }

        # 保存快照
        snapshot_file = self.data_dir / 'latest_confidence_snapshot.json'
        with open(snapshot_file, 'w') as f:
            json.dump(result, f, indent=2)

        # 保存详细数据
        pred_df[['symbol', 'confidence_score', 'confidence_norm', 'confidence_bucket']].to_csv(
            self.data_dir / 'confidence_history.csv', index=False
        )

        return result, pred_df


def load_confidence_snapshot():
    """加载最新置信度快照"""
    snapshot_file = (_REPO_ROOT / 'data/ai_engine/latest_confidence_snapshot.json')
    if snapshot_file.exists():
        with open(snapshot_file, 'r') as f:
            return json.load(f)
    return None
