import polars as pl
import pandas as pd
import numpy as np
import random
import time
from collections import Counter
from pathlib import Path
import sys
from .ast_generator import ASTGenerator, ASTNode
from .polars_compiler import PolarsCompiler
from .fitness_evaluator import FitnessEvaluator
from .operator_library import (
    build_derived_terminal_exprs,
    build_terminals_by_type,
    FAST_OPERATOR_REGISTRY,
    Domain,
    DERIVED_TERMINALS,
    RAW_TERMINALS
)

sys.path.append(str(Path(__file__).parent.parent))

from runtime_paths import get_price_lake_glob

class AlphaEngine:
    def __init__(self, data_path, n_alphas=5000, max_depth=4, seed=42):
        self.data_path = data_path
        self.n_alphas = n_alphas
        self.max_depth = max_depth
        self.seed = seed
        random.seed(seed)

        print(f"🔥 V9 Alpha Factory Phase B.2 (衍生终端扩展版) 点火中...")
        print(f"📊 加载标普500数据: {data_path}")
        self.df = pl.scan_parquet(data_path).collect()
        print(f"✅ 数据加载完成: {self.df.height} 行 × {self.df.width} 列")
        print(f"📈 股票数量: {self.df.select('symbol').n_unique()}")

        # Step A: 构建衍生终端表达式
        print(f"\n🧬 Step A: 构建衍生终端表达式...")
        build_derived_terminal_exprs()
        print(f"✅ 衍生终端定义完成: {len(DERIVED_TERMINALS)} 个")

        # Step A.1: 物化衍生终端列到DataFrame
        print(f"\n🧬 Step A.1: 物化衍生终端列到DataFrame...")
        derived_cols = {name: expr for name, (expr, dtype) in DERIVED_TERMINALS.items()}
        self.df = self.df.with_columns(**derived_cols)
        print(f"✅ DataFrame扩展完成: {self.df.height} 行 × {self.df.width} 列")

        # Step A.2: 验证衍生列存在
        print(f"\n🧬 Step A.2: 验证衍生列...")
        missing_cols = [name for name in DERIVED_TERMINALS.keys() if name not in self.df.columns]
        if missing_cols:
            raise ValueError(f"衍生列缺失: {missing_cols}")
        print(f"✅ 所有衍生列验证通过: {list(DERIVED_TERMINALS.keys())[:5]}... (共{len(DERIVED_TERMINALS)}个)")

        # Step B: 构建动态终端池
        print(f"\n🧬 Step B: 构建动态终端池...")
        self.terminals_by_type = build_terminals_by_type()

        # Step C: 自检
        print(f"\n{'='*60}")
        print(f"【自检报告】")
        print(f"{'='*60}")

        print(f"\n1. 原始终端 (RAW_TERMINALS):")
        for name, dtype in RAW_TERMINALS.items():
            print(f"   {name}: {dtype.value}")

        print(f"\n2. 衍生终端 (DERIVED_TERMINALS):")
        for name, (expr, dtype) in DERIVED_TERMINALS.items():
            print(f"   {name}: {dtype.value}")

        print(f"\n3. 按DType分组的终端池 (terminals_by_type):")
        for dtype, terms in self.terminals_by_type.items():
            print(f"   {dtype.value}:")
            for name, weight, term_type in terms:
                print(f"      {name} (weight={weight:.2f}, type={term_type})")

        print(f"\n4. 随机抽样测试 (20次):")
        test_generator = ASTGenerator(max_depth=4, seed=999, terminals_by_type=self.terminals_by_type)
        from .operator_library import DType
        sample_results = {"RETURN": [], "RATIO": [], "PRICE": [], "VOLUME": []}
        for _ in range(20):
            for dtype_name in ["RETURN", "RATIO", "PRICE", "VOLUME"]:
                dtype = DType[dtype_name]
                node = test_generator._terminal(expected_type=dtype)
                sample_results[dtype_name].append(node.value)

        for dtype_name, samples in sample_results.items():
            if samples:
                print(f"   {dtype_name}: {samples[:5]}")  # 只显示前5个

        print(f"{'='*60}\n")

        # Step D: 创建生成器（注入终端池）
        self.generator = ASTGenerator(
            max_depth=max_depth,
            seed=seed,
            terminals_by_type=self.terminals_by_type
        )
        self.compiler = PolarsCompiler()
        self.evaluator = FitnessEvaluator(self.df)

        # 构建operator domain映射
        self.op_domain_map = {op.name: op.domain for op in FAST_OPERATOR_REGISTRY}

    def _extract_ast_stats(self, node):
        """递归提取AST中的operator、terminal、domain"""
        operators = []
        terminals = []
        domains = []

        if node.op in ["terminal", "derived_terminal"]:
            terminals.append(node.value)
        elif node.op == "const":
            pass
        else:
            operators.append(node.op)
            if node.op in self.op_domain_map:
                domains.append(self.op_domain_map[node.op].value)

        for child in node.children:
            child_ops, child_terms, child_doms = self._extract_ast_stats(child)
            operators.extend(child_ops)
            terminals.extend(child_terms)
            domains.extend(child_doms)

        return operators, terminals, domains

    def run(self):
        print(f"\n{'='*60}")
        print(f"🎯 Phase B.2 (衍生终端扩展版) 配置")
        print(f"{'='*60}")
        print(f"Alpha目标数量: {self.n_alphas}")
        print(f"AST最大深度: {self.max_depth}")
        print(f"随机种子: {self.seed}")
        print(f"{'='*60}\n")

        start_time = time.time()
        results = []
        compile_success = 0
        all_operators = []
        all_terminals = []
        all_domains = []

        print(f"🧬 开始生成 {self.n_alphas} 个随机Alpha因子...")

        for i in range(self.n_alphas):
            ast = self.generator.generate()
            formula = self.generator.to_string(ast)

            # 提取AST统计
            ops, terms, doms = self._extract_ast_stats(ast)
            all_operators.extend(ops)
            all_terminals.extend(terms)
            all_domains.extend(doms)

            expr = self.compiler.compile(ast)
            if expr is None:
                continue

            compile_success += 1
            ic = self.evaluator.evaluate(expr, f"alpha_{i}")
            results.append({
                "alpha_id": i,
                "formula": formula,
                "ic": ic,
                "ast": ast,
                "operators": ops,
                "terminals": terms,
                "domains": doms
            })

            if (i + 1) % 500 == 0:
                print(f"  ⏳ 进度: {i + 1}/{self.n_alphas} | 编译成功: {compile_success}")

        elapsed = time.time() - start_time

        # 输出报告
        df_results = pd.DataFrame(results)
        ic_array = df_results['ic'].values

        # Top 1% (前50个)
        top50_indices = np.argsort(np.abs(ic_array))[-50:]
        top50_df = df_results.iloc[top50_indices]

        # Top 1%统计
        top50_operators = []
        top50_terminals = []
        top50_domains = []
        for _, row in top50_df.iterrows():
            top50_operators.extend(row['operators'])
            top50_terminals.extend(row['terminals'])
            top50_domains.extend(row['domains'])

        print(f"\n{'='*60}")
        print(f"【A. 基础执行信息】")
        print(f"{'='*60}")
        print(f"数据行数: {self.df.height}")
        print(f"股票数量: {self.df.select('symbol').n_unique()}")
        print(f"时间跨度: {self.df.select('timestamp').min().item()} 至 {self.df.select('timestamp').max().item()}")
        print(f"Alpha目标数量: {self.n_alphas}")
        print(f"Alpha编译成功数量: {compile_success}")
        print(f"编译成功率: {compile_success / self.n_alphas * 100:.1f}%")
        print(f"总运行耗时: {elapsed:.1f}秒")

        print(f"\n{'='*60}")
        print(f"【B. Null Distribution 报告】")
        print(f"{'='*60}")
        print(f"count: {len(ic_array)}")
        print(f"mean:  {np.mean(ic_array):.6f}")
        print(f"std:   {np.std(ic_array):.6f}")
        print(f"min:   {np.min(ic_array):.6f}")
        print(f"p95:   {np.percentile(ic_array, 95):.6f}")
        print(f"p99:   {np.percentile(ic_array, 99):.6f}")
        print(f"max:   {np.max(ic_array):.6f}")

        print(f"\n{'='*60}")
        print(f"【C. 全样本雷达】")
        print(f"{'='*60}")
        op_counter = Counter(all_operators)
        term_counter = Counter(all_terminals)
        dom_counter = Counter(all_domains)

        print(f"\nOperator Usage Top 20:")
        for op, count in op_counter.most_common(20):
            print(f"  {op}: {count}")

        print(f"\nTerminal Usage Top 20:")
        for term, count in term_counter.most_common(20):
            print(f"  {term}: {count}")

        print(f"\nDomain 占比:")
        total_doms = sum(dom_counter.values())
        for dom, count in dom_counter.most_common():
            print(f"  {dom}: {count} ({count/total_doms*100:.1f}%)")

        print(f"\n{'='*60}")
        print(f"【D. Top 1% Alpha 雷达】")
        print(f"{'='*60}")
        top_op_counter = Counter(top50_operators)
        top_term_counter = Counter(top50_terminals)
        top_dom_counter = Counter(top50_domains)

        print(f"\nTop 50 Operator Usage Top 20:")
        for op, count in top_op_counter.most_common(20):
            print(f"  {op}: {count}")

        print(f"\nTop 50 Terminal Usage Top 20:")
        for term, count in top_term_counter.most_common(20):
            print(f"  {term}: {count}")

        print(f"\nTop 50 Domain 占比:")
        total_top_doms = sum(top_dom_counter.values())
        for dom, count in top_dom_counter.most_common():
            print(f"  {dom}: {count} ({count/total_top_doms*100:.1f}%)")

        print(f"\nTop 10 Alpha:")
        top10 = df_results.iloc[np.argsort(np.abs(df_results['ic']))[-10:][::-1]]
        for _, row in top10.iterrows():
            print(f"  alpha_{row['alpha_id']}: IC={row['ic']:.6f} | {row['formula']}")

        print(f"{'='*60}")

        return df_results

if __name__ == "__main__":
    engine = AlphaEngine(
        data_path=get_price_lake_glob(),
        n_alphas=5000,
        max_depth=4,
        seed=42
    )
    engine.run()
