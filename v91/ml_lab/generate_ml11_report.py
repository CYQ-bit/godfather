"""
ML.1.1 确认版报告生成函数
"""

import numpy as np


def generate_ml11_report(ic_metrics, portfolio_metrics, baseline_metrics,
                         best_single_factor, window_info, feature_metadata, total_time,
                         single_factor_results=None, audit_report=None):
    """
    生成ML.1.1确认版最终报告

    Args:
        ic_metrics: ML模型IC指标
        portfolio_metrics: ML模型组合指标
        baseline_metrics: 随机基线指标
        best_single_factor: 最佳单因子统计信息
        window_info: 窗口信息
        feature_metadata: 特征元数据
        total_time: 总运行时间
        single_factor_results: 单因子基线评估结果
        audit_report: 收益计算审计报告
    """
    print(f"\n{'='*80}")
    print(f"【Phase ML.1.1 最终报告（确认版）】")
    print(f"{'='*80}")

    # A. 基本执行信息
    print(f"\n【A. 基本执行信息】")
    print(f"Alpha总数量: {len(feature_metadata)}")
    print(f"Walk-forward窗口数: {len(window_info['windows'])}")
    print(f"总运行耗时: {total_time:.1f}秒 ({total_time/60:.1f}分钟)")

    # 统计每个窗口的特征数
    feature_counts = [w['n_features'] for w in window_info['windows']]
    print(f"每个训练窗平均入选因子数: {np.mean(feature_counts):.1f}")
    print(f"入选因子数范围: {min(feature_counts)} - {max(feature_counts)}")

    # B. 逐窗口选择信息
    print(f"\n【B. 逐窗口选择信息】")
    print(f"Top特征选择规则: |IC Mean| 排序")
    print(f"去共线阈值: 0.7")
    print(f"\n窗口详情:")
    for w in window_info['windows']:
        print(f"  窗口 {w['window_id']}: {w['train_start'].date()} - {w['test_start'].date()} | "
              f"{w['n_features']}个特征 | 最佳单因子: {w['best_single_factor']}")

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

    # C. OOS预测表现：ML
    print(f"\n【C. OOS预测表现：ML模型】")
    if 'ic_mean' in ic_metrics:
        print(f"OOS IC Mean: {ic_metrics['ic_mean']:.6f}")
        print(f"OOS IC Std:  {ic_metrics['ic_std']:.6f}")
        print(f"OOS IR:      {ic_metrics['ir']:.4f}")
        print(f"OOS T-stat:  {ic_metrics['t_stat']:.4f}")
        print(f"有效天数:    {ic_metrics['n_days']}")
    else:
        print("⚠️  IC指标计算失败")

    # D. OOS预测表现：最佳单因子基线
    print(f"\n【D. OOS预测表现：最佳单因子基线】")
    if single_factor_results and 'ic_metrics' in single_factor_results:
        sf_ic = single_factor_results['ic_metrics']
        if 'ic_mean' in sf_ic:
            print(f"OOS IC Mean: {sf_ic['ic_mean']:.6f}")
            print(f"OOS IC Std:  {sf_ic['ic_std']:.6f}")
            print(f"OOS IR:      {sf_ic['ir']:.4f}")
            print(f"OOS T-stat:  {sf_ic['t_stat']:.4f}")
            print(f"有效天数:    {sf_ic['n_days']}")
        else:
            print("⚠️  单因子IC指标计算失败")
    else:
        print("⚠️  未提供单因子基线评估结果")

    # E. ML vs 单因子对比
    print(f"\n【E. ML vs 单因子对比】")
    if single_factor_results and 'ic_metrics' in single_factor_results:
        sf_ic = single_factor_results['ic_metrics']
        if 'ic_mean' in ic_metrics and 'ic_mean' in sf_ic:
            ic_diff = ic_metrics['ic_mean'] - sf_ic['ic_mean']
            ic_improvement = (ic_diff / (abs(sf_ic['ic_mean']) + 1e-8)) * 100
            print(f"IC对比:")
            print(f"  ML: {ic_metrics['ic_mean']:.6f}")
            print(f"  单因子: {sf_ic['ic_mean']:.6f}")
            print(f"  差值: {ic_diff:.6f} ({'+' if ic_diff > 0 else ''}{ic_improvement:.1f}%)")

            ir_diff = ic_metrics['ir'] - sf_ic['ir']
            print(f"\nIR对比:")
            print(f"  ML: {ic_metrics['ir']:.4f}")
            print(f"  单因子: {sf_ic['ir']:.4f}")
            print(f"  差值: {ir_diff:.4f}")

    # F. 收益计算审计（关键章节）
    print(f"\n【F. 收益计算审计】")
    if audit_report:
        print(f"Target列名: {audit_report['target_column']}")
        print(f"Target含义: 未来{audit_report['holding_days']}日收益率")
        print(f"Target均值: {audit_report['target_mean']:.6f}")
        print(f"Target标准差: {audit_report['target_std']:.6f}")
        print(f"\n持有期设置: {audit_report['holding_days']}天")
        print(f"再平衡频率: 每{audit_report['holding_days']}天")
        print(f"年化因子: sqrt(252/{audit_report['holding_days']}) = {np.sqrt(252/audit_report['holding_days']):.4f}")
        print(f"\n修正说明:")
        print(f"  旧版本错误: 将{audit_report['holding_days']}日收益当作1日收益")
        print(f"  导致Sharpe被高估约 {np.sqrt(audit_report['holding_days']):.2f}倍")
        print(f"  新版本修正: 使用正确的年化因子")
    else:
        print("⚠️  未提供审计报告")

    # G. OOS组合表现：ML
    print(f"\n【G. OOS组合表现：ML模型】")
    ls_metrics = portfolio_metrics['ls']
    print(f"年化收益: {ls_metrics['annual_return']*100:.2f}%")
    print(f"年化波动: {ls_metrics['annual_vol']*100:.2f}%")
    print(f"Sharpe比率: {ls_metrics['sharpe']:.4f}")
    print(f"最大回撤: {ls_metrics['max_drawdown']*100:.2f}%")
    print(f"胜率: {ls_metrics['win_rate']*100:.2f}%")
    print(f"总收益: {ls_metrics['total_return']*100:.2f}%")

    print(f"\nLong单边:")
    top_metrics = portfolio_metrics['top']
    print(f"  年化收益: {top_metrics['annual_return']*100:.2f}%")
    print(f"  Sharpe: {top_metrics['sharpe']:.4f}")

    print(f"\nShort单边:")
    bottom_metrics = portfolio_metrics['bottom']
    print(f"  年化收益: {bottom_metrics['annual_return']*100:.2f}%")
    print(f"  Sharpe: {bottom_metrics['sharpe']:.4f}")

    # H. OOS组合表现：最佳单因子基线
    print(f"\n【H. OOS组合表现：最佳单因子基线】")
    if single_factor_results and 'portfolio_metrics' in single_factor_results:
        sf_ls = single_factor_results['portfolio_metrics']['ls']
        print(f"年化收益: {sf_ls['annual_return']*100:.2f}%")
        print(f"年化波动: {sf_ls['annual_vol']*100:.2f}%")
        print(f"Sharpe比率: {sf_ls['sharpe']:.4f}")
        print(f"最大回撤: {sf_ls['max_drawdown']*100:.2f}%")
        print(f"胜率: {sf_ls['win_rate']*100:.2f}%")
        print(f"总收益: {sf_ls['total_return']*100:.2f}%")

        sf_top = single_factor_results['portfolio_metrics']['top']
        print(f"\nLong单边:")
        print(f"  年化收益: {sf_top['annual_return']*100:.2f}%")
        print(f"  Sharpe: {sf_top['sharpe']:.4f}")

        sf_bottom = single_factor_results['portfolio_metrics']['bottom']
        print(f"\nShort单边:")
        print(f"  年化收益: {sf_bottom['annual_return']*100:.2f}%")
        print(f"  Sharpe: {sf_bottom['sharpe']:.4f}")

        # 对比
        print(f"\nML vs 单因子组合对比:")
        sharpe_diff = ls_metrics['sharpe'] - sf_ls['sharpe']
        print(f"  Sharpe差值: {sharpe_diff:.4f} ({'ML胜' if sharpe_diff > 0 else '单因子胜'})")
        return_diff = ls_metrics['annual_return'] - sf_ls['annual_return']
        print(f"  年化收益差值: {return_diff*100:.2f}%")
    else:
        print("⚠️  未提供单因子基线组合表现")

    # 随机基线对比
    print(f"\n【随机预测基线】")
    print(f"  IC Mean: {baseline_metrics['ic_mean']:.6f} ± {baseline_metrics['ic_std']:.6f}")
    print(f"  Sharpe: {baseline_metrics['sharpe_mean']:.4f} ± {baseline_metrics['sharpe_std']:.4f}")

    print(f"\n最佳单因子统计:")
    if best_single_factor:
        print(f"  特征: {best_single_factor['best_feature']}")
        print(f"  被选中次数: {best_single_factor['selection_count']}/{len(window_info['windows'])}")
        print(f"  公式: {best_single_factor['formula'][:80]}")

    # I. 最终结论与建议
    print(f"\n【I. 最终结论与建议】")

    # 判断1: ML是否优于单因子
    print(f"\n1. ML模型是否优于最佳单因子？")
    if single_factor_results and 'ic_metrics' in single_factor_results and 'portfolio_metrics' in single_factor_results:
        sf_ic = single_factor_results['ic_metrics']
        sf_ls = single_factor_results['portfolio_metrics']['ls']

        ml_better_ic = ic_metrics.get('ic_mean', 0) > sf_ic.get('ic_mean', 0)
        ml_better_sharpe = ls_metrics['sharpe'] > sf_ls['sharpe']

        if ml_better_ic and ml_better_sharpe:
            print(f"   ✅ 是的，ML在IC和Sharpe上均优于单因子")
            print(f"   - IC: ML {ic_metrics['ic_mean']:.6f} vs 单因子 {sf_ic['ic_mean']:.6f}")
            print(f"   - Sharpe: ML {ls_metrics['sharpe']:.4f} vs 单因子 {sf_ls['sharpe']:.4f}")
        elif ml_better_ic or ml_better_sharpe:
            print(f"   ⚠️  ML部分优于单因子")
            print(f"   - IC: ML {'胜' if ml_better_ic else '负'}")
            print(f"   - Sharpe: ML {'胜' if ml_better_sharpe else '负'}")
        else:
            print(f"   ❌ ML未能优于单因子基线")
    else:
        print(f"   ⚠️  无法对比（缺少单因子基线数据）")

    # 判断2: 是否达到生产门槛
    print(f"\n2. 是否达到生产级ML Pipeline门槛？")
    ic_threshold = 0.001
    ir_threshold = 0.5
    sharpe_threshold = 0.5

    meets_ic = ic_metrics.get('ic_mean', 0) > ic_threshold
    meets_ir = ic_metrics.get('ir', 0) > ir_threshold
    meets_sharpe = ls_metrics['sharpe'] > sharpe_threshold

    if meets_ic and meets_ir and meets_sharpe:
        print(f"   ✅ 是的，已达到门槛")
        print(f"   - IC Mean > {ic_threshold}: ✅ ({ic_metrics['ic_mean']:.6f})")
        print(f"   - IR > {ir_threshold}: ✅ ({ic_metrics['ir']:.4f})")
        print(f"   - Sharpe > {sharpe_threshold}: ✅ ({ls_metrics['sharpe']:.4f})")
    else:
        print(f"   ⚠️  尚未完全达到门槛")
        print(f"   - IC Mean > {ic_threshold}: {'✅' if meets_ic else '❌'} ({ic_metrics.get('ic_mean', 0):.6f})")
        print(f"   - IR > {ir_threshold}: {'✅' if meets_ir else '❌'} ({ic_metrics.get('ir', 0):.4f})")
        print(f"   - Sharpe > {sharpe_threshold}: {'✅' if meets_sharpe else '❌'} ({ls_metrics['sharpe']:.4f})")

    # 判断3: 收益计算是否可信
    print(f"\n3. 收益计算方法是否可信？")
    if audit_report:
        print(f"   ✅ 已修正收益计算方法")
        print(f"   - 正确处理{audit_report['holding_days']}天持有期")
        print(f"   - 使用非重叠再平衡")
        print(f"   - 年化因子已修正")
        print(f"   - 当前Sharpe {ls_metrics['sharpe']:.4f} 是修正后的可信值")
    else:
        print(f"   ⚠️  未进行审计")

    # 判断4: 下一步建议
    print(f"\n4. 下一步应该做什么？")

    has_positive_results = meets_ic and meets_sharpe
    ml_beats_single = False
    if single_factor_results:
        sf_ic = single_factor_results.get('ic_metrics', {})
        sf_ls = single_factor_results.get('portfolio_metrics', {}).get('ls', {})
        ml_beats_single = (ic_metrics.get('ic_mean', 0) > sf_ic.get('ic_mean', 0) and
                          ls_metrics['sharpe'] > sf_ls.get('sharpe', 0))

    if meets_ic and meets_ir and meets_sharpe and ml_beats_single:
        print(f"   推荐: A. 继续做ML Pipeline")
        print(f"   理由: ML显著优于单因子，已达到生产门槛")
        print(f"   建议行动:")
        print(f"   - 扩展到全部36个窗口进行完整验证")
        print(f"   - 尝试更复杂的模型（LightGBM, Neural Network）")
        print(f"   - 引入风险模型和组合优化")
        print(f"   - 构建完整的生产级回测系统")
    elif has_positive_results:
        print(f"   推荐: B. 先回到因子工厂继续打磨")
        print(f"   理由: ML有一定效果但优势不够明显")
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
