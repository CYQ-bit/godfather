"""
Regime Features - V10.0
计算市场状态特征
"""
import pandas as pd
import numpy as np
from pathlib import Path
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))


def fetch_vix_data():
    """获取 VIX 数据（简化版，实际需要接入数据源）"""
    # TODO: 接入真实 VIX 数据源
    return pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=500),
        'vix': np.random.uniform(12, 35, 500)
    })


def fetch_spy_data():
    """获取 SPY 数据"""
    price_dir = (_REPO_ROOT / 'data/price_lake')
    spy_file = price_dir / 'SPY.parquet'

    if spy_file.exists():
        df = pd.read_parquet(spy_file)
        return df[['date', 'close']].rename(columns={'close': 'spy_close'})

    # Fallback
    return pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=500),
        'spy_close': np.random.uniform(400, 500, 500)
    })


def compute_regime_features():
    """计算 5 个 regime 特征"""
    vix_df = fetch_vix_data()
    spy_df = fetch_spy_data()

    df = pd.merge(vix_df, spy_df, on='date', how='inner').sort_values('date')

    # 1. VIX_21d_mean
    df['vix_21d_mean'] = df['vix'].rolling(21).mean()

    # 2. VIX_5d_change
    df['vix_5d_change'] = df['vix'] - df['vix'].shift(5)

    # 3. SPY realized vol ratio
    df['spy_ret'] = df['spy_close'].pct_change()
    df['spy_vol_21d'] = df['spy_ret'].rolling(21).std() * np.sqrt(252)
    df['spy_vol_63d'] = df['spy_ret'].rolling(63).std() * np.sqrt(252)
    df['spy_vol_ratio'] = df['spy_vol_21d'] / df['spy_vol_63d']

    # 4. Portfolio beta (简化版，实际需要持仓数据)
    df['portfolio_beta_20d'] = 1.0  # TODO: 计算真实 beta

    # 5. Cross-section dispersion (简化版)
    df['cross_section_dispersion'] = 0.15  # TODO: 计算真实 dispersion

    return df[[
        'date', 'vix_21d_mean', 'vix_5d_change', 'spy_vol_ratio',
        'portfolio_beta_20d', 'cross_section_dispersion'
    ]].dropna()
