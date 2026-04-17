import polars as pl
from .operator_library import FAST_OPERATOR_REGISTRY, TERMINALS, DERIVED_TERMINALS, Domain

class PolarsCompiler:
    def __init__(self):
        self.op_map = {op.name: op for op in FAST_OPERATOR_REGISTRY}

    def compile(self, ast_node):
        try:
            expr = self._compile_node(ast_node)
            return expr
        except Exception:
            return None

    def _compile_node(self, node):
        if node.op == "terminal":
            return pl.col(node.value)
        elif node.op == "derived_terminal":
            # Phase B.2: 衍生终端已物化到DataFrame，直接读取列
            return pl.col(node.value)
        elif node.op == "const":
            return pl.lit(node.value)

        op = self.op_map.get(node.op)
        if not op:
            raise ValueError(f"Unknown operator: {node.op}")

        if op.arity == 1:
            child_expr = self._compile_node(node.children[0])
            result = op.func(child_expr)
        elif op.arity == 2:
            left_expr = self._compile_node(node.children[0])
            if node.children[1].op == "const":
                right_val = node.children[1].value
                result = op.func(left_expr, right_val)
            else:
                right_expr = self._compile_node(node.children[1])
                result = op.func(left_expr, right_expr)
        else:
            raise ValueError(f"Invalid arity: {op.arity}")

        # 根据Domain应用正确的.over()
        if op.domain == Domain.TS:
            return result.over("symbol")
        elif op.domain == Domain.CS:
            return result.over("timestamp")
        else:  # POINTWISE
            return result
