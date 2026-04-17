"""
Short Interest Features - V10.0
"""
import pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from alpha_factory.external_data_short_interest import ShortInterestDataProvider


def compute_short_interest_features(symbols):
    """计算 short interest 特征"""
    provider = ShortInterestDataProvider()
    si_df = provider.fetch_short_interest(symbols)

    # 特征工程
    si_df['short_float_rank'] = si_df['short_float'].rank(pct=True)
    si_df['days_to_cover_rank'] = si_df['days_to_cover'].rank(pct=True)
    si_df['utilization_rank'] = si_df['utilization_rate'].rank(pct=True)

    # 综合 short squeeze 风险分数
    si_df['short_squeeze_risk'] = (
        si_df['short_float_rank'] * 0.4 +
        si_df['days_to_cover_rank'] * 0.3 +
        si_df['utilization_rank'] * 0.3
    )

    return si_df


def merge_short_interest_to_features(feature_df, si_df):
    """合并到主特征集"""
    return feature_df.merge(
        si_df[['symbol', 'short_float', 'days_to_cover', 'utilization_rate', 'short_squeeze_risk']],
        on='symbol',
        how='left'
    )
