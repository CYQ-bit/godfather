"""
Walk-forward Trainer - Phase ML.1

严格滚动训练器 - 防泄漏
关键要求：
1. 严格按时间滚动，不允许shuffle
2. 每个测试窗只使用训练窗选出的特征
3. 不使用未来窗做早停
4. 保存每个窗口的OOS预测结果
"""

import polars as pl
import pandas as pd
import numpy as np
from typing import List, Tuple, Dict
from datetime import datetime, timedelta
import xgboost as xgb
from pathlib import Path
import pickle


class WalkForwardTrainer:
    def __init__(self, train_months=24, test_months=2, step_months=2, max_windows=None):
        """
        初始化Walk-forward训练器

        Args:
            train_months: 训练窗口月数
            test_months: 测试窗口月数
            step_months: 滚动步长月数
            max_windows: 最大窗口数（用于快速测试）
        """
        self.train_months = train_months
        self.test_months = test_months
        self.step_months = step_months
        self.max_windows = max_windows

        # XGBoost默认参数（稳健配置）
        self.xgb_params = {
            'objective': 'reg:squarederror',
            'max_depth': 3,
            'learning_rate': 0.05,
            'n_estimators': 100,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'random_state': 42,
            'n_jobs': -1
        }

    def generate_windows(self, feature_df: pl.DataFrame) -> List[Tuple[datetime, datetime, datetime, datetime]]:
        """
        生成walk-forward窗口

        Args:
            feature_df: 特征DataFrame

        Returns:
            windows: [(train_start, train_end, test_start, test_end), ...]
        """
        # 获取时间范围
        min_date = feature_df.select(pl.col('timestamp').min()).item()
        max_date = feature_df.select(pl.col('timestamp').max()).item()

        print(f"\n📅 生成Walk-forward窗口...")
        print(f"  数据时间范围: {min_date} 至 {max_date}")
        print(f"  训练窗口: {self.train_months} 个月")
        print(f"  测试窗口: {self.test_months} 个月")
        print(f"  滚动步长: {self.step_months} 个月")

        windows = []
        current_train_start = min_date

        while True:
            # 计算训练窗口结束时间
            train_end = current_train_start + timedelta(days=self.train_months * 30)

            # 计算测试窗口
            test_start = train_end
            test_end = test_start + timedelta(days=self.test_months * 30)

            # 检查是否超出数据范围
            if test_end > max_date:
                break

            windows.append((current_train_start, train_end, test_start, test_end))

            # 滚动到下一个窗口
            current_train_start = current_train_start + timedelta(days=self.step_months * 30)

        print(f"  ✅ 生成 {len(windows)} 个窗口")

        # 限制窗口数量（用于快速测试）
        if self.max_windows and len(windows) > self.max_windows:
            windows = windows[:self.max_windows]
            print(f"  ⚠️  限制为前 {self.max_windows} 个窗口（快速测试模式）")

        return windows

    def train_window(self, train_df: pl.DataFrame, selected_features: List[str],
                    window_id: int) -> xgb.XGBRegressor:
        """
        训练单个窗口的模型

        Args:
            train_df: 训练数据
            selected_features: 选中的特征列表
            window_id: 窗口ID

        Returns:
            model: 训练好的XGBoost模型
        """
        print(f"\n  🤖 训练窗口 {window_id} 的模型...")

        # 准备训练数据
        train_pd = train_df.to_pandas()

        # 过滤掉target缺失的样本
        train_pd = train_pd.dropna(subset=['target'])

        # 准备X, y
        X_train = train_pd[selected_features].fillna(0)  # 简单填充缺失值
        y_train = train_pd['target']

        print(f"  训练样本数: {len(X_train):,}")
        print(f"  特征数: {len(selected_features)}")

        # 训练XGBoost
        model = xgb.XGBRegressor(**self.xgb_params)
        model.fit(X_train, y_train, verbose=False)

        print(f"  ✅ 模型训练完成")

        return model

    def get_best_single_factor(self, train_df: pl.DataFrame, ic_stats: pd.DataFrame) -> str:
        """
        从训练窗内选择最佳单因子作为基线

        Args:
            train_df: 训练数据
            ic_stats: IC统计DataFrame

        Returns:
            best_factor: 最佳单因子名称
        """
        if len(ic_stats) == 0:
            return None

        # 按|IC Mean|排序，选择最佳
        ic_stats = ic_stats.copy()
        ic_stats['abs_ic'] = ic_stats['ic_mean'].abs()
        best_factor = ic_stats.sort_values('abs_ic', ascending=False).iloc[0]['feature']

        return best_factor

    def predict_window(self, model: xgb.XGBRegressor, test_df: pl.DataFrame,
                      selected_features: List[str], window_id: int,
                      best_single_factor: str = None) -> pd.DataFrame:
        """
        对测试窗口进行预测（包含单因子基线）

        Args:
            model: 训练好的模型
            test_df: 测试数据
            selected_features: 选中的特征列表
            window_id: 窗口ID
            best_single_factor: 最佳单因子名称（用于基线对比）

        Returns:
            predictions: 预测结果DataFrame (timestamp, symbol, y_true, y_pred, y_pred_baseline, window_id)
        """
        print(f"  🔮 预测窗口 {window_id}...")

        # 准备测试数据
        test_pd = test_df.to_pandas()

        # 过滤掉target缺失的样本
        test_pd = test_pd.dropna(subset=['target'])

        # 准备X, y
        X_test = test_pd[selected_features].fillna(0)
        y_test = test_pd['target']

        print(f"  测试样本数: {len(X_test):,}")

        # XGBoost预测
        y_pred = model.predict(X_test)

        # 单因子基线预测
        y_pred_baseline = None
        if best_single_factor and best_single_factor in test_pd.columns:
            y_pred_baseline = test_pd[best_single_factor].fillna(0).values
            print(f"  📊 单因子基线: {best_single_factor}")

        # 构建结果DataFrame
        predictions = pd.DataFrame({
            'timestamp': test_pd['timestamp'].values,
            'symbol': test_pd['symbol'].values,
            'y_true': y_test.values,
            'y_pred': y_pred,
            'y_pred_baseline': y_pred_baseline if y_pred_baseline is not None else np.nan,
            'window_id': window_id
        })

        print(f"  ✅ 预测完成")

        return predictions

    def run_walkforward(self, feature_df: pl.DataFrame, feature_selector,
                       output_dir: str = "data/ml_results") -> Tuple[pd.DataFrame, Dict]:
        """
        运行完整的walk-forward训练流程

        Args:
            feature_df: 特征DataFrame
            feature_selector: 特征选择器实例
            output_dir: 输出目录

        Returns:
            all_predictions: 所有OOS预测结果
            window_info: 窗口信息字典
        """
        print(f"\n{'='*60}")
        print(f"🚀 开始Walk-forward训练")
        print(f"{'='*60}")

        # 创建输出目录
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 获取所有特征列
        feature_cols = [col for col in feature_df.columns
                       if col.startswith('alpha_')]

        print(f"总特征数: {len(feature_cols)}")

        # 生成窗口
        windows = self.generate_windows(feature_df)

        # 存储所有预测结果
        all_predictions = []
        window_info = {
            'windows': [],
            'selected_features': {},
            'ic_stats': {}
        }

        # 遍历每个窗口
        for i, (train_start, train_end, test_start, test_end) in enumerate(windows):
            window_id = i + 1

            print(f"\n{'='*60}")
            print(f"📊 窗口 {window_id}/{len(windows)}")
            print(f"{'='*60}")
            print(f"训练期: {train_start.date()} 至 {train_end.date()}")
            print(f"测试期: {test_start.date()} 至 {test_end.date()}")

            # 切分训练和测试数据
            train_df = feature_df.filter(
                (pl.col('timestamp') >= train_start) &
                (pl.col('timestamp') < train_end)
            )

            test_df = feature_df.filter(
                (pl.col('timestamp') >= test_start) &
                (pl.col('timestamp') < test_end)
            )

            print(f"训练样本: {train_df.height:,}")
            print(f"测试样本: {test_df.height:,}")

            # Step 1: 训练窗内特征筛选
            selected_features, ic_stats = feature_selector.select_features_for_window(
                train_df, feature_cols
            )

            if len(selected_features) == 0:
                print(f"  ⚠️  警告: 窗口 {window_id} 没有选中任何特征，跳过")
                continue

            # 获取最佳单因子基线
            best_single_factor = self.get_best_single_factor(train_df, ic_stats)
            print(f"  📊 最佳单因子基线: {best_single_factor}")

            # 保存窗口信息
            window_info['windows'].append({
                'window_id': window_id,
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end,
                'n_features': len(selected_features),
                'best_single_factor': best_single_factor
            })
            window_info['selected_features'][window_id] = selected_features
            window_info['ic_stats'][window_id] = ic_stats

            # Step 2: 训练模型
            model = self.train_window(train_df, selected_features, window_id)

            # Step 3: 预测测试窗口（包含单因子基线）
            predictions = self.predict_window(model, test_df, selected_features, window_id, best_single_factor)

            all_predictions.append(predictions)

            # 保存模型（可选）
            model_path = output_path / f"model_window_{window_id}.pkl"
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)

        # 合并所有预测结果
        if len(all_predictions) > 0:
            all_predictions_df = pd.concat(all_predictions, ignore_index=True)
        else:
            all_predictions_df = pd.DataFrame()

        print(f"\n{'='*60}")
        print(f"✅ Walk-forward训练完成")
        print(f"{'='*60}")
        print(f"总窗口数: {len(windows)}")
        print(f"有效窗口数: {len(all_predictions)}")
        print(f"总OOS预测样本: {len(all_predictions_df):,}")

        # 保存预测结果
        predictions_path = output_path / "oos_predictions.parquet"
        all_predictions_df.to_parquet(predictions_path, index=False)
        print(f"✅ OOS预测结果已保存: {predictions_path}")

        # 保存窗口信息
        window_info_path = output_path / "window_info.pkl"
        with open(window_info_path, 'wb') as f:
            pickle.dump(window_info, f)
        print(f"✅ 窗口信息已保存: {window_info_path}")

        return all_predictions_df, window_info


if __name__ == "__main__":
    # 测试代码
    print("Walk-forward Trainer - 测试模式")
    print("请使用 run_ml_feature_mining.py 运行完整流水线")
