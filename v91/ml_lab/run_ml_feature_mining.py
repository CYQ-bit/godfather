"""
Run ML Feature Mining - Phase ML.1

完整的Walk-forward ML Feature Mining流水线
严格防泄漏 + 基线对比 + 完整评估报告
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import polars as pl
import numpy as np
import time
from datetime import datetime

from ml_lab.feature_dataset_builder import FeatureDatasetBuilder
from ml_lab.feature_selector import FeatureSelector
from ml_lab.walkforward_trainer import WalkForwardTrainer
from ml_lab.oos_backtester import OOSBacktester
from ml_lab.generate_ml11_report import generate_ml11_report
from runtime_paths import get_price_lake_glob


def print_section_header(title):
    """打印章节标题"""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}")


def generate_final_report(ic_metrics, portfolio_metrics, baseline_metrics,
                         best_single_factor, window_info, feature_metadata, total_time):
    """
    生成最终报告

    Args:
        ic_metrics: IC指标
        portfolio_metrics: 组合指标
        baseline_metrics: 基线指标
        best_single_factor: 最佳单因子基线
        window_info: 窗口信息
        feature_metadata: 特征元数据
        total_time: 总运行时间
    """
    print_section_header("【Phase ML.1 最终报告（快速烟雾测试）】")

    # A. 数据与流水线信息
    print(f"\n【A. 数据与流水线信息】")
    print(f"Alpha总数量: {len(feature_metadata)}")
    print(f"Walk-forward窗口数: {len(window_info['windows'])}")
    print(f"总运行耗时: {total_time:.1f}秒 ({total_time/60:.1f}分钟)")

    # 统计每个窗口的特征数
    feature_counts = [w['n_features'] for w in window_info['windows']]
    print(f"每个训练窗平均入选因子数: {np.mean(feature_counts):.1f}")
    print(f"入选因子数范围: {min(feature_counts)} - {max(feature_counts)}")

    # B. 训练窗内筛选报告
    print(f"\n【B. 训练窗内筛选报告】")
    print(f"Top特征选择规则: |IC Mean| 排序")
    print(f"去共线阈值: 0.7")

    # 统计被选中频率最高的Alpha
    all_selected_features = []
    for features in window_info['selected_features'].values():
        all_selected_features.extend(features)

    from collections import Counter
    feature_counter = Counter(all_selected_features)
    top_20_features = feature_counter.most_common(20)

    print(f"\n被选中频率最高的Top 20 Alpha:")
    for feature, count in top_20_features:
        freq = count / len(window_info['windows']) * 100
        # 查找formula
        formula = feature_metadata[feature_metadata['alpha_name'] == feature]['formula'].values
        formula_str = formula[0] if len(formula) > 0 else "N/A"
        print(f"  {feature}: {count}次 ({freq:.1f}%) | {formula_str[:60]}")

    # C. OOS预测表现
    print(f"\n【C. OOS预测表现】")
    if 'ic_mean' in ic_metrics:
        print(f"OOS IC Mean: {ic_metrics['ic_mean']:.6f}")
        print(f"OOS IC Std:  {ic_metrics['ic_std']:.6f}")
        print(f"OOS IR:      {ic_metrics['ir']:.4f}")
        print(f"OOS T-stat:  {ic_metrics['t_stat']:.4f}")
        print(f"有效天数:    {ic_metrics['n_days']}")
    else:
        print("⚠️  IC指标计算失败")

    # D. OOS组合表现
    print(f"\n【D. OOS组合表现】")
    ls_metrics = portfolio_metrics['ls']
    print(f"年化收益: {ls_metrics['annual_return']*100:.2f}%")
    print(f"年化波动: {ls_metrics['annual_vol']*100:.2f}%")
    print(f"Sharpe比率: {ls_metrics['sharpe']:.4f}")
    print(f"最大回撤: {ls_metrics['max_drawdown']*100:.2f}%")
    print(f"胜率: {ls_metrics['win_rate']*100:.2f}%")
    print(f"总收益: {ls_metrics['total_return']*100:.2f}%")

    print(f"\nLong单边贡献:")
    top_metrics = portfolio_metrics['top']
    print(f"  年化收益: {top_metrics['annual_return']*100:.2f}%")
    print(f"  Sharpe: {top_metrics['sharpe']:.4f}")

    print(f"\nShort单边贡献:")
    bottom_metrics = portfolio_metrics['bottom']
    print(f"  年化收益: {bottom_metrics['annual_return']*100:.2f}%")
    print(f"  Sharpe: {bottom_metrics['sharpe']:.4f}")

    # E. 基线对比
    print(f"\n【E. 基线对比】")
    print(f"随机预测基线:")
    print(f"  IC Mean: {baseline_metrics['ic_mean']:.6f} ± {baseline_metrics['ic_std']:.6f}")
    print(f"  Sharpe: {baseline_metrics['sharpe_mean']:.4f} ± {baseline_metrics['sharpe_std']:.4f}")

    print(f"\n最佳单因子基线:")
    if best_single_factor:
        print(f"  特征: {best_single_factor['best_feature']}")
        print(f"  被选中次数: {best_single_factor['selection_count']}/{len(window_info['windows'])}")
        print(f"  公式: {best_single_factor['formula'][:80]}")

    print(f"\nML模型 vs 随机基线:")
    if 'ic_mean' in ic_metrics:
        ic_improvement = (ic_metrics['ic_mean'] - baseline_metrics['ic_mean']) / (abs(baseline_metrics['ic_mean']) + 1e-8)
        print(f"  IC提升: {ic_improvement*100:.1f}%")
    sharpe_improvement = (ls_metrics['sharpe'] - baseline_metrics['sharpe_mean']) / (abs(baseline_metrics['sharpe_mean']) + 1e-8)
    print(f"  Sharpe提升: {sharpe_improvement*100:.1f}%")

    # F. 结论
    print(f"\n【F. 结论】")

    # 判断1: B.2 Alpha Factory是否产生真实OOS增益
    has_positive_ic = ic_metrics.get('ic_mean', 0) > 0
    has_positive_sharpe = ls_metrics['sharpe'] > 0
    beats_random_ic = ic_metrics.get('ic_mean', 0) > baseline_metrics['ic_mean']
    beats_random_sharpe = ls_metrics['sharpe'] > baseline_metrics['sharpe_mean']

    print(f"\n1. B.2 Alpha Factory是否产生真实OOS增益？")
    if has_positive_ic and has_positive_sharpe and beats_random_ic and beats_random_sharpe:
        print(f"   ✅ 是的，产生了真实OOS增益")
        print(f"   - OOS IC Mean > 0: {ic_metrics.get('ic_mean', 0):.6f}")
        print(f"   - Sharpe > 0: {ls_metrics['sharpe']:.4f}")
        print(f"   - 显著优于随机基线")
    else:
        print(f"   ⚠️  增益有限或不显著")
        if not has_positive_ic:
            print(f"   - OOS IC Mean ≤ 0")
        if not has_positive_sharpe:
            print(f"   - Sharpe ≤ 0")
        if not beats_random_ic:
            print(f"   - IC未显著优于随机基线")
        if not beats_random_sharpe:
            print(f"   - Sharpe未显著优于随机基线")

    # 判断2: 是否达到ML Pipeline门槛
    print(f"\n2. 当前系统是否达到进入更完整ML/Portfolio阶段的门槛？")
    ic_threshold = 0.001  # IC均值阈值
    ir_threshold = 0.5    # IR阈值
    sharpe_threshold = 0.5  # Sharpe阈值

    meets_ic = ic_metrics.get('ic_mean', 0) > ic_threshold
    meets_ir = ic_metrics.get('ir', 0) > ir_threshold
    meets_sharpe = ls_metrics['sharpe'] > sharpe_threshold

    if meets_ic and meets_ir and meets_sharpe:
        print(f"   ✅ 是的，已达到门槛")
        print(f"   - IC Mean > {ic_threshold}: ✅")
        print(f"   - IR > {ir_threshold}: ✅")
        print(f"   - Sharpe > {sharpe_threshold}: ✅")
    else:
        print(f"   ⚠️  尚未完全达到门槛")
        print(f"   - IC Mean > {ic_threshold}: {'✅' if meets_ic else '❌'}")
        print(f"   - IR > {ir_threshold}: {'✅' if meets_ir else '❌'}")
        print(f"   - Sharpe > {sharpe_threshold}: {'✅' if meets_sharpe else '❌'}")

    # 判断3: 下一步建议
    print(f"\n3. 下一步应优先做什么？")

    if meets_ic and meets_ir and meets_sharpe:
        print(f"   推荐: A. 继续做ML Pipeline")
        print(f"   理由: 模型已显示有效性，可以进入更完整的ML/Portfolio流程")
        print(f"   建议行动:")
        print(f"   - 增加更多Alpha特征（5000-10000个）")
        print(f"   - 尝试更复杂的模型（LightGBM, Neural Network）")
        print(f"   - 引入风险模型和组合优化")
        print(f"   - 构建完整的生产级回测系统")
    elif has_positive_ic and has_positive_sharpe:
        print(f"   推荐: B. 先回到因子工厂继续打磨")
        print(f"   理由: 模型有一定效果但不够强，需要更高质量的Alpha")
        print(f"   建议行动:")
        print(f"   - Phase B.3: 提高CS权重（45%/35%）")
        print(f"   - Phase C: 小规模Evolution（100代，种群50）")
        print(f"   - 增加更多衍生终端（技术指标、基本面因子）")
    else:
        print(f"   推荐: D. 全面检查系统")
        print(f"   理由: 模型效果不佳，可能存在系统性问题")
        print(f"   建议行动:")
        print(f"   - 检查数据质量和target定义")
        print(f"   - 检查特征筛选逻辑")
        print(f"   - 检查是否存在数据泄漏")
        print(f"   - 重新审视Alpha Factory设计")

    print(f"\n{'='*80}")


def main():
    """主函数"""
    start_time = time.time()

    print_section_header("🚀 Phase ML.1.1 - Walk-forward ML Feature Mining 流水线（确认版）")

    # 打印ML.1.1确认版配置
    print(f"\n{'='*80}")
    print(f"【ML.1.1 确认版配置】")
    print(f"{'='*80}")
    print(f"Mode: ML.1.1 Confirmation Version")
    print(f"Window count: 6 (扩展验证)")
    print(f"Train window: 24 months")
    print(f"Test window: 2 months")
    print(f"Step size: 2 months")
    print(f"Holding period: 5 days (non-overlapping)")
    print(f"Stage A prefilter target: 100 features")
    print(f"Stage B strict IC calculation: Top 100 features")
    print(f"Final feature count per window: 50-100 (after correlation pruning)")
    print(f"Model: XGBoost only")
    print(f"Leakage protection: ENABLED")
    print(f"Single factor baseline: ENABLED (完整评估)")
    print(f"Return calculation audit: ENABLED")
    print(f"{'='*80}\n")

    # Step 1: 加载或生成Alpha特征矩阵
    print_section_header("Step 1: 加载Alpha特征矩阵")

    feature_path = Path("data/feature_store/ml_alpha_matrix.parquet")
    metadata_path = Path("data/feature_store/ml_alpha_metadata.parquet")

    if feature_path.exists() and metadata_path.exists():
        print(f"✅ 发现已有特征文件，直接加载...")
        print(f"特征矩阵: {feature_path}")
        print(f"元数据: {metadata_path}")

        feature_df = pl.read_parquet(feature_path)
        metadata_df = pd.read_parquet(metadata_path)

        print(f"✅ 特征加载完成: {feature_df.height:,} 行 × {feature_df.width} 列")
        print(f"✅ Alpha数量: {len(metadata_df)}")

        # 重命名target列（如果需要）
        if 'target_5d' in feature_df.columns and 'target' not in feature_df.columns:
            feature_df = feature_df.rename({'target_5d': 'target'})
            print(f"✅ Target列已重命名: target_5d -> target")
    else:
        print(f"⚠️  特征文件不存在，开始生成...")
        builder = FeatureDatasetBuilder(
            data_path=get_price_lake_glob(),
            n_alphas=2000,
            max_depth=4,
            seed=42
        )

        feature_df, metadata_df = builder.generate_alpha_features()
        builder.save_features(feature_df, metadata_df)

    # Step 2-4: Walk-forward训练与评估
    print_section_header("Step 2-4: Walk-forward训练与OOS评估")

    # 创建特征选择器
    feature_selector = FeatureSelector(
        ic_threshold=0.001,
        corr_threshold=0.7,
        top_n=100
    )

    # 创建训练器（ML.1.1确认版：6个窗口）
    trainer = WalkForwardTrainer(
        train_months=24,  # 2年训练窗口
        test_months=2,    # 2个月测试窗口
        step_months=2,    # 2个月滚动步长
        max_windows=6     # ML.1.1确认版：6个窗口
    )

    # 运行walk-forward训练
    predictions_df, window_info = trainer.run_walkforward(
        feature_df, feature_selector
    )

    # Step 5: OOS评估与基线对比
    print_section_header("Step 5: OOS评估与基线对比（ML.1.1确认版）")

    # 提取单因子预测
    single_factor_predictions = predictions_df[['timestamp', 'symbol', 'y_pred_baseline']].copy()
    single_factor_predictions = single_factor_predictions.rename(columns={'y_pred_baseline': 'y_pred_single'})
    single_factor_predictions = single_factor_predictions.dropna(subset=['y_pred_single'])

    backtester = OOSBacktester()
    results = backtester.run_full_evaluation(
        predictions_df, window_info, metadata_df,
        single_factor_predictions=single_factor_predictions,
        holding_days=5  # 5天持有期
    )

    # 生成最终报告
    total_time = time.time() - start_time

    generate_ml11_report(
        ic_metrics=results['ic_metrics'],
        portfolio_metrics=results['portfolio_metrics'],
        baseline_metrics=results['baseline_metrics'],
        best_single_factor=results['best_single_factor'],
        window_info=window_info,
        feature_metadata=metadata_df,
        total_time=total_time,
        single_factor_results=results.get('single_factor_results'),
        audit_report=results.get('audit_report')
    )

    print(f"\n✅ Phase ML.1.1 完成！")
    print(f"所有结果已保存到: data/ml_results/")


if __name__ == "__main__":
    main()
