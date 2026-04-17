"""
Feature Dataset Builder - Phase ML.1

基于冻结的Phase B.2 Alpha Factory生成Alpha特征矩阵
严格要求：
1. 使用冻结版B.2 Alpha Factory
2. 不做任何全样本筛选
3. 输出标准长表格式
"""

import polars as pl
import pandas as pd
import numpy as np
import random
import time
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from alpha_factory.ast_generator import ASTGenerator
from alpha_factory.polars_compiler import PolarsCompiler
from alpha_factory.operator_library import (
    build_derived_terminal_exprs,
    build_terminals_by_type,
    DERIVED_TERMINALS
)
from runtime_paths import get_price_lake_glob


class FeatureDatasetBuilder:
    def __init__(self, data_path, n_alphas=2000, max_depth=4, seed=42):
        """
        初始化特征数据集构建器

        Args:
            data_path: 数据路径
            n_alphas: 生成Alpha数量
            max_depth: AST最大深度
            seed: 随机种子
        """
        self.data_path = data_path
        self.n_alphas = n_alphas
        self.max_depth = max_depth
        self.seed = seed
        random.seed(seed)

        print(f"🔥 ML Feature Mining Phase ML.1 - Feature Dataset Builder")
        print(f"📊 加载数据: {data_path}")
        self.df = pl.scan_parquet(data_path).collect()
        print(f"✅ 数据加载完成: {self.df.height} 行 × {self.df.width} 列")
        print(f"📈 股票数量: {self.df.select('symbol').n_unique()}")

        # 构建衍生终端
        print(f"\n🧬 构建Phase B.2衍生终端...")
        build_derived_terminal_exprs()
        print(f"✅ 衍生终端: {len(DERIVED_TERMINALS)} 个")

        # 物化衍生终端到DataFrame
        print(f"🧬 物化衍生终端列...")
        derived_cols = {name: expr for name, (expr, dtype) in DERIVED_TERMINALS.items()}
        self.df = self.df.with_columns(**derived_cols)
        print(f"✅ DataFrame扩展完成: {self.df.height} 行 × {self.df.width} 列")

        # 构建终端池
        self.terminals_by_type = build_terminals_by_type()

        # 创建生成器和编译器
        self.generator = ASTGenerator(
            max_depth=max_depth,
            seed=seed,
            terminals_by_type=self.terminals_by_type
        )
        self.compiler = PolarsCompiler()

        # 添加target列（未来5日收益率）
        print(f"\n🎯 构建target变量（未来5日收益率）...")
        self.df = self.df.with_columns([
            (pl.col("close").shift(-5).over("symbol") / pl.col("close") - 1).alias("target_5d")
        ])
        print(f"✅ Target变量构建完成")

    def generate_alpha_features(self):
        """
        生成Alpha特征矩阵

        Returns:
            feature_df: 特征DataFrame (timestamp, symbol, target, alpha_0001, ...)
            metadata_df: 元数据DataFrame (alpha_name, formula, ...)
        """
        print(f"\n{'='*60}")
        print(f"🧬 开始生成 {self.n_alphas} 个Alpha特征...")
        print(f"{'='*60}")

        start_time = time.time()
        alpha_features = {}
        metadata_records = []
        compile_success = 0

        for i in range(self.n_alphas):
            alpha_name = f"alpha_{i:04d}"

            # 生成AST
            ast = self.generator.generate()
            formula = self.generator.to_string(ast)

            # 编译为Polars表达式
            expr = self.compiler.compile(ast)
            if expr is None:
                continue

            # 计算Alpha值
            try:
                alpha_series = self.df.select([
                    pl.col("timestamp"),
                    pl.col("symbol"),
                    expr.alias(alpha_name)
                ])

                # 检查是否有有效值
                if alpha_series.select(pl.col(alpha_name).is_not_null().sum()).item() == 0:
                    continue

                # 保存特征
                alpha_features[alpha_name] = alpha_series

                # 保存元数据
                metadata_records.append({
                    "alpha_name": alpha_name,
                    "formula": formula,
                    "generation_order": i
                })

                compile_success += 1

                if (i + 1) % 500 == 0:
                    print(f"  ⏳ 进度: {i + 1}/{self.n_alphas} | 编译成功: {compile_success}")

            except Exception as e:
                continue

        elapsed = time.time() - start_time
        print(f"\n✅ Alpha生成完成: {compile_success}/{self.n_alphas} 成功")
        print(f"⏱️  总耗时: {elapsed:.1f}秒")

        # 构建特征矩阵
        print(f"\n🔧 构建特征矩阵...")

        # 从第一个Alpha开始
        feature_df = self.df.select([
            pl.col("timestamp"),
            pl.col("symbol"),
            pl.col("target_5d").alias("target")
        ])

        # 逐个join Alpha特征
        for alpha_name, alpha_data in alpha_features.items():
            feature_df = feature_df.join(
                alpha_data,
                on=["timestamp", "symbol"],
                how="left"
            )

        # 按时间排序
        feature_df = feature_df.sort(["timestamp", "symbol"])

        # 构建元数据DataFrame
        metadata_df = pd.DataFrame(metadata_records)

        print(f"✅ 特征矩阵构建完成: {feature_df.height} 行 × {feature_df.width} 列")
        print(f"✅ 元数据构建完成: {len(metadata_df)} 个Alpha")

        return feature_df, metadata_df

    def save_features(self, feature_df, metadata_df, output_dir="data/feature_store"):
        """
        保存特征矩阵和元数据

        Args:
            feature_df: 特征DataFrame
            metadata_df: 元数据DataFrame
            output_dir: 输出目录
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"\n💾 保存特征数据...")

        # 保存特征矩阵
        feature_path = output_path / "ml_alpha_matrix.parquet"
        feature_df.write_parquet(feature_path)
        print(f"✅ 特征矩阵已保存: {feature_path}")

        # 保存元数据
        metadata_path = output_path / "ml_alpha_metadata.parquet"
        metadata_df.to_parquet(metadata_path, index=False)
        print(f"✅ 元数据已保存: {metadata_path}")

        # 输出统计信息
        print(f"\n{'='*60}")
        print(f"【特征数据集统计】")
        print(f"{'='*60}")
        print(f"数据行数: {feature_df.height:,}")
        print(f"股票数量: {feature_df.select('symbol').n_unique()}")
        print(f"时间跨度: {feature_df.select('timestamp').min().item()} 至 {feature_df.select('timestamp').max().item()}")
        print(f"Alpha特征数量: {len(metadata_df)}")
        print(f"特征列数: {feature_df.width - 3}")  # 减去timestamp, symbol, target
        print(f"{'='*60}")


if __name__ == "__main__":
    # 构建特征数据集
    builder = FeatureDatasetBuilder(
        data_path=get_price_lake_glob(),
        n_alphas=2000,
        max_depth=4,
        seed=42
    )

    # 生成Alpha特征
    feature_df, metadata_df = builder.generate_alpha_features()

    # 保存特征
    builder.save_features(feature_df, metadata_df)
