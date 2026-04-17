import polars as pl
import numpy as np

class FitnessEvaluator:
    def __init__(self, df):
        self.df = df

    def evaluate(self, factor_expr, factor_name):
        try:
            # 计算因子值（不fill_null）
            df_with_factor = self.df.with_columns(factor_expr.alias(factor_name))

            # 计算目标收益率（5日后收益）
            df_with_factor = df_with_factor.with_columns(
                ((pl.col("close").shift(-5) / pl.col("close") - 1).over("symbol")).alias("target_5d")
            )

            # 计算每日横截面IC（Spearman相关性）
            daily_ic = df_with_factor.group_by("timestamp").agg(
                pl.corr(factor_name, "target_5d", method="spearman").alias("ic")
            )

            # 统一drop_nulls处理
            daily_ic = daily_ic.filter(pl.col("ic").is_not_null() & pl.col("ic").is_not_nan())

            if daily_ic.height < 50:
                return 0.0

            # 计算IC均值
            ic_mean = daily_ic.select(pl.col("ic").mean()).item()
            return ic_mean if not np.isnan(ic_mean) else 0.0

        except Exception:
            return 0.0

    def evaluate_full_stats(self, factor_expr, factor_name):
        """返回完整统计信息（用于最终报告）"""
        try:
            df_with_factor = self.df.with_columns(factor_expr.alias(factor_name))
            df_with_factor = df_with_factor.with_columns(
                ((pl.col("close").shift(-5) / pl.col("close") - 1).over("symbol")).alias("target_5d")
            )

            daily_ic = df_with_factor.group_by("timestamp").agg(
                pl.corr(factor_name, "target_5d", method="spearman").alias("ic")
            )
            daily_ic = daily_ic.filter(pl.col("ic").is_not_null() & pl.col("ic").is_not_nan())

            if daily_ic.height < 50:
                return None

            ic_series = daily_ic.select("ic").to_series().to_numpy()
            return {
                "count": len(ic_series),
                "mean": np.mean(ic_series),
                "std": np.std(ic_series),
                "min": np.min(ic_series),
                "p95": np.percentile(ic_series, 95),
                "p99": np.percentile(ic_series, 99),
                "max": np.max(ic_series)
            }
        except Exception:
            return None
