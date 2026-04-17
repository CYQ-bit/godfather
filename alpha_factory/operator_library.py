from enum import Enum
import polars as pl

class DType(Enum):
    PRICE = "price"
    VOLUME = "volume"
    RETURN = "return"
    RATIO = "ratio"
    SIGNAL = "signal"
    MASK = "mask"

class Domain(Enum):
    TS = "ts"
    CS = "cs"
    POINTWISE = "pointwise"

class Operator:
    def __init__(self, name, func, input_types, output_type, domain, arity, scalar_args=None):
        self.name = name
        self.func = func
        self.input_types = input_types
        self.output_type = output_type
        self.domain = domain
        self.arity = arity
        self.scalar_args = scalar_args or []

# FAST_OPERATOR_REGISTRY
FAST_OPERATOR_REGISTRY = [
    # TS算子（时序）
    Operator("ts_delta", lambda x, n: x - x.shift(n), [DType.PRICE], DType.RETURN, Domain.TS, 2, [5,10,20]),
    Operator("ts_returns", lambda x, n: x / x.shift(n) - 1, [DType.PRICE], DType.RETURN, Domain.TS, 2, [5,10,20]),
    Operator("ts_mean", lambda x, n: x.rolling_mean(n), [DType.RETURN, DType.RATIO], DType.SIGNAL, Domain.TS, 2, [5,10,20,60]),
    Operator("ts_std", lambda x, n: x.rolling_std(n), [DType.RETURN, DType.RATIO], DType.SIGNAL, Domain.TS, 2, [5,10,20,60]),
    Operator("ts_max", lambda x, n: x.rolling_max(n), [DType.RETURN, DType.RATIO], DType.SIGNAL, Domain.TS, 2, [5,10,20,60]),
    Operator("ts_min", lambda x, n: x.rolling_min(n), [DType.RETURN, DType.RATIO], DType.SIGNAL, Domain.TS, 2, [5,10,20,60]),
    Operator("ts_rank", lambda x, n: x.rank().over(pl.int_range(0, pl.len()).over("symbol") // n), [DType.RETURN], DType.SIGNAL, Domain.TS, 2, [5,10,20]),

    # CS算子（横截面）
    Operator("cs_rank", lambda x: x.rank(), [DType.RETURN, DType.RATIO, DType.SIGNAL], DType.SIGNAL, Domain.CS, 1),
    Operator("cs_zscore", lambda x: (x - x.mean()) / (x.std() + 1e-8), [DType.RETURN, DType.RATIO, DType.SIGNAL], DType.SIGNAL, Domain.CS, 1),

    # POINTWISE算子
    Operator("add", lambda x, y: x + y, [DType.RETURN, DType.RATIO, DType.SIGNAL], DType.SIGNAL, Domain.POINTWISE, 2),
    Operator("sub", lambda x, y: x - y, [DType.RETURN, DType.RATIO, DType.SIGNAL], DType.SIGNAL, Domain.POINTWISE, 2),
    Operator("mul", lambda x, y: x * y, [DType.RETURN, DType.RATIO, DType.SIGNAL], DType.SIGNAL, Domain.POINTWISE, 2),
    Operator("div", lambda x, y: x / (y.abs() + 1e-8), [DType.RETURN, DType.RATIO, DType.SIGNAL], DType.SIGNAL, Domain.POINTWISE, 2),
    Operator("abs", lambda x: x.abs(), [DType.RETURN, DType.RATIO, DType.SIGNAL], DType.SIGNAL, Domain.POINTWISE, 1),
    Operator("sign", lambda x: x.sign(), [DType.RETURN, DType.RATIO, DType.SIGNAL], DType.SIGNAL, Domain.POINTWISE, 1),
]

# 原始终端（10%权重 - Phase B.2压缩）
RAW_TERMINALS = {
    "close": DType.PRICE,
    "volume": DType.VOLUME,
}

RAW_TERMINAL_WEIGHTS = {
    "close": 0.08,
    "volume": 0.02,
}

# 衍生终端（80%权重）
DERIVED_TERMINALS = {}
DERIVED_TERMINAL_WEIGHTS = {}

def build_derived_terminal_exprs():
    """构建衍生终端节点（RETURN/RATIO类型）- Phase B.2 扩展版"""
    global DERIVED_TERMINALS, DERIVED_TERMINAL_WEIGHTS
    DERIVED_TERMINALS.clear()
    DERIVED_TERMINAL_WEIGHTS.clear()

    DERIVED_TERMINALS.update({
        # RETURN类型终端 (8个)
        "ret_1d": (pl.col("close") / pl.col("close").shift(1).over("symbol") - 1, DType.RETURN),
        "ret_3d": (pl.col("close") / pl.col("close").shift(3).over("symbol") - 1, DType.RETURN),
        "ret_5d": (pl.col("close") / pl.col("close").shift(5).over("symbol") - 1, DType.RETURN),
        "ret_7d": (pl.col("close") / pl.col("close").shift(7).over("symbol") - 1, DType.RETURN),
        "ret_10d": (pl.col("close") / pl.col("close").shift(10).over("symbol") - 1, DType.RETURN),
        "ret_15d": (pl.col("close") / pl.col("close").shift(15).over("symbol") - 1, DType.RETURN),
        "ret_20d": (pl.col("close") / pl.col("close").shift(20).over("symbol") - 1, DType.RETURN),
        "ret_30d": (pl.col("close") / pl.col("close").shift(30).over("symbol") - 1, DType.RETURN),

        # RATIO类型终端 - 成交量相关 (4个)
        "volume_ratio_5_20": (pl.col("volume") / (pl.col("volume").rolling_mean(20).over("symbol") + 1e-8), DType.RATIO),
        "volume_ratio_10_30": (pl.col("volume").rolling_mean(10).over("symbol") / (pl.col("volume").rolling_mean(30).over("symbol") + 1e-8), DType.RATIO),
        "volume_ratio_20_60": (pl.col("volume").rolling_mean(20).over("symbol") / (pl.col("volume").rolling_mean(60).over("symbol") + 1e-8), DType.RATIO),
        "volume_ratio_30_90": (pl.col("volume").rolling_mean(30).over("symbol") / (pl.col("volume").rolling_mean(90).over("symbol") + 1e-8), DType.RATIO),

        # RATIO类型终端 - 价格相关 (4个)
        "price_range_20d": ((pl.col("high").rolling_max(20).over("symbol") - pl.col("low").rolling_min(20).over("symbol")) / (pl.col("close") + 1e-8), DType.RATIO),
        "price_to_sma20": (pl.col("close") / (pl.col("close").rolling_mean(20).over("symbol") + 1e-8), DType.RATIO),
        "price_to_sma60": (pl.col("close") / (pl.col("close").rolling_mean(60).over("symbol") + 1e-8), DType.RATIO),
        "dist_vwap": (pl.col("close") / ((pl.col("close") * pl.col("volume")).rolling_sum(20).over("symbol") / (pl.col("volume").rolling_sum(20).over("symbol") + 1e-8) + 1e-8), DType.RATIO),

        # RATIO类型终端 - 波动率相关 (5个)
        "volatility_5d": ((pl.col("close") / pl.col("close").shift(1).over("symbol") - 1).rolling_std(5).over("symbol"), DType.RATIO),
        "volatility_10d": ((pl.col("close") / pl.col("close").shift(1).over("symbol") - 1).rolling_std(10).over("symbol"), DType.RATIO),
        "volatility_20d": ((pl.col("close") / pl.col("close").shift(1).over("symbol") - 1).rolling_std(20).over("symbol"), DType.RATIO),
        "vol_regime_5_20": ((pl.col("close") / pl.col("close").shift(1).over("symbol") - 1).rolling_std(5).over("symbol") / ((pl.col("close") / pl.col("close").shift(1).over("symbol") - 1).rolling_std(20).over("symbol") + 1e-8), DType.RATIO),
        "vol_regime_10_60": ((pl.col("close") / pl.col("close").shift(1).over("symbol") - 1).rolling_std(10).over("symbol") / ((pl.col("close") / pl.col("close").shift(1).over("symbol") - 1).rolling_std(60).over("symbol") + 1e-8), DType.RATIO),
    })

    DERIVED_TERMINAL_WEIGHTS.update({
        # RETURN类型权重 (总计0.38)
        "ret_1d": 0.06,
        "ret_3d": 0.05,
        "ret_5d": 0.06,
        "ret_7d": 0.05,
        "ret_10d": 0.05,
        "ret_15d": 0.04,
        "ret_20d": 0.04,
        "ret_30d": 0.03,

        # RATIO类型权重 - 成交量 (总计0.15)
        "volume_ratio_5_20": 0.04,
        "volume_ratio_10_30": 0.04,
        "volume_ratio_20_60": 0.04,
        "volume_ratio_30_90": 0.03,

        # RATIO类型权重 - 价格 (总计0.17)
        "price_range_20d": 0.04,
        "price_to_sma20": 0.05,
        "price_to_sma60": 0.04,
        "dist_vwap": 0.04,

        # RATIO类型权重 - 波动率 (总计0.20)
        "volatility_5d": 0.05,
        "volatility_10d": 0.05,
        "volatility_20d": 0.04,
        "vol_regime_5_20": 0.03,
        "vol_regime_10_60": 0.03,
    })
    return DERIVED_TERMINALS

def build_terminals_by_type():
    """动态构建按dtype分组的终端池（含权重）"""
    terminals_by_type = {}

    # 添加原始终端
    for name, dtype in RAW_TERMINALS.items():
        if dtype not in terminals_by_type:
            terminals_by_type[dtype] = []
        weight = RAW_TERMINAL_WEIGHTS.get(name, 0.05)
        terminals_by_type[dtype].append((name, weight, "raw"))

    # 添加衍生终端
    for name, (expr, dtype) in DERIVED_TERMINALS.items():
        if dtype not in terminals_by_type:
            terminals_by_type[dtype] = []
        weight = DERIVED_TERMINAL_WEIGHTS.get(name, 0.1)
        terminals_by_type[dtype].append((name, weight, "derived"))

    return terminals_by_type

# 保留TERMINALS用于向后兼容
TERMINALS = RAW_TERMINALS
TERMINAL_WEIGHTS = RAW_TERMINAL_WEIGHTS
