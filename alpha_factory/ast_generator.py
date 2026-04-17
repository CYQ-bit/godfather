import random
from .operator_library import FAST_OPERATOR_REGISTRY, DERIVED_TERMINALS, DType, Domain

class ASTNode:
    def __init__(self, op, children=None, value=None, dtype=None, domain=None):
        self.op = op
        self.children = children or []
        self.value = value
        self.dtype = dtype
        self.domain = domain

class ASTGenerator:
    def __init__(self, max_depth=4, seed=42, terminals_by_type=None):
        self.max_depth = max_depth
        random.seed(seed)
        self.cs_used = False
        self.ts_streak = 0
        self.parent_op_name = None

        # 接收运行时注入的终端池
        if terminals_by_type is None:
            raise ValueError("terminals_by_type must be provided!")
        self.terminals_by_type = terminals_by_type

    def generate(self):
        self.cs_used = False
        self.ts_streak = 0
        self.parent_op_name = None
        return self._grow(0, expected_type=DType.SIGNAL)

    def _grow(self, depth, expected_type=None):
        remaining_depth = self.max_depth - depth

        if depth >= self.max_depth:
            return self._terminal(expected_type)

        # 降低终端概率
        terminal_prob = 0.1 if depth < 2 else 0.2
        if random.random() < terminal_prob:
            return self._terminal(expected_type)

        # 【第一刀：CS顶层概率注入】
        cs_boost_prob = 0.0
        if remaining_depth == 4:  # root层
            cs_boost_prob = 0.35
        elif remaining_depth == 3:  # root-1层
            cs_boost_prob = 0.25

        # 筛选可用算子
        valid_ops = [op for op in FAST_OPERATOR_REGISTRY
                     if expected_type is None or op.output_type == expected_type]

        # CS算子只能在顶层（depth <= 1）
        if depth > 1:
            valid_ops = [op for op in valid_ops if op.domain != Domain.CS]

        # 每棵树最多一个CS算子
        if self.cs_used:
            valid_ops = [op for op in valid_ops if op.domain != Domain.CS]

        # 【第三刀：反同源2.0基因锁】
        # ts_streak >= 2时禁止TS算子
        if self.ts_streak >= 2:
            valid_ops = [op for op in valid_ops if op.domain != Domain.TS]

        # 禁止同算子连续
        if self.parent_op_name:
            valid_ops = [op for op in valid_ops if op.name != self.parent_op_name]

        # 禁止同家族连续（ts_returns和ts_delta）
        if self.parent_op_name in ["ts_returns", "ts_delta"]:
            valid_ops = [op for op in valid_ops if op.name not in ["ts_returns", "ts_delta"]]

        if not valid_ops:
            return self._terminal(expected_type)

        # CS顶层加权抽样
        if cs_boost_prob > 0 and random.random() < cs_boost_prob:
            cs_ops = [op for op in valid_ops if op.domain == Domain.CS]
            if cs_ops:
                op = random.choice(cs_ops)
            else:
                op = random.choice(valid_ops)
        else:
            op = random.choice(valid_ops)

        if op.domain == Domain.CS:
            self.cs_used = True

        # 保存父算子名和更新ts_streak
        old_parent = self.parent_op_name
        old_ts_streak = self.ts_streak
        self.parent_op_name = op.name
        if op.domain == Domain.TS:
            self.ts_streak += 1
        else:
            self.ts_streak = 0

        result = None
        if op.arity == 1:
            child = self._grow(depth + 1, expected_type=op.input_types[0] if len(op.input_types) == 1 else None)
            if child.dtype not in op.input_types:
                self.parent_op_name = old_parent
                self.ts_streak = old_ts_streak
                return self._terminal(expected_type)
            result = ASTNode(op.name, [child], dtype=op.output_type, domain=op.domain)

        elif op.arity == 2:
            if op.scalar_args:
                child = self._grow(depth + 1, expected_type=op.input_types[0] if len(op.input_types) == 1 else None)
                if child.dtype not in op.input_types:
                    self.parent_op_name = old_parent
                    self.ts_streak = old_ts_streak
                    return self._terminal(expected_type)
                scalar = random.choice(op.scalar_args)
                result = ASTNode(op.name, [child, ASTNode("const", value=scalar)], dtype=op.output_type, domain=op.domain)
            else:
                left = self._grow(depth + 1, expected_type=op.input_types[0] if len(op.input_types) == 1 else None)
                right = self._grow(depth + 1, expected_type=op.input_types[0] if len(op.input_types) == 1 else None)
                if left.dtype not in op.input_types or right.dtype not in op.input_types:
                    self.parent_op_name = old_parent
                    self.ts_streak = old_ts_streak
                    return self._terminal(expected_type)
                result = ASTNode(op.name, [left, right], dtype=op.output_type, domain=op.domain)

        self.parent_op_name = old_parent
        self.ts_streak = old_ts_streak
        return result if result else self._terminal(expected_type)

    def _terminal(self, expected_type=None):
        """【第二刀：80/20终端权重】使用运行时注入的终端池"""
        candidates = []
        weights = []

        # 从注入的终端池中收集候选
        if expected_type and expected_type in self.terminals_by_type:
            for name, weight, term_type in self.terminals_by_type[expected_type]:
                candidates.append((name, term_type))
                weights.append(weight)
        else:
            # 如果没有指定类型，从所有终端中收集
            for dtype, terms in self.terminals_by_type.items():
                for name, weight, term_type in terms:
                    candidates.append((name, term_type))
                    weights.append(weight)

        if not candidates:
            # 回退到PRICE类型
            if DType.PRICE in self.terminals_by_type:
                for name, weight, term_type in self.terminals_by_type[DType.PRICE]:
                    candidates.append((name, term_type))
                    weights.append(weight)
            else:
                # 最后回退
                return ASTNode("terminal", value="close", dtype=DType.PRICE)

        # 加权抽样
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]
        (name, term_type) = random.choices(candidates, weights=weights)[0]

        if term_type == "derived":
            dtype = DERIVED_TERMINALS[name][1]
            return ASTNode("derived_terminal", value=name, dtype=dtype)
        else:
            # 从RAW_TERMINALS推断dtype
            from .operator_library import RAW_TERMINALS
            dtype = RAW_TERMINALS.get(name, DType.PRICE)
            return ASTNode("terminal", value=name, dtype=dtype)

    def to_string(self, node):
        if node.op == "terminal" or node.op == "derived_terminal":
            return node.value
        elif node.op == "const":
            return str(node.value)
        elif len(node.children) == 1:
            return f"{node.op}({self.to_string(node.children[0])})"
        elif len(node.children) == 2:
            return f"{node.op}({self.to_string(node.children[0])}, {self.to_string(node.children[1])})"
        return "unknown"
