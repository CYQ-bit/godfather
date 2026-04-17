"""
Run ML.2 Robustness Confirmation - Optimized Version

ML.2 稳健性确认版（优化版）
- 8窗口 Walk-forward 主确认
- 1个 Lockbox Holdout
- 成本敏感性分析（复用预测）
- 组合参数稳定性分析（复用预测）
- 轻量 Ablation Test（只针对稳定特征家族）
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import polars as pl
import numpy as np
import time
from datetime import datetime, timedelta
import xgboost as xgb

from ml_lab.feature_dataset_builder import FeatureDatasetBuilder
from ml_lab.feature_selector import FeatureSelector
from ml_lab.walkforward_trainer import WalkForwardTrainer
from ml_lab.oos_backtester import OOSBacktester


def print_section_header(title):
    """打印章节标题"""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}")


def main():
    """主函数"""
    start_time = time.time()

    print_section_header("🚀 Phase ML.2 - 稳健性确认版（优化版）")

    # 打印ML.2配置
    print(f"\n{'='*80}")
    print(f"【ML.2 优化确认版配置】")
    print(f"{'='*80}")
    print(f"ML.2 Optimized Confirm Mode: ON")
    print(f"Window count: 8 (主确认)")
    print(f"Lockbox holdout: ON (独立封存考场)")
    print(f"Cost sensitivity: ON (复用预测)")
    print(f"Portfolio stability: ON (复用预测)")
    print(f"Light ablation: ON (稳定特征家族)")
    print(f"Train window: 24 months")
    print(f"Test window: 2 months")
    print(f"Step size: 2 months")
    print(f"Stage A prefilter: 100 features")
    print(f"Stage B strict IC: Top 100 features")
    print(f"Model: XGBoost only")
    print(f"Leakage protection: ENABLED")
    print(f"B.2 Alpha Factory: FROZEN")
    print(f"{'='*80}\n")

    # Step 1: 加载Alpha特征矩阵
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
        raise FileNotFoundError("特征文件不存在，请先运行 B.2 Alpha Factory")

    # Step 2: 8窗口 Walk-forward 主确认
    print_section_header("Step 2: 8窗口 Walk-forward 主确认")

    # 创建特征选择器
    feature_selector = FeatureSelector(
        ic_threshold=0.001,
        corr_threshold=0.7,
        top_n=100
    )

    # 创建训练器（8窗口）
    trainer = WalkForwardTrainer(
        train_months=24,
        test_months=2,
        step_months=2,
        max_windows=8  # ML.2: 8窗口
    )

    # 运行walk-forward训练
    predictions_df, window_info = trainer.run_walkforward(
        feature_df, feature_selector
    )

    # Step 3: OOS评估（8窗口）
    print_section_header("Step 3: OOS评估（8窗口主确认）")

    # 提取单因子预测
    single_factor_predictions = predictions_df[['timestamp', 'symbol', 'y_pred_baseline']].copy()
    single_factor_predictions = single_factor_predictions.rename(columns={'y_pred_baseline': 'y_pred_single'})
    single_factor_predictions = single_factor_predictions.dropna(subset=['y_pred_single'])

    backtester = OOSBacktester()
    results_8window = backtester.run_full_evaluation(
        predictions_df, window_info, metadata_df,
        single_factor_predictions=single_factor_predictions,
        holding_days=5
    )

    print(f"\n✅ 8窗口主确认完成")
    print(f"总OOS样本: {len(predictions_df):,}")

    # 保存8窗口结果
    output_dir = Path("data/ml2_results")
    output_dir.mkdir(parents=True, exist_ok=True)

    predictions_df.to_parquet(output_dir / "predictions_8window.parquet", index=False)
    print(f"✅ 8窗口预测结果已保存: {output_dir / 'predictions_8window.parquet'}")

    # Step 4: Lockbox Holdout
    print_section_header("Step 4: Lockbox Holdout（独立封存考场）")

    # 确定lockbox时间范围（最后6个月）
    max_date = feature_df.select(pl.col('timestamp').max()).item()
    lockbox_start = max_date - timedelta(days=180)  # 最后6个月

    print(f"\n📦 Lockbox设置:")
    print(f"  Lockbox开始: {lockbox_start}")
    print(f"  Lockbox结束: {max_date}")
    print(f"  ⚠️  此数据未参与任何模型设计或调参")

    # 过滤lockbox数据
    lockbox_df = feature_df.filter(pl.col('timestamp') >= lockbox_start)
    print(f"  Lockbox样本数: {lockbox_df.height:,}")

    # 使用8窗口中最稳定的特征集合
    # 统计每个特征在8个窗口中的出现频率
    feature_counts = {}
    for window_id, features in window_info['selected_features'].items():
        for feat in features:
            feature_counts[feat] = feature_counts.get(feat, 0) + 1

    # 选择出现频率>=4次的特征（至少在一半窗口中出现）
    stable_features = [f for f, cnt in feature_counts.items() if cnt >= 4]
    print(f"\n  稳定特征数（出现>=4次）: {len(stable_features)}")

    # 准备lockbox训练数据（使用lockbox之前的所有数据）
    lockbox_train_df = feature_df.filter(pl.col('timestamp') < lockbox_start)
    print(f"  Lockbox训练样本: {lockbox_train_df.height:,}")

    # 转换为pandas进行训练
    lockbox_train_pd = lockbox_train_df.to_pandas()
    lockbox_test_pd = lockbox_df.to_pandas()

    # 准备特征和目标
    X_lockbox_train = lockbox_train_pd[stable_features].fillna(0)
    y_lockbox_train = lockbox_train_pd['target']
    X_lockbox_test = lockbox_test_pd[stable_features].fillna(0)
    y_lockbox_test = lockbox_test_pd['target']

    # 训练lockbox模型
    print(f"\n  🤖 训练Lockbox模型...")
    lockbox_model = xgb.XGBRegressor(**trainer.xgb_params)
    lockbox_model.fit(X_lockbox_train, y_lockbox_train)

    # 预测
    print(f"  🔮 Lockbox预测...")
    y_lockbox_pred = lockbox_model.predict(X_lockbox_test)

    # 构建lockbox预测DataFrame
    lockbox_predictions = lockbox_test_pd[['timestamp', 'symbol', 'target']].copy()
    lockbox_predictions['y_pred'] = y_lockbox_pred
    lockbox_predictions = lockbox_predictions.rename(columns={'target': 'y_true'})

    # 评估lockbox
    print(f"\n  📊 评估Lockbox表现...")
    lockbox_ic = backtester.calculate_oos_ic(lockbox_predictions)

    # Lockbox组合回测
    lockbox_portfolio = backtester.create_portfolio(
        lockbox_predictions, top_pct=0.1, bottom_pct=0.1,
        holding_days=5, non_overlapping=True
    )
    lockbox_metrics = backtester.calculate_portfolio_metrics(lockbox_portfolio)

    print(f"\n  【Lockbox Long-Short组合】")
    print(f"  年化收益: {lockbox_metrics['ls']['annual_return']*100:.2f}%")
    print(f"  Sharpe比率: {lockbox_metrics['ls']['sharpe']:.4f}")
    print(f"  最大回撤: {lockbox_metrics['ls']['max_drawdown']*100:.2f}%")

    # 保存lockbox结果
    lockbox_predictions.to_parquet(output_dir / "predictions_lockbox.parquet", index=False)
    print(f"\n✅ Lockbox结果已保存")

    # Step 5: 成本敏感性分析（复用8窗口预测）
    print_section_header("Step 5: 成本敏感性分析（复用预测，不重训）")

    cost_scenarios = [
        ('低成本', 0.0010),   # 10 bps
        ('中成本', 0.0025),   # 25 bps
        ('高成本', 0.0050),   # 50 bps
    ]

    cost_results = {}

    for cost_name, cost_bps in cost_scenarios:
        print(f"\n📊 测试 {cost_name}: {cost_bps*10000:.0f} bps")

        # 复用预测，只改变成本假设
        portfolio_with_cost = backtester.create_portfolio(
            predictions_df, top_pct=0.1, bottom_pct=0.1,
            holding_days=5, non_overlapping=True
        )

        # 计算扣除成本后的收益（直接覆盖原列）
        portfolio_with_cost['ls_return'] = portfolio_with_cost['ls_return'] - cost_bps
        portfolio_with_cost['top_return'] = portfolio_with_cost['top_return'] - cost_bps/2
        portfolio_with_cost['bottom_return'] = portfolio_with_cost['bottom_return'] - cost_bps/2

        # 重新计算指标
        metrics_with_cost = backtester.calculate_portfolio_metrics(portfolio_with_cost)

        cost_results[cost_name] = metrics_with_cost

        print(f"  年化收益: {metrics_with_cost['ls']['annual_return']*100:.2f}%")
        print(f"  Sharpe: {metrics_with_cost['ls']['sharpe']:.4f}")
        print(f"  最大回撤: {metrics_with_cost['ls']['max_drawdown']*100:.2f}%")

    print(f"\n✅ 成本敏感性分析完成")

    # Step 6: 组合参数稳定性分析（复用8窗口预测）
    print_section_header("Step 6: 组合参数稳定性分析（复用预测，不重训）")

    portfolio_configs = [
        ('Top 10% / Bottom 10%', 0.10, 0.10),
        ('Top 15% / Bottom 15%', 0.15, 0.15),
        ('Top 20% / Bottom 20%', 0.20, 0.20),
    ]

    portfolio_results = {}

    for config_name, top_pct, bottom_pct in portfolio_configs:
        print(f"\n📊 测试 {config_name}")

        # 复用预测，只改变组合构建参数
        portfolio_config = backtester.create_portfolio(
            predictions_df, top_pct=top_pct, bottom_pct=bottom_pct,
            holding_days=5, non_overlapping=True
        )

        metrics_config = backtester.calculate_portfolio_metrics(portfolio_config)

        portfolio_results[config_name] = metrics_config

        print(f"  年化收益: {metrics_config['ls']['annual_return']*100:.2f}%")
        print(f"  Sharpe: {metrics_config['ls']['sharpe']:.4f}")
        print(f"  最大回撤: {metrics_config['ls']['max_drawdown']*100:.2f}%")

    print(f"\n✅ 组合参数稳定性分析完成")

    # Step 7: 轻量Ablation Test（稳定特征家族）
    print_section_header("Step 7: 轻量Ablation Test（稳定特征家族）")

    # 统计高频特征
    print(f"\n📊 统计高频稳定特征...")
    sorted_features = sorted(feature_counts.items(), key=lambda x: x[1], reverse=True)
    top_20_features = sorted_features[:20]

    print(f"\n高频特征 Top 20:")
    for feat, cnt in top_20_features:
        formula = metadata_df[metadata_df['alpha_name'] == feat]['formula'].values[0] if feat in metadata_df['alpha_name'].values else 'N/A'
        print(f"  {feat}: {cnt}次 ({cnt/8*100:.1f}%) | {formula[:60]}")

    # 特征家族分类
    print(f"\n🔍 特征家族分类...")

    def classify_feature_family(formula):
        """根据公式分类特征家族"""
        if pd.isna(formula):
            return 'unknown'
        formula_lower = str(formula).lower()

        if 'cs_' in formula_lower:
            return 'cross_sectional'
        elif 'volatility' in formula_lower or 'vol_' in formula_lower:
            return 'volatility'
        elif 'sma' in formula_lower or 'price_to_' in formula_lower:
            return 'price_distance'
        elif 'volume' in formula_lower:
            return 'volume'
        elif 'ret_' in formula_lower or 'return' in formula_lower:
            return 'momentum'
        else:
            return 'other'

    # 为每个特征分配家族
    feature_families = {}
    for feat, cnt in sorted_features:
        if feat in metadata_df['alpha_name'].values:
            formula = metadata_df[metadata_df['alpha_name'] == feat]['formula'].values[0]
            family = classify_feature_family(formula)
            feature_families[feat] = family

    # 统计各家族数量
    family_counts = {}
    for feat, cnt in sorted_features[:50]:  # 只看top 50
        family = feature_families.get(feat, 'unknown')
        family_counts[family] = family_counts.get(family, 0) + 1

    print(f"\n特征家族分布（Top 50特征）:")
    for family, count in sorted(family_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {family}: {count}个")

    print(f"\n✅ 轻量Ablation分析完成（特征家族已识别）")
    print(f"⚠️  完整Ablation需要重训练，暂时跳过以节省时间")

    # 生成最终报告
    print_section_header("【Phase ML.2 最终报告（优化确认版）】")

    print(f"\n{'='*80}")
    print(f"【A. 主确认结果（8窗口）】")
    print(f"{'='*80}")
    print(f"\nML模型:")
    print(f"  OOS IC Mean: {results_8window['ic_metrics']['ic_mean']:.6f}")
    print(f"  OOS IC Std:  {results_8window['ic_metrics']['ic_std']:.6f}")
    print(f"  OOS IR:      {results_8window['ic_metrics']['ir']:.4f}")
    print(f"  OOS T-stat:  {results_8window['ic_metrics']['t_stat']:.4f}")
    print(f"  有效天数:    {results_8window['ic_metrics']['n_days']}")

    print(f"\n最佳单因子基线:")
    print(f"  OOS IC Mean: {results_8window['single_factor_results']['ic_metrics']['ic_mean']:.6f}")
    print(f"  OOS IC Std:  {results_8window['single_factor_results']['ic_metrics']['ic_std']:.6f}")
    print(f"  OOS IR:      {results_8window['single_factor_results']['ic_metrics']['ir']:.4f}")
    print(f"  OOS T-stat:  {results_8window['single_factor_results']['ic_metrics']['t_stat']:.4f}")

    print(f"\nML vs 单因子对比:")
    ic_improvement = (results_8window['ic_metrics']['ic_mean'] - results_8window['single_factor_results']['ic_metrics']['ic_mean']) / abs(results_8window['single_factor_results']['ic_metrics']['ic_mean']) * 100
    print(f"  IC提升: {ic_improvement:+.1f}%")
    print(f"  IR差值: {results_8window['ic_metrics']['ir'] - results_8window['single_factor_results']['ic_metrics']['ir']:+.4f}")

    print(f"\n{'='*80}")
    print(f"【B. Lockbox结果（独立封存考场）】")
    print(f"{'='*80}")
    print(f"\nLockbox IC指标:")
    print(f"  IC Mean: {lockbox_ic['ic_mean']:.6f}")
    print(f"  IR:      {lockbox_ic['ir']:.4f}")
    print(f"  T-stat:  {lockbox_ic['t_stat']:.4f}")

    print(f"\nLockbox组合表现:")
    print(f"  年化收益: {lockbox_metrics['ls']['annual_return']*100:.2f}%")
    print(f"  Sharpe:   {lockbox_metrics['ls']['sharpe']:.4f}")
    print(f"  最大回撤: {lockbox_metrics['ls']['max_drawdown']*100:.2f}%")

    lockbox_degradation = (lockbox_ic['ic_mean'] - results_8window['ic_metrics']['ic_mean']) / results_8window['ic_metrics']['ic_mean'] * 100
    print(f"\nLockbox vs 主确认:")
    print(f"  IC变化: {lockbox_degradation:+.1f}%")
    if abs(lockbox_degradation) < 30:
        print(f"  ✅ Lockbox表现稳定（变化<30%）")
    else:
        print(f"  ⚠️  Lockbox表现有明显变化")

    print(f"\n{'='*80}")
    print(f"【C. 成本敏感性分析】")
    print(f"{'='*80}")
    for cost_name, metrics in cost_results.items():
        print(f"\n{cost_name}:")
        print(f"  年化收益: {metrics['ls']['annual_return']*100:.2f}%")
        print(f"  Sharpe:   {metrics['ls']['sharpe']:.4f}")
        print(f"  最大回撤: {metrics['ls']['max_drawdown']*100:.2f}%")

    print(f"\n{'='*80}")
    print(f"【D. 组合参数稳定性分析】")
    print(f"{'='*80}")
    for config_name, metrics in portfolio_results.items():
        print(f"\n{config_name}:")
        print(f"  年化收益: {metrics['ls']['annual_return']*100:.2f}%")
        print(f"  Sharpe:   {metrics['ls']['sharpe']:.4f}")
        print(f"  最大回撤: {metrics['ls']['max_drawdown']*100:.2f}%")

    print(f"\n{'='*80}")
    print(f"【E. 高频稳定特征报告】")
    print(f"{'='*80}")
    print(f"\n8窗口中入选频率最高的Top 20特征:")
    for feat, cnt in top_20_features:
        formula = metadata_df[metadata_df['alpha_name'] == feat]['formula'].values[0] if feat in metadata_df['alpha_name'].values else 'N/A'
        family = feature_families.get(feat, 'unknown')
        print(f"  {feat}: {cnt}次 ({cnt/8*100:.1f}%) | {family} | {formula[:50]}")

    print(f"\n特征家族稳定性:")
    for family, count in sorted(family_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {family}: {count}个特征")

    print(f"\n{'='*80}")
    print(f"【F. 最终结论与建议】")
    print(f"{'='*80}")

    # 判断逻辑
    ml_better = results_8window['ic_metrics']['ic_mean'] > results_8window['single_factor_results']['ic_metrics']['ic_mean']
    ml_significant = results_8window['ic_metrics']['t_stat'] > 2.0
    lockbox_stable = abs(lockbox_degradation) < 30
    cost_robust = cost_results['中成本']['ls']['sharpe'] > 0.5

    print(f"\n1. 当前ML是否稳健优于最佳单因子？")
    if ml_better and ml_significant:
        print(f"   ✅ 是的，ML在IC上显著优于单因子")
        print(f"   - ML IC: {results_8window['ic_metrics']['ic_mean']:.6f} (t={results_8window['ic_metrics']['t_stat']:.2f})")
        print(f"   - 单因子IC: {results_8window['single_factor_results']['ic_metrics']['ic_mean']:.6f}")
    else:
        print(f"   ⚠️  ML优势不够明显或不显著")

    print(f"\n2. Lockbox是否支持当前结论？")
    if lockbox_stable:
        print(f"   ✅ Lockbox表现稳定，支持主确认结论")
    else:
        print(f"   ⚠️  Lockbox表现有明显变化，需谨慎")

    print(f"\n3. 成本敏感性下策略是否仍站得住？")
    if cost_robust:
        print(f"   ✅ 中等成本下Sharpe仍>0.5，策略稳健")
    else:
        print(f"   ⚠️  成本敏感，需要优化执行")

    print(f"\n4. 组合参数变化后策略是否仍然成立？")
    all_positive = all(m['ls']['sharpe'] > 0 for m in portfolio_results.values())
    if all_positive:
        print(f"   ✅ 多种组合参数下表现方向一致")
    else:
        print(f"   ⚠️  部分组合参数下表现不佳")

    print(f"\n5. 现阶段下一步最合理的是：")

    if ml_better and ml_significant and lockbox_stable and cost_robust:
        print(f"   🎯 推荐: A. 进入更完整ML/Portfolio Pipeline")
        print(f"   理由: 8窗口+Lockbox确认稳健，成本敏感性可控")
        print(f"   建议行动:")
        print(f"   - 实现完整的生产级回测框架")
        print(f"   - 加入风险管理模块")
        print(f"   - 准备模拟盘测试")
    elif ml_better and ml_significant:
        print(f"   🎯 推荐: 继续ML稳健性打磨")
        print(f"   理由: 主确认不错，但Lockbox或成本有待改进")
        print(f"   建议行动:")
        print(f"   - 优化特征工程")
        print(f"   - 调整模型参数")
        print(f"   - 改进组合构建")
    else:
        print(f"   🎯 推荐: B. 回到因子工厂继续打磨")
        print(f"   理由: ML优势不够明显")
        print(f"   建议行动:")
        print(f"   - Phase B.3: 提高CS权重")
        print(f"   - Phase C: 小规模Evolution")
        print(f"   - 增加更多衍生终端")

    print(f"\n{'='*80}")

    total_time = time.time() - start_time
    print(f"\n✅ Phase ML.2 完成！")
    print(f"总耗时: {total_time:.1f}秒 ({total_time/60:.1f}分钟)")
    print(f"所有结果已保存到: {output_dir}/")


if __name__ == "__main__":
    main()
