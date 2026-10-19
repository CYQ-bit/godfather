"""
OOS Backtester - Phase ML.1

样本外评估与组合回测
关键要求：
1. 只使用OOS窗口的预测结果
2. 计算日度横截面IC
3. 基于预测值构建Top/Bottom组合
4. 与基线对比
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple
from scipy.stats import pearsonr
import matplotlib.pyplot as plt
from pathlib import Path


class OOSBacktester:
    def __init__(self):
        """初始化OOS回测器"""
        pass

    def calculate_oos_ic(self, predictions_df: pd.DataFrame) -> Dict:
        """
        计算OOS IC指标

        Args:
            predictions_df: 预测结果DataFrame (timestamp, symbol, y_true, y_pred, window_id)

        Returns:
            ic_metrics: IC指标字典
        """
        print(f"\n{'='*60}")
        print(f"📊 计算OOS IC指标")
        print(f"{'='*60}")

        # 按日期分组计算IC
        daily_ics = []

        for date, group in predictions_df.groupby('timestamp'):
            # 过滤掉缺失值
            valid_data = group[['y_true', 'y_pred']].dropna()

            if len(valid_data) < 10:  # 至少需要10个样本
                continue

            # 计算横截面相关性
            try:
                ic, _ = pearsonr(valid_data['y_pred'], valid_data['y_true'])
                if not np.isnan(ic):
                    daily_ics.append({
                        'date': date,
                        'ic': ic,
                        'n_stocks': len(valid_data)
                    })
            except:
                continue

        daily_ic_df = pd.DataFrame(daily_ics)

        if len(daily_ic_df) == 0:
            print("⚠️  警告: 没有有效的IC数据")
            return {}

        # 计算统计指标
        ic_mean = daily_ic_df['ic'].mean()
        ic_std = daily_ic_df['ic'].std()
        ir = ic_mean / (ic_std + 1e-8)
        t_stat = ic_mean / (ic_std / np.sqrt(len(daily_ic_df)) + 1e-8)

        ic_metrics = {
            'ic_mean': ic_mean,
            'ic_std': ic_std,
            'ir': ir,
            't_stat': t_stat,
            'n_days': len(daily_ic_df),
            'daily_ic': daily_ic_df
        }

        print(f"OOS IC Mean: {ic_mean:.6f}")
        print(f"OOS IC Std:  {ic_std:.6f}")
        print(f"OOS IR:      {ir:.4f}")
        print(f"OOS T-stat:  {t_stat:.4f}")
        print(f"有效天数:    {len(daily_ic_df)}")

        return ic_metrics

    def create_portfolio(self, predictions_df: pd.DataFrame, top_pct=0.1, bottom_pct=0.1,
                        holding_days=5, non_overlapping=True, cost_bps=10.0) -> pd.DataFrame:
        """
        基于预测值创建Top/Bottom组合（支持非重叠持有期）

        Args:
            predictions_df: 预测结果DataFrame
            top_pct: Top组合百分比
            bottom_pct: Bottom组合百分比
            holding_days: 持有天数（默认5天）
            non_overlapping: 是否使用非重叠持有期（默认True）
            cost_bps: 单边交易成本（基点）。按每期多、空两腿的换手比例扣除，买卖双边各算一次

        Returns:
            portfolio_returns: 组合收益DataFrame
        """
        print(f"\n{'='*60}")
        print(f"📈 构建Top/Bottom组合")
        print(f"{'='*60}")
        print(f"Top组合: {top_pct*100:.0f}%")
        print(f"Bottom组合: {bottom_pct*100:.0f}%")
        print(f"持有期: {holding_days}天")
        print(f"非重叠模式: {'是' if non_overlapping else '否'}")

        portfolio_returns = []

        # 获取所有唯一日期并排序
        all_dates = sorted(predictions_df['timestamp'].unique())

        if non_overlapping:
            # 非重叠模式：每holding_days天再平衡一次
            rebalance_dates = all_dates[::holding_days]
            print(f"再平衡日期数: {len(rebalance_dates)}")
        else:
            # 重叠模式：每天都再平衡（原始逻辑）
            rebalance_dates = all_dates

        prev_top, prev_bottom = set(), set()
        for date in rebalance_dates:
            group = predictions_df[predictions_df['timestamp'] == date]

            if len(group) == 0:
                continue

            # 按预测值排序
            group = group.sort_values('y_pred', ascending=False)

            n_stocks = len(group)
            n_top = max(1, int(n_stocks * top_pct))
            n_bottom = max(1, int(n_stocks * bottom_pct))

            # Top组合（做多）
            top_stocks = group.head(n_top)
            top_return = top_stocks['y_true'].mean()

            # Bottom组合（做空）
            bottom_stocks = group.tail(n_bottom)
            bottom_return = bottom_stocks['y_true'].mean()

            # 换手：本期新进入的名字占比（等权）；首期为全部建仓
            top_set, bottom_set = set(top_stocks['symbol']), set(bottom_stocks['symbol'])
            turn_top = 1 - len(top_set & prev_top) / len(top_set)
            turn_bottom = 1 - len(bottom_set & prev_bottom) / len(bottom_set)
            prev_top, prev_bottom = top_set, bottom_set
            # 换出卖一次、换入买一次 => 每腿成本 = 2 * 换手 * 单边成本
            cost = 2 * (turn_top + turn_bottom) * cost_bps / 1e4

            # Long-Short组合（扣成本）
            ls_return = top_return - bottom_return - cost

            portfolio_returns.append({
                'date': date,
                'top_return': top_return,
                'bottom_return': bottom_return,
                'ls_return': ls_return,
                'cost': cost,
                'n_stocks': n_stocks,
                'holding_days': holding_days
            })

        portfolio_df = pd.DataFrame(portfolio_returns)

        print(f"✅ 组合构建完成: {len(portfolio_df)} 个再平衡期")

        return portfolio_df

    def calculate_portfolio_metrics(self, portfolio_df: pd.DataFrame) -> Dict:
        """
        计算组合绩效指标（修正版：正确处理持有期）

        Args:
            portfolio_df: 组合收益DataFrame

        Returns:
            metrics: 绩效指标字典
        """
        print(f"\n{'='*60}")
        print(f"📊 计算组合绩效指标")
        print(f"{'='*60}")

        # 获取持有期天数
        holding_days = portfolio_df['holding_days'].iloc[0] if 'holding_days' in portfolio_df.columns else 1

        # 计算累计收益
        portfolio_df['cum_top'] = (1 + portfolio_df['top_return']).cumprod()
        portfolio_df['cum_bottom'] = (1 + portfolio_df['bottom_return']).cumprod()
        portfolio_df['cum_ls'] = (1 + portfolio_df['ls_return']).cumprod()

        # 计算实际时间跨度
        n_periods = len(portfolio_df)  # 再平衡期数
        first_date = portfolio_df['date'].iloc[0]
        last_date = portfolio_df['date'].iloc[-1]
        actual_days = (last_date - first_date).days
        n_years = actual_days / 365.25  # 使用实际天数计算年数

        # 总收益
        total_return_ls = portfolio_df['cum_ls'].iloc[-1] - 1
        total_return_top = portfolio_df['cum_top'].iloc[-1] - 1
        total_return_bottom = portfolio_df['cum_bottom'].iloc[-1] - 1

        # 年化收益
        annual_return_ls = (1 + total_return_ls) ** (1 / n_years) - 1
        annual_return_top = (1 + total_return_top) ** (1 / n_years) - 1
        annual_return_bottom = (1 + total_return_bottom) ** (1 / n_years) - 1

        # 年化波动率（关键修正：考虑持有期）
        # 如果持有期是5天，每年有252/5=50.4个再平衡期
        periods_per_year = 252 / holding_days
        annual_vol_ls = portfolio_df['ls_return'].std() * np.sqrt(periods_per_year)
        annual_vol_top = portfolio_df['top_return'].std() * np.sqrt(periods_per_year)
        annual_vol_bottom = portfolio_df['bottom_return'].std() * np.sqrt(periods_per_year)

        # Sharpe比率
        sharpe_ls = annual_return_ls / (annual_vol_ls + 1e-8)
        sharpe_top = annual_return_top / (annual_vol_top + 1e-8)
        sharpe_bottom = annual_return_bottom / (annual_vol_bottom + 1e-8)

        # 最大回撤
        def calculate_max_drawdown(cum_returns):
            running_max = cum_returns.expanding().max()
            drawdown = (cum_returns - running_max) / running_max
            return drawdown.min()

        max_dd_ls = calculate_max_drawdown(portfolio_df['cum_ls'])
        max_dd_top = calculate_max_drawdown(portfolio_df['cum_top'])
        max_dd_bottom = calculate_max_drawdown(portfolio_df['cum_bottom'])

        # 胜率
        win_rate_ls = (portfolio_df['ls_return'] > 0).mean()
        win_rate_top = (portfolio_df['top_return'] > 0).mean()
        win_rate_bottom = (portfolio_df['bottom_return'] > 0).mean()

        metrics = {
            'ls': {
                'annual_return': annual_return_ls,
                'annual_vol': annual_vol_ls,
                'sharpe': sharpe_ls,
                'max_drawdown': max_dd_ls,
                'win_rate': win_rate_ls,
                'total_return': total_return_ls
            },
            'top': {
                'annual_return': annual_return_top,
                'annual_vol': annual_vol_top,
                'sharpe': sharpe_top,
                'max_drawdown': max_dd_top,
                'win_rate': win_rate_top,
                'total_return': total_return_top
            },
            'bottom': {
                'annual_return': annual_return_bottom,
                'annual_vol': annual_vol_bottom,
                'sharpe': sharpe_bottom,
                'max_drawdown': max_dd_bottom,
                'win_rate': win_rate_bottom,
                'total_return': total_return_bottom
            },
            'n_periods': n_periods,
            'n_years': n_years,
            'holding_days': holding_days,
            'periods_per_year': periods_per_year,
            'actual_days': actual_days
        }

        print(f"\n【Long-Short组合】")
        print(f"年化收益: {annual_return_ls*100:.2f}%")
        print(f"年化波动: {annual_vol_ls*100:.2f}%")
        print(f"Sharpe比率: {sharpe_ls:.4f}")
        print(f"最大回撤: {max_dd_ls*100:.2f}%")
        print(f"胜率: {win_rate_ls*100:.2f}%")

        print(f"\n【Top组合（Long）】")
        print(f"年化收益: {annual_return_top*100:.2f}%")
        print(f"Sharpe比率: {sharpe_top:.4f}")

        print(f"\n【Bottom组合（Short）】")
        print(f"年化收益: {annual_return_bottom*100:.2f}%")
        print(f"Sharpe比率: {sharpe_bottom:.4f}")

        return metrics

    def create_best_single_factor_baseline(self, predictions_df: pd.DataFrame,
                                          window_info: Dict, feature_metadata: pd.DataFrame) -> Dict:
        """
        创建最佳单因子基线

        Args:
            predictions_df: 预测结果DataFrame
            window_info: 窗口信息
            feature_metadata: 特征元数据

        Returns:
            baseline_metrics: 最佳单因子基线指标
        """
        print(f"\n{'='*60}")
        print(f"🏆 创建最佳单因子基线")
        print(f"{'='*60}")

        # 统计被选中频率最高的特征
        all_selected_features = []
        for features in window_info['selected_features'].values():
            all_selected_features.extend(features)

        from collections import Counter
        feature_counter = Counter(all_selected_features)

        if len(feature_counter) == 0:
            print("⚠️  警告: 没有被选中的特征")
            return {}

        # 选择被选中频率最高的特征作为最佳单因子
        best_feature, best_count = feature_counter.most_common(1)[0]

        # 查找formula
        formula = feature_metadata[feature_metadata['alpha_name'] == best_feature]['formula'].values
        formula_str = formula[0] if len(formula) > 0 else "N/A"

        print(f"最佳单因子: {best_feature}")
        print(f"被选中次数: {best_count}/{len(window_info['windows'])}")
        print(f"公式: {formula_str}")

        # 使用该单因子的IC作为基线（需要从window_info中提取）
        # 简化：返回统计信息
        baseline_metrics = {
            'best_feature': best_feature,
            'selection_count': best_count,
            'formula': formula_str
        }

        return baseline_metrics

    def evaluate_single_factor_baseline(self, predictions_df: pd.DataFrame,
                                        single_factor_predictions: pd.DataFrame,
                                        holding_days: int = 5) -> Dict:
        """
        评估最佳单因子基线

        Args:
            predictions_df: ML预测结果DataFrame (用于获取y_true)
            single_factor_predictions: 单因子预测DataFrame (timestamp, symbol, y_pred_single)
            holding_days: 持有天数

        Returns:
            baseline_results: 单因子基线评估结果
        """
        print(f"\n{'='*60}")
        print(f"🏆 评估最佳单因子基线")
        print(f"{'='*60}")

        # 合并ML的y_true和单因子的y_pred
        merged_df = predictions_df[['timestamp', 'symbol', 'y_true']].merge(
            single_factor_predictions[['timestamp', 'symbol', 'y_pred_single']],
            on=['timestamp', 'symbol'],
            how='inner'
        )

        # 重命名列以适配现有方法
        baseline_pred_df = merged_df.rename(columns={'y_pred_single': 'y_pred'})

        # 1. 计算IC指标
        ic_metrics = self.calculate_oos_ic(baseline_pred_df)

        # 2. 构建组合
        portfolio_df = self.create_portfolio(baseline_pred_df, holding_days=holding_days, non_overlapping=True)

        # 3. 计算组合指标
        portfolio_metrics = self.calculate_portfolio_metrics(portfolio_df)

        baseline_results = {
            'ic_metrics': ic_metrics,
            'portfolio_metrics': portfolio_metrics,
            'portfolio_df': portfolio_df
        }

        return baseline_results

    def audit_return_calculation(self, predictions_df: pd.DataFrame, holding_days: int = 5) -> Dict:
        """
        审计收益计算方法

        Args:
            predictions_df: 预测结果DataFrame
            holding_days: 持有天数

        Returns:
            audit_report: 审计报告
        """
        print(f"\n{'='*60}")
        print(f"🔍 收益计算审计")
        print(f"{'='*60}")

        # 检查target列名
        target_col = 'y_true'
        if target_col not in predictions_df.columns:
            print(f"⚠️  警告: 未找到{target_col}列")
            return {}

        # 统计target的基本信息
        target_mean = predictions_df[target_col].mean()
        target_std = predictions_df[target_col].std()
        target_min = predictions_df[target_col].min()
        target_max = predictions_df[target_col].max()

        # 检查是否有异常值
        n_samples = len(predictions_df)
        n_dates = predictions_df['timestamp'].nunique()

        audit_report = {
            'target_column': target_col,
            'holding_days': holding_days,
            'target_mean': target_mean,
            'target_std': target_std,
            'target_min': target_min,
            'target_max': target_max,
            'n_samples': n_samples,
            'n_dates': n_dates
        }

        print(f"\n【A. Target定义】")
        print(f"Target列名: {target_col}")
        print(f"Target含义: 未来{holding_days}日收益率")
        print(f"Target均值: {target_mean:.6f}")
        print(f"Target标准差: {target_std:.6f}")
        print(f"Target范围: [{target_min:.6f}, {target_max:.6f}]")

        print(f"\n【B. 持有期聚合】")
        print(f"持有期: {holding_days}天")
        print(f"再平衡频率: 每{holding_days}天")
        print(f"组合构建方式: 非重叠持有期（推荐方案）")
        print(f"年化因子: sqrt(252/{holding_days}) = sqrt({252/holding_days:.2f})")

        print(f"\n【C. 收益计算逻辑】")
        print(f"1. 每{holding_days}天选择一次Top/Bottom组合")
        print(f"2. 组合收益 = 该期间的平均target值（即未来{holding_days}日收益）")
        print(f"3. 年化波动率 = 期间收益标准差 × sqrt(252/{holding_days})")
        print(f"4. 年化收益 = (1 + 总收益)^(1/实际年数) - 1")
        print(f"5. Sharpe = 年化收益 / 年化波动率")

        print(f"\n【D. 与旧版本的差异】")
        print(f"旧版本问题: 将{holding_days}日收益当作1日收益，导致:")
        print(f"  - 年化波动率被高估 sqrt(252) / sqrt(252/{holding_days}) = sqrt({holding_days}) = {np.sqrt(holding_days):.2f}倍")
        print(f"  - Sharpe被高估约 {np.sqrt(holding_days):.2f}倍")
        print(f"新版本修正: 正确使用 sqrt(252/{holding_days}) 作为年化因子")

        return audit_report

    def create_random_baseline(self, predictions_df: pd.DataFrame, n_trials: int = 10, holding_days: int = 5) -> Dict:
        """
        创建随机预测基线

        Args:
            predictions_df: 预测结果DataFrame
            n_trials: 随机试验次数
            holding_days: 持有天数

        Returns:
            baseline_metrics: 基线指标
        """
        print(f"\n{'='*60}")
        print(f"🎲 创建随机预测基线 (n_trials={n_trials})")
        print(f"{'='*60}")

        random_ics = []
        random_sharpes = []

        for trial in range(n_trials):
            # 生成随机预测
            random_pred_df = predictions_df.copy()
            np.random.seed(42 + trial)
            random_pred_df['y_pred'] = np.random.randn(len(random_pred_df))

            # 计算IC
            ic_metrics = self.calculate_oos_ic(random_pred_df)
            if 'ic_mean' in ic_metrics:
                random_ics.append(ic_metrics['ic_mean'])

            # 计算组合收益（使用修正后的方法）
            portfolio_df = self.create_portfolio(random_pred_df, holding_days=holding_days, non_overlapping=True)
            portfolio_metrics = self.calculate_portfolio_metrics(portfolio_df)
            random_sharpes.append(portfolio_metrics['ls']['sharpe'])

        baseline_metrics = {
            'ic_mean': np.mean(random_ics) if random_ics else 0,
            'ic_std': np.std(random_ics) if random_ics else 0,
            'sharpe_mean': np.mean(random_sharpes) if random_sharpes else 0,
            'sharpe_std': np.std(random_sharpes) if random_sharpes else 0
        }

        print(f"随机基线 IC Mean: {baseline_metrics['ic_mean']:.6f} ± {baseline_metrics['ic_std']:.6f}")
        print(f"随机基线 Sharpe: {baseline_metrics['sharpe_mean']:.4f} ± {baseline_metrics['sharpe_std']:.4f}")

        return baseline_metrics

    def plot_cumulative_returns(self, portfolio_df: pd.DataFrame, output_path: str):
        """
        绘制累计收益曲线

        Args:
            portfolio_df: 组合收益DataFrame
            output_path: 输出路径
        """
        plt.figure(figsize=(12, 6))

        plt.plot(portfolio_df['date'], portfolio_df['cum_ls'], label='Long-Short', linewidth=2)
        plt.plot(portfolio_df['date'], portfolio_df['cum_top'], label='Top (Long)', linewidth=1.5, alpha=0.7)
        plt.plot(portfolio_df['date'], portfolio_df['cum_bottom'], label='Bottom (Short)', linewidth=1.5, alpha=0.7)

        plt.axhline(y=1, color='black', linestyle='--', alpha=0.3)
        plt.xlabel('Date')
        plt.ylabel('Cumulative Return')
        plt.title('OOS Portfolio Cumulative Returns')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        plt.savefig(output_path, dpi=150)
        print(f"✅ 累计收益曲线已保存: {output_path}")
        plt.close()

    def run_full_evaluation(self, predictions_df: pd.DataFrame, window_info: Dict,
                           feature_metadata: pd.DataFrame, single_factor_predictions: pd.DataFrame = None,
                           holding_days: int = 5, output_dir: str = "data/ml_results") -> Dict:
        """
        运行完整的OOS评估（ML.1.1确认版）

        Args:
            predictions_df: ML预测结果DataFrame
            window_info: 窗口信息
            feature_metadata: 特征元数据
            single_factor_predictions: 单因子预测DataFrame（可选）
            holding_days: 持有天数
            output_dir: 输出目录

        Returns:
            results: 完整评估结果
        """
        print(f"\n{'='*60}")
        print(f"🎯 开始OOS完整评估（ML.1.1确认版）")
        print(f"{'='*60}")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 0. 审计收益计算方法
        audit_report = self.audit_return_calculation(predictions_df, holding_days=holding_days)

        # 1. 计算ML模型的OOS IC
        print(f"\n{'='*60}")
        print(f"📊 评估ML模型")
        print(f"{'='*60}")
        ic_metrics = self.calculate_oos_ic(predictions_df)

        # 2. 构建ML组合（使用修正后的方法）
        portfolio_df = self.create_portfolio(predictions_df, holding_days=holding_days, non_overlapping=True)

        # 3. 计算ML组合指标
        portfolio_metrics = self.calculate_portfolio_metrics(portfolio_df)

        # 4. 评估最佳单因子基线（如果提供）
        single_factor_results = None
        if single_factor_predictions is not None:
            print(f"\n{'='*60}")
            print(f"📊 评估最佳单因子基线")
            print(f"{'='*60}")
            single_factor_results = self.evaluate_single_factor_baseline(
                predictions_df, single_factor_predictions, holding_days=holding_days
            )

        # 5. 创建随机基线
        baseline_metrics = self.create_random_baseline(predictions_df, n_trials=10, holding_days=holding_days)

        # 6. 创建最佳单因子统计信息
        best_single_factor = self.create_best_single_factor_baseline(
            predictions_df, window_info, feature_metadata
        )

        # 7. 绘制累计收益曲线
        self.plot_cumulative_returns(portfolio_df, str(output_path / "cumulative_returns_ml.png"))
        if single_factor_results:
            self.plot_cumulative_returns(
                single_factor_results['portfolio_df'],
                str(output_path / "cumulative_returns_single_factor.png")
            )

        # 汇总结果
        results = {
            'audit_report': audit_report,
            'ic_metrics': ic_metrics,
            'portfolio_metrics': portfolio_metrics,
            'single_factor_results': single_factor_results,
            'baseline_metrics': baseline_metrics,
            'best_single_factor': best_single_factor,
            'portfolio_df': portfolio_df,
            'holding_days': holding_days
        }

        print(f"\n{'='*60}")
        print(f"✅ OOS评估完成")
        print(f"{'='*60}")

        return results


if __name__ == "__main__":
    # 测试代码
    print("OOS Backtester - 测试模式")
    print("请使用 run_ml_feature_mining.py 运行完整流水线")
