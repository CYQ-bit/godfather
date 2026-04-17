"""
Short Interest External Data - V10.0
接入外部数据源（第一版：模拟数据）
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))


class ShortInterestDataProvider:
    """Short Interest 数据提供者"""

    def __init__(self):
        self.data_dir = (_REPO_ROOT / 'data/external/short_interest')
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def fetch_short_interest(self, symbols):
        """获取 short interest 数据（模拟）"""
        # TODO: 接入真实数据源 (Finviz/FINRA/etc)
        data = []
        for symbol in symbols:
            data.append({
                'symbol': symbol,
                'short_float': np.random.uniform(1, 20),
                'days_to_cover': np.random.uniform(0.5, 10),
                'utilization_rate': np.random.uniform(10, 90),
                'date': datetime.now().strftime('%Y-%m-%d')
            })

        df = pd.DataFrame(data)

        # 保存
        output_file = self.data_dir / f'short_interest_{datetime.now().strftime("%Y%m%d")}.parquet'
        df.to_parquet(output_file, index=False)

        return df

    def load_latest(self):
        """加载最新数据"""
        files = sorted(self.data_dir.glob('short_interest_*.parquet'))
        if files:
            return pd.read_parquet(files[-1])
        return None
