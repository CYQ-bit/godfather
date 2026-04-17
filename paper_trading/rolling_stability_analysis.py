"""
Rolling Stability Analysis - Godfather V9.0
Analyze 8-week rolling metrics for normal regime period
"""
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime


def load_daily_reports(reports_dir: Path, start_date: str):
    """Load all daily reports from start_date onwards"""
    reports = []

    for report_file in sorted(reports_dir.glob('*.json')):
        date = report_file.stem
        if date >= start_date:
            with open(report_file, 'r') as f:
                data = json.load(f)
                data['date'] = date
                reports.append(data)

    return reports


def calculate_rolling_metrics(reports: list, window: int = 8):
    """Calculate 8-week rolling metrics"""

    # Extract key metrics
    dates = []
    turnovers = []
    retained_list = []
    impl_shortfalls = []
    drift_warns = []
    regimes = []

    for r in reports:
        dates.append(r['date'])

        # Turnover
        portfolio_summary = r.get('portfolio_summary', {})
        if portfolio_summary.get('status') != 'No rebalance':
            turnovers.append(portfolio_summary.get('expected_turnover', 0))
            buffer_stats = portfolio_summary.get('buffer_stats', {})
            retained_list.append(buffer_stats.get('retained', 0))
        else:
            turnovers.append(None)
            retained_list.append(None)

        # Implementation shortfall
        exec_summary = r.get('execution_summary', {})
        if exec_summary.get('status') != 'No fills':
            impl_shortfalls.append(exec_summary.get('implementation_shortfall_abs_mean_bps', 0))
        else:
            impl_shortfalls.append(None)

        # Drift WARN
        drift_results = r.get('drift_results', {})
        drift_warns.append(1 if drift_results.get('drift_detected') else 0)

        # Regime
        regimes.append(r.get('regime', 'unknown'))

    # Create DataFrame
    df = pd.DataFrame({
        'date': dates,
        'turnover': turnovers,
        'retained': retained_list,
        'impl_shortfall': impl_shortfalls,
        'drift_warn': drift_warns,
        'regime': regimes
    })

    # Calculate rolling metrics
    df['rolling_turnover'] = df['turnover'].rolling(window=window, min_periods=1).mean()
    df['rolling_retained'] = df['retained'].rolling(window=window, min_periods=1).mean()
    df['rolling_impl_mean'] = df['impl_shortfall'].rolling(window=window, min_periods=1).mean()
    df['rolling_impl_p95'] = df['impl_shortfall'].rolling(window=window, min_periods=1).quantile(0.95)
    df['rolling_drift_warn_freq'] = df['drift_warn'].rolling(window=window, min_periods=1).mean()

    return df


def analyze_stability(df: pd.DataFrame, baseline_turnover: float = 0.4014):
    """Analyze stability trends"""

    # Debug: print regime distribution
    print(f"Debug: Total observations: {len(df)}")
    print(f"Debug: Regime distribution:")
    print(df['regime'].value_counts())
    print()

    # Filter for normal/high_vol regime only
    normal_df = df[df['regime'].isin(['normal', 'high_vol'])].copy()

    # If no normal regime data, use all data
    if len(normal_df) == 0:
        print("Warning: No normal/high_vol regime data found. Using all observations.")
        normal_df = df.copy()

    # Calculate ex-first turnover
    turnovers_clean = normal_df['turnover'].dropna()
    if len(turnovers_clean) > 1:
        ex_first_turnover = turnovers_clean.iloc[1:].mean()
    else:
        ex_first_turnover = turnovers_clean.mean() if len(turnovers_clean) > 0 else 0

    # Latest 8-week rolling metrics
    if len(normal_df) > 0:
        latest = normal_df.iloc[-1]
    else:
        latest = df.iloc[-1]

    # Stability metrics (coefficient of variation for last 16 weeks)
    recent_16w = normal_df.tail(16) if len(normal_df) >= 16 else normal_df

    turnover_cv = recent_16w['rolling_turnover'].std() / recent_16w['rolling_turnover'].mean() if recent_16w['rolling_turnover'].mean() > 0 else 0
    retained_cv = recent_16w['rolling_retained'].std() / recent_16w['rolling_retained'].mean() if recent_16w['rolling_retained'].mean() > 0 else 0
    impl_cv = recent_16w['rolling_impl_mean'].std() / recent_16w['rolling_impl_mean'].mean() if recent_16w['rolling_impl_mean'].mean() > 0 else 0

    return {
        'total_observations': len(df),
        'normal_observations': len(normal_df),
        'stress_observations': len(df[df['regime'] == 'stress']),
        'start_date': df['date'].iloc[0],
        'end_date': df['date'].iloc[-1],
        'ex_first_turnover': ex_first_turnover,
        'latest_rolling_turnover': latest['rolling_turnover'],
        'latest_rolling_retained': latest['rolling_retained'],
        'latest_rolling_impl_mean': latest['rolling_impl_mean'],
        'latest_rolling_impl_p95': latest['rolling_impl_p95'],
        'latest_rolling_drift_warn_freq': latest['rolling_drift_warn_freq'],
        'turnover_cv': turnover_cv,
        'retained_cv': retained_cv,
        'impl_cv': impl_cv,
        'baseline_turnover': baseline_turnover,
        'turnover_drift': ex_first_turnover - baseline_turnover
    }


