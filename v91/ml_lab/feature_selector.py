"""
Feature Selector - Phase ML.1

训练窗内特征筛选器 - 严格防泄漏
关键要求：
1. 特征筛选必须只在训练窗内完成
2. 每个训练窗独立筛选Top 100 Alpha
3. 去共线处理只在训练窗内进行
4. 禁止使用测试窗信息
"""

import polars as pl
import pandas as pd
import numpy as np
from typing import List, Tuple, Dict
from scipy.stats import pearsonr


class FeatureSelector:
    def __init__(self, ic_threshold=0.001, corr_threshold=0.7, top_n=100):
        """
        初始化特征选择器

        Args:
            ic_threshold: IC绝对值最小阈值
            corr_threshold: 相关性剪枝阈值
            top_n: 保留的Top特征数量
        """
        self.ic_threshold = ic_threshold
        self.corr_threshold = corr_threshold
        self.top_n = top_n

    def calculate_daily_ic(self, feature_df: pl.DataFrame, feature_cols: List[str]) -> pd.DataFrame:
        """
        计算每个特征的日度横截面IC

        Args:
            feature_df: 特征DataFrame (必须包含timestamp, symbol, target, alpha_xxxx)
            feature_cols: 特征列名列表

        Returns:
            ic_stats: IC统计DataFrame (feature, ic_mean, ic_std, ir, t_stat)
        """
        print(f"  📊 Stage B 严格日度IC计算: {len(feature_cols)} 个特征...")

        # 转换为pandas以便计算
        df_pd = feature_df.to_pandas()

        # 按日期分组计算IC
        ic_results = []

        for feature in feature_cols:
            daily_ics = []

            for date, group in df_pd.groupby('timestamp'):
                # 过滤掉缺失值
                valid_data = group[[feature, 'target']].dropna()

                if len(valid_data) < 10:  # 至少需要10个样本
                    continue

                # 计算横截面相关性
                try:
                    ic, _ = pearsonr(valid_data[feature], valid_data['target'])
                    if not np.isnan(ic):
                        daily_ics.append(ic)
                except:
                    continue

            if len(daily_ics) > 0:
                ic_mean = np.mean(daily_ics)
                ic_std = np.std(daily_ics)
                ir = ic_mean / (ic_std + 1e-8)
                t_stat = ic_mean / (ic_std / np.sqrt(len(daily_ics)) + 1e-8)

                ic_results.append({
                    'feature': feature,
                    'ic_mean': ic_mean,
                    'ic_std': ic_std,
                    'ir': ir,
                    't_stat': t_stat,
                    'n_days': len(daily_ics)
                })

        ic_stats = pd.DataFrame(ic_results)
        print(f"  ✅ IC计算完成: {len(ic_stats)} 个有效特征")

        return ic_stats

    def select_top_features(self, ic_stats: pd.DataFrame) -> List[str]:
        """
        根据IC统计选择Top特征

        Args:
            ic_stats: IC统计DataFrame

        Returns:
            selected_features: 选中的特征列表
        """
        # 过滤掉IC过低的特征
        ic_stats = ic_stats[ic_stats['ic_mean'].abs() >= self.ic_threshold].copy()

        if len(ic_stats) == 0:
            print(f"  ⚠️  警告: 没有特征满足IC阈值 {self.ic_threshold}")
            return []

        # 按|IC Mean|排序
        ic_stats['abs_ic'] = ic_stats['ic_mean'].abs()
        ic_stats = ic_stats.sort_values('abs_ic', ascending=False)

        # 选择Top N
        top_features = ic_stats.head(self.top_n * 2)['feature'].tolist()  # 先选2倍，后续去共线

        print(f"  ✅ 初步筛选: {len(top_features)} 个特征")

        return top_features

    def correlation_pruning(self, feature_df: pl.DataFrame, candidate_features: List[str],
                           ic_stats: pd.DataFrame) -> List[str]:
        """
        去共线处理 - 只在训练窗内进行

        Args:
            feature_df: 特征DataFrame
            candidate_features: 候选特征列表
            ic_stats: IC统计DataFrame

        Returns:
            selected_features: 去共线后的特征列表
        """
        print(f"  🔧 去共线处理 (阈值={self.corr_threshold})...")

        if len(candidate_features) == 0:
            return []

        # 转换为pandas
        df_pd = feature_df.select(['timestamp', 'symbol'] + candidate_features).to_pandas()

        # 计算特征相关性矩阵
        feature_data = df_pd[candidate_features].dropna()

        if len(feature_data) < 100:
            print(f"  ⚠️  警告: 有效样本不足，跳过去共线")
            return candidate_features[:self.top_n]

        corr_matrix = feature_data.corr()

        # 按IC排序特征（优先保留IC高的）
        ic_dict = dict(zip(ic_stats['feature'], ic_stats['ic_mean'].abs()))
        sorted_features = sorted(candidate_features, key=lambda x: ic_dict.get(x, 0), reverse=True)

        # 贪心去共线
        selected = []
        for feature in sorted_features:
            if len(selected) >= self.top_n:
                break

            # 检查与已选特征的相关性
            is_redundant = False
            for selected_feature in selected:
                if abs(corr_matrix.loc[feature, selected_feature]) > self.corr_threshold:
                    is_redundant = True
                    break

            if not is_redundant:
                selected.append(feature)

        print(f"  ✅ 去共线完成: 保留 {len(selected)} 个特征")

        return selected

    def fast_prefilter(self, train_df: pl.DataFrame, feature_cols: List[str], top_n=100) -> List[str]:
        """
        快速预筛选 - 删除常数/低方差特征，用简单指标筛选到Top 100（研究模式）

        Args:
            train_df: 训练窗口数据
            feature_cols: 所有特征列名
            top_n: 预筛选保留数量

        Returns:
            prefiltered_features: 预筛选后的特征列表
        """
        print(f"  ⚡ Stage A 快速预筛选: {len(feature_cols)} -> {top_n}...")

        df_pd = train_df.to_pandas()

        feature_scores = []

        for feature in feature_cols:
            # 获取特征值
            values = df_pd[feature].values

            # 过滤NaN
            valid_values = values[~np.isnan(values)]

            if len(valid_values) < 100:
                continue

            # 检查方差
            std = np.std(valid_values)
            if std < 1e-8:  # 常数特征
                continue

            # 快速代理指标：整体相关性（非横截面）
            target_values = df_pd['target'].values
            valid_mask = ~(np.isnan(values) | np.isnan(target_values))

            if valid_mask.sum() < 100:
                continue

            try:
                corr = np.corrcoef(values[valid_mask], target_values[valid_mask])[0, 1]
                if not np.isnan(corr):
                    feature_scores.append({
                        'feature': feature,
                        'abs_corr': abs(corr),
                        'std': std
                    })
            except:
                continue

        if len(feature_scores) == 0:
            print(f"  ⚠️  警告: 没有有效特征")
            return []

        # 按绝对相关性排序
        feature_scores_df = pd.DataFrame(feature_scores)
        feature_scores_df = feature_scores_df.sort_values('abs_corr', ascending=False)

        prefiltered = feature_scores_df.head(top_n)['feature'].tolist()

        print(f"  ✅ 预筛选完成: 保留 {len(prefiltered)} 个特征")

        return prefiltered

    def select_features_for_window(self, train_df: pl.DataFrame, feature_cols: List[str]) -> Tuple[List[str], pd.DataFrame]:
        """
        为单个训练窗口选择特征（研究模式 - 两阶段筛选）

        Args:
            train_df: 训练窗口数据
            feature_cols: 所有特征列名

        Returns:
            selected_features: 选中的特征列表
            ic_stats: IC统计DataFrame
        """
        print(f"\n  🎯 训练窗内特征筛选（研究模式 - 两阶段）...")
        print(f"  训练窗样本数: {train_df.height:,}")
        print(f"  候选特征数: {len(feature_cols)}")

        # Stage A: 快速预筛选（删除常数/低方差，用简单指标筛到100）
        prefiltered_features = self.fast_prefilter(train_df, feature_cols, top_n=100)

        if len(prefiltered_features) == 0:
            print(f"  ⚠️  警告: Stage A 预筛选后没有有效特征")
            return [], pd.DataFrame()

        # Stage B: 计算严格的日度横截面IC（只对预筛选后的特征）
        ic_stats = self.calculate_daily_ic(train_df, prefiltered_features)

        if len(ic_stats) == 0:
            print(f"  ⚠️  警告: Stage B 没有有效特征")
            return [], ic_stats

        # Step 2: 选择Top特征
        candidate_features = self.select_top_features(ic_stats)

        if len(candidate_features) == 0:
            return [], ic_stats

        # Step 3: 去共线
        selected_features = self.correlation_pruning(train_df, candidate_features, ic_stats)

        print(f"  ✅ 最终选中: {len(selected_features)} 个特征\n")

        return selected_features, ic_stats


if __name__ == "__main__":
    # 测试代码
    print("Feature Selector - 测试模式")
    print("请使用 run_ml_feature_mining.py 运行完整流水线")