def generate_report(analysis: dict):
    """Generate stability report"""

    print("=" * 80)
    print("【Godfather V9.0 - 常态期滚动稳定性分析报告】")
    print("=" * 80)
    print()

    print("【A. 观察覆盖】")
    print(f"  起止日期: {analysis['start_date']} 至 {analysis['end_date']}")
    print(f"  总观测点: {analysis['total_observations']}")
    print(f"  常态观测点: {analysis['normal_observations']}")
    print(f"  压力观测点: {analysis['stress_observations']}")
    print()

    print("【B. 8周滚动指标（最新）】")
    print(f"  Rolling ex-first-turnover: {analysis['latest_rolling_turnover']*100:.1f}%")
    print(f"  Rolling retained: {analysis['latest_rolling_retained']:.1f} stocks")
    print(f"  Rolling impl shortfall mean: {analysis['latest_rolling_impl_mean']:.1f} bps")
    print(f"  Rolling impl shortfall p95: {analysis['latest_rolling_impl_p95']:.1f} bps")
    print(f"  Rolling drift WARN frequency: {analysis['latest_rolling_drift_warn_freq']*100:.1f}%")
    print()

    print("【C. 稳定性判断】")
    print(f"  Turnover 变异系数: {analysis['turnover_cv']:.3f} ({'稳定' if analysis['turnover_cv'] < 0.2 else '波动'})")
    print(f"  Retained 变异系数: {analysis['retained_cv']:.3f} ({'稳定' if analysis['retained_cv'] < 0.2 else '波动'})")
    print(f"  Impl shortfall 变异系数: {analysis['impl_cv']:.3f} ({'稳定' if analysis['impl_cv'] < 0.3 else '波动'})")
    print()
    print(f"  Ex-first turnover: {analysis['ex_first_turnover']*100:.1f}%")
    print(f"  Baseline: {analysis['baseline_turnover']*100:.1f}%")
    print(f"  Drift: {analysis['turnover_drift']*100:+.1f} pct points")
    print()

    # Stability assessment
    is_turnover_stable = analysis['turnover_cv'] < 0.2
    is_retained_stable = analysis['retained_cv'] < 0.2
    is_impl_stable = analysis['impl_cv'] < 0.3
    is_near_baseline = abs(analysis['turnover_drift']) < 0.10  # Within 10 pct points

    stable_count = sum([is_turnover_stable, is_retained_stable, is_impl_stable])

    print(f"  稳定指标: {stable_count}/3")
    if is_turnover_stable:
        print(f"    ✅ Turnover 已稳定")
    else:
        print(f"    ⚠️  Turnover 仍在波动")

    if is_retained_stable:
        print(f"    ✅ Retained 已稳定")
    else:
        print(f"    ⚠️  Retained 仍在波动")

    if is_impl_stable:
        print(f"    ✅ Impl shortfall 已稳定")
    else:
        print(f"    ⚠️  Impl shortfall 仍在波动")
    print()

    print("【D. 最终结论】")
    print()

    # Question 1
    is_converging = stable_count >= 2 and abs(analysis['turnover_drift']) < abs(0.226)  # Better than previous 22.6pp
    print(f"  1. Godfather V9.0 在常态期是否继续收敛？")
    print(f"     {'✅ 是' if is_converging else '⚠️  部分收敛'}")
    print()

    # Question 2
    print(f"  2. turnover / retained / shortfall / drift WARN 是否趋于稳定？")
    if stable_count >= 2:
        print(f"     ✅ 多数指标已稳定")
    else:
        print(f"     ⚠️  仍需继续观察")
    print()

    # Question 3
    ready_for_pt4 = (stable_count >= 2 and
                     is_near_baseline and
                     analysis['latest_rolling_drift_warn_freq'] < 0.2)

    print(f"  3. 当前是否接近 PT.4 前的稳定门槛？")
    if ready_for_pt4:
        print(f"     ✅ 接近门槛")
    else:
        print(f"     ⚠️  尚未达到")
        if not is_near_baseline:
            print(f"        - Turnover 仍偏离 baseline")
        if analysis['latest_rolling_drift_warn_freq'] >= 0.2:
            print(f"        - Drift WARN 频率仍偏高")
    print()

    # Question 4
    print(f"  4. 下一步建议：")
    if ready_for_pt4:
        print(f"     → B. 准备 PT.4")
        print(f"        理由: 核心指标已稳定，接近 baseline")
    elif stable_count >= 2:
        print(f"     → A. 继续观察 (1-2 个月)")
        print(f"        理由: 稳定性良好，但需确认 turnover 收敛至 baseline")
    else:
        print(f"     → A. 继续观察 (2-3 个月)")
        print(f"        理由: 指标仍在波动，需更多数据确认稳定性")
    print()

    print("=" * 80)


def main():
    BASE_DIR = Path(__file__).parent.parent
    REPORTS_DIR = BASE_DIR / 'data' / 'paper_trading' / 'daily_reports'

    # Load reports from 2020-06-01 onwards (normal regime period)
    reports = load_daily_reports(REPORTS_DIR, start_date='2020-06-01')

    if len(reports) == 0:
        print("No reports found for normal regime period")
        return

    # Calculate rolling metrics
    df = calculate_rolling_metrics(reports, window=8)

    # Analyze stability
    analysis = analyze_stability(df)

    # Generate report
    generate_report(analysis)

    # Save detailed data
    output_file = BASE_DIR / 'data' / 'paper_trading' / 'rolling_stability_analysis.csv'
    df.to_csv(output_file, index=False)
    print(f"详细数据已保存: {output_file}")


if __name__ == '__main__':
    main()
