"""
Incrementally refresh market data and the frozen feature matrix for PT.4.4.

Flow:
1. Refresh v8_empire market data lake with latest OHLCV bars.
2. Recompute only the recent overlap window of the frozen feature matrix.
3. Replace the tail of data/feature_store/ml_alpha_matrix.parquet in place.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd
import polars as pl
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))

from alpha_factory.ast_generator import ASTNode
from alpha_factory.operator_library import (
    DERIVED_TERMINALS,
    FAST_OPERATOR_REGISTRY,
    RAW_TERMINALS,
    build_derived_terminal_exprs,
)
from alpha_factory.polars_compiler import PolarsCompiler
from runtime_paths import get_price_lake_dir, get_runtime_path_report, get_universe_path


REPO_ROOT = Path(__file__).resolve().parents[1]
PRICE_DIR = get_price_lake_dir()
UNIVERSE_PATH = get_universe_path()
FEATURE_PATH = REPO_ROOT / "data" / "feature_store" / "ml_alpha_matrix.parquet"
METADATA_PATH = REPO_ROOT / "data" / "feature_store" / "ml_alpha_metadata.parquet"

MARKET_REFRESH_BUFFER_DAYS = 180
FEATURE_LOOKBACK_BUFFER_DAYS = 260
FEATURE_REPLACE_OVERLAP_DAYS = 45
BATCH_SIZE = 40


def log(message: str) -> None:
    print(message, flush=True)


def log_runtime_paths() -> None:
    log("=" * 80)
    log("Runtime path resolver")
    log("=" * 80)
    for key, value in get_runtime_path_report().items():
        log(f"{key}={value}")


@dataclass
class MarketRefreshSummary:
    current_latest_date: pd.Timestamp
    refreshed_latest_date: pd.Timestamp
    total_symbols: int
    advanced_symbols: int
    failed_symbols: List[str]


class FormulaParser:
    def __init__(self, text: str):
        self.text = text.strip()
        self.pos = 0

    def parse(self) -> ASTNode:
        node = self._parse_expr()
        self._skip_ws()
        if self.pos != len(self.text):
            raise ValueError(f"Unexpected trailing content in formula: {self.text}")
        return node

    def _parse_expr(self) -> ASTNode:
        self._skip_ws()
        if self.pos >= len(self.text):
            raise ValueError("Unexpected end of formula")

        char = self.text[self.pos]
        if char.isdigit() or char in "-.":
            return self._parse_number()

        identifier = self._parse_identifier()
        self._skip_ws()

        if self.pos < len(self.text) and self.text[self.pos] == "(":
            self.pos += 1
            children: List[ASTNode] = []

            while True:
                self._skip_ws()
                if self.pos >= len(self.text):
                    raise ValueError(f"Unclosed function call in formula: {self.text}")
                if self.text[self.pos] == ")":
                    self.pos += 1
                    break
                children.append(self._parse_expr())
                self._skip_ws()
                if self.pos < len(self.text) and self.text[self.pos] == ",":
                    self.pos += 1
                    continue
                if self.pos < len(self.text) and self.text[self.pos] == ")":
                    self.pos += 1
                    break
                raise ValueError(f"Unexpected token in formula: {self.text}")

            return ASTNode(identifier, children=children)

        if identifier in DERIVED_TERMINALS:
            return ASTNode("derived_terminal", value=identifier)
        if identifier in RAW_TERMINALS:
            return ASTNode("terminal", value=identifier)

        raise ValueError(f"Unknown terminal in formula: {identifier}")

    def _parse_identifier(self) -> str:
        start = self.pos
        while self.pos < len(self.text) and (
            self.text[self.pos].isalnum() or self.text[self.pos] == "_"
        ):
            self.pos += 1
        if start == self.pos:
            raise ValueError(f"Expected identifier in formula: {self.text}")
        return self.text[start:self.pos]

    def _parse_number(self) -> ASTNode:
        start = self.pos
        while self.pos < len(self.text) and (
            self.text[self.pos].isdigit() or self.text[self.pos] in ".-"
        ):
            self.pos += 1
        raw = self.text[start:self.pos]
        value = float(raw) if "." in raw else int(raw)
        return ASTNode("const", value=value)

    def _skip_ws(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1


def chunked(items: List[str], size: int) -> Iterable[List[str]]:
    for index in range(0, len(items), size):
        yield items[index:index + size]


def get_universe_sector_map() -> Dict[str, str]:
    if not UNIVERSE_PATH.exists():
        return {}

    universe_df = pd.read_csv(UNIVERSE_PATH)
    if "Symbol" not in universe_df.columns or "GICS Sector" not in universe_df.columns:
        return {}

    return {
        str(row["Symbol"]).replace(".", "-"): row["GICS Sector"]
        for _, row in universe_df.iterrows()
    }


def read_price_file_summary(price_file: Path, fallback_sector: str | None) -> Tuple[pd.Timestamp, str]:
    df = pd.read_parquet(price_file, columns=["timestamp", "sector"])
    latest_date = pd.to_datetime(df["timestamp"]).max().normalize()

    sector = fallback_sector or "Unknown"
    if "sector" in df.columns and df["sector"].notna().any():
        sector = str(df["sector"].dropna().iloc[-1])

    return latest_date, sector


def collect_market_state() -> Tuple[pd.Timestamp, Dict[str, pd.Timestamp], Dict[str, str]]:
    sector_map = get_universe_sector_map()
    latest_by_symbol: Dict[str, pd.Timestamp] = {}
    enriched_sector_map: Dict[str, str] = {}

    price_files = sorted(PRICE_DIR.glob("*.parquet"))
    if not price_files:
        raise FileNotFoundError(f"No price files found in {PRICE_DIR}")

    for price_file in price_files:
        symbol = price_file.stem
        latest_date, sector = read_price_file_summary(price_file, sector_map.get(symbol))
        latest_by_symbol[symbol] = latest_date
        enriched_sector_map[symbol] = sector

    current_latest = max(latest_by_symbol.values())
    return current_latest, latest_by_symbol, enriched_sector_map


def normalize_yfinance_frame(raw_df: pd.DataFrame, symbol: str, sector: str) -> pd.DataFrame:
    if raw_df.empty:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "symbol", "sector"])

    frame = raw_df.copy()
    frame = frame.rename_axis("timestamp").reset_index()
    frame.columns = [str(col).lower().replace(" ", "_") for col in frame.columns]

    required_columns = ["timestamp", "open", "high", "low", "close", "volume"]
    missing = [col for col in required_columns if col not in frame.columns]
    if missing:
        raise ValueError(f"{symbol}: missing columns from yfinance payload: {missing}")

    frame["timestamp"] = pd.to_datetime(frame["timestamp"]).dt.tz_localize(None)
    frame = frame[required_columns].dropna(subset=["timestamp", "close"])
    if frame.empty:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "symbol", "sector"])

    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0).astype("int64")
    frame["symbol"] = symbol
    frame["sector"] = sector or "Unknown"

    return frame.sort_values("timestamp").reset_index(drop=True)


def extract_symbol_frame(downloaded: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if downloaded.empty:
        return pd.DataFrame()

    if isinstance(downloaded.columns, pd.MultiIndex):
        level0 = downloaded.columns.get_level_values(0)
        level1 = downloaded.columns.get_level_values(1)

        if symbol in level0:
            frame = downloaded[symbol].copy()
            frame.columns = [str(col) for col in frame.columns]
            return frame
        if symbol in level1:
            frame = downloaded.xs(symbol, axis=1, level=1).copy()
            frame.columns = [str(col) for col in frame.columns]
            return frame
        return pd.DataFrame()

    return downloaded.copy()


def merge_price_file(symbol: str, fresh_df: pd.DataFrame) -> bool:
    if fresh_df.empty:
        return False

    price_file = PRICE_DIR / f"{symbol}.parquet"
    if price_file.exists():
        existing_df = pd.read_parquet(price_file)
    else:
        existing_df = pd.DataFrame(columns=fresh_df.columns)

    combined = pd.concat([existing_df, fresh_df], ignore_index=True)
    combined["timestamp"] = pd.to_datetime(combined["timestamp"]).dt.tz_localize(None)
    combined = (
        combined.sort_values("timestamp")
        .drop_duplicates(subset=["timestamp"], keep="last")
        .reset_index(drop=True)
    )

    previous_latest = pd.to_datetime(existing_df["timestamp"]).max().normalize() if not existing_df.empty else None
    refreshed_latest = pd.to_datetime(combined["timestamp"]).max().normalize()
    advanced = previous_latest is None or refreshed_latest > previous_latest

    combined.to_parquet(price_file, index=False)
    return advanced


def refresh_market_data() -> MarketRefreshSummary:
    log("=" * 80)
    log("Step 1 - Refresh latest market data")
    log("=" * 80)

    current_latest, latest_by_symbol, sector_map = collect_market_state()
    symbols = sorted(latest_by_symbol.keys())
    refresh_start = (current_latest - pd.Timedelta(days=MARKET_REFRESH_BUFFER_DAYS)).date().isoformat()

    log(f"RESOLVED_PRICE_PATH={PRICE_DIR}")
    log(f"RESOLVED_UNIVERSE_PATH={UNIVERSE_PATH}")
    log(f"Price source: {PRICE_DIR}")
    log(f"Current latest market date: {current_latest.date().isoformat()}")
    log(f"Incremental refresh start: {refresh_start}")
    log(f"Universe size: {len(symbols)}")

    advanced_symbols = 0
    failed_symbols: List[str] = []

    for batch_index, batch in enumerate(chunked(symbols, BATCH_SIZE), start=1):
        log(f"Downloading batch {batch_index}/{math.ceil(len(symbols) / BATCH_SIZE)} ({len(batch)} tickers)")

        try:
            downloaded = yf.download(
                tickers=" ".join(batch),
                start=refresh_start,
                interval="1d",
                auto_adjust=True,
                progress=False,
                group_by="ticker",
                threads=True,
            )
        except Exception as exc:
            log(f"Batch download failed: {exc}")
            failed_symbols.extend(batch)
            continue

        for symbol in batch:
            try:
                symbol_frame = extract_symbol_frame(downloaded, symbol)
                normalized = normalize_yfinance_frame(symbol_frame, symbol, sector_map.get(symbol, "Unknown"))
                if normalized.empty:
                    failed_symbols.append(symbol)
                    continue
                if merge_price_file(symbol, normalized):
                    advanced_symbols += 1
            except Exception as exc:
                log(f"{symbol}: refresh failed ({exc})")
                failed_symbols.append(symbol)

    refreshed_latest, _, _ = collect_market_state()
    log(f"Refreshed latest market date: {refreshed_latest.date().isoformat()}")
    log(f"Symbols advanced: {advanced_symbols}")
    log(f"Symbols failed: {len(failed_symbols)}")
    if failed_symbols:
        log(f"Failed symbols sample: {', '.join(sorted(failed_symbols)[:10])}")

    return MarketRefreshSummary(
        current_latest_date=current_latest,
        refreshed_latest_date=refreshed_latest,
        total_symbols=len(symbols),
        advanced_symbols=advanced_symbols,
        failed_symbols=sorted(set(failed_symbols)),
    )


def get_feature_schema() -> pa.Schema:
    if not FEATURE_PATH.exists():
        raise FileNotFoundError(f"Feature matrix not found: {FEATURE_PATH}")
    return pq.ParquetFile(FEATURE_PATH).schema_arrow


def get_feature_latest_date() -> pd.Timestamp:
    latest_df = pl.scan_parquet(str(FEATURE_PATH)).select(pl.col("timestamp").max()).collect()
    return pd.Timestamp(latest_df.item()).normalize()


def parse_formula(formula: str) -> ASTNode:
    return FormulaParser(formula).parse()


def build_feature_exprs(feature_columns: List[str], formula_map: Dict[str, str]) -> List[pl.Expr]:
    build_derived_terminal_exprs()
    compiler = PolarsCompiler()

    expressions: List[pl.Expr] = [
        pl.col("timestamp"),
        pl.col("symbol"),
        (pl.col("close").shift(-5).over("symbol") / pl.col("close") - 1).alias("target"),
    ]

    for feature_name in feature_columns:
        formula = formula_map.get(feature_name)
        if not formula:
            raise KeyError(f"Missing formula for {feature_name}")
        ast = parse_formula(formula)
        expr = compiler.compile(ast)
        if expr is None:
            raise ValueError(f"Failed to compile formula for {feature_name}: {formula}")
        expressions.append(expr.alias(feature_name))

    return expressions


def load_recent_price_window(compute_start: pd.Timestamp) -> pl.DataFrame:
    price_glob = str(PRICE_DIR / "*.parquet")
    price_df = (
        pl.scan_parquet(price_glob)
        .filter(pl.col("timestamp") >= pl.lit(compute_start.to_pydatetime()))
        .select(["timestamp", "symbol", "open", "high", "low", "close", "volume"])
        .collect()
        .sort(["timestamp", "symbol"])
    )

    build_derived_terminal_exprs()
    derived_columns = {name: expr for name, (expr, _) in DERIVED_TERMINALS.items()}
    return price_df.with_columns(**derived_columns)


def recompute_feature_tail(market_latest_date: pd.Timestamp) -> pl.DataFrame:
    log("=" * 80)
    log("Step 2 - Recompute frozen feature matrix tail")
    log("=" * 80)

    feature_schema = get_feature_schema()
    current_feature_latest = get_feature_latest_date()
    feature_columns = feature_schema.names[3:]
    formula_map = (
        pd.read_parquet(METADATA_PATH)[["alpha_name", "formula"]]
        .set_index("alpha_name")["formula"]
        .to_dict()
    )

    replace_start = current_feature_latest - pd.Timedelta(days=FEATURE_REPLACE_OVERLAP_DAYS)
    compute_start = replace_start - pd.Timedelta(days=FEATURE_LOOKBACK_BUFFER_DAYS)

    log(f"Feature path: {FEATURE_PATH}")
    log(f"Current feature latest date: {current_feature_latest.date().isoformat()}")
    log(f"Market latest date: {market_latest_date.date().isoformat()}")
    log(f"Feature recompute window: {replace_start.date().isoformat()} -> {market_latest_date.date().isoformat()}")
    log(f"Feature lookback buffer start: {compute_start.date().isoformat()}")

    price_window = load_recent_price_window(compute_start)
    feature_exprs = build_feature_exprs(feature_columns, formula_map)
    refreshed_tail = (
        price_window
        .select(feature_exprs)
        .filter(pl.col("timestamp") >= pl.lit(replace_start.to_pydatetime()))
        .sort(["timestamp", "symbol"])
    )

    if refreshed_tail.is_empty():
        raise ValueError("Refreshed feature tail is empty")

    log(f"Refreshed tail rows: {refreshed_tail.height}")
    log(f"Refreshed tail latest date: {refreshed_tail.select(pl.col('timestamp').max()).item()}")

    return refreshed_tail


def replace_feature_tail(refreshed_tail: pl.DataFrame) -> None:
    schema = get_feature_schema()
    replace_start = pd.Timestamp(refreshed_tail.select(pl.col("timestamp").min()).item()).to_pydatetime()

    temp_path = FEATURE_PATH.with_suffix(".tmp.parquet")
    if temp_path.exists():
        temp_path.unlink()

    parquet_file = pq.ParquetFile(FEATURE_PATH)
    writer: pq.ParquetWriter | None = None

    try:
        replace_scalar = pa.scalar(replace_start, type=schema.field("timestamp").type)

        for row_group_index in range(parquet_file.num_row_groups):
            table = parquet_file.read_row_group(row_group_index)
            mask = pc.less(table["timestamp"], replace_scalar)
            filtered = table.filter(mask)
            if filtered.num_rows == 0:
                continue

            if writer is None:
                writer = pq.ParquetWriter(temp_path, schema=schema)
            writer.write_table(filtered.select(schema.names))

        refreshed_table = refreshed_tail.select(schema.names).to_arrow()
        if not refreshed_table.schema.equals(schema, check_metadata=False):
            refreshed_table = refreshed_table.cast(schema)

        if writer is None:
            writer = pq.ParquetWriter(temp_path, schema=schema)
        writer.write_table(refreshed_table)
    finally:
        if writer is not None:
            writer.close()

    temp_path.replace(FEATURE_PATH)


def summarize_feature_matrix() -> Dict[str, object]:
    stats_df = (
        pl.scan_parquet(str(FEATURE_PATH))
        .select(
            [
                pl.len().alias("rows"),
                pl.col("timestamp").max().alias("latest_date"),
                pl.col("symbol").n_unique().alias("symbols"),
            ]
        )
        .collect()
    )

    return {
        "path": str(FEATURE_PATH),
        "rows": int(stats_df["rows"][0]),
        "latest_date": pd.Timestamp(stats_df["latest_date"][0]).date().isoformat(),
        "symbols": int(stats_df["symbols"][0]),
    }


def main() -> int:
    log_runtime_paths()
    market_summary = refresh_market_data()

    if market_summary.refreshed_latest_date < market_summary.current_latest_date:
        raise RuntimeError("Market refresh moved backwards unexpectedly")

    feature_latest_before = get_feature_latest_date()

    if market_summary.refreshed_latest_date > feature_latest_before:
        refreshed_tail = recompute_feature_tail(market_summary.refreshed_latest_date)
        replace_feature_tail(refreshed_tail)
    else:
        log("Feature matrix already up to date with market data; no rebuild needed")

    feature_summary = summarize_feature_matrix()

    log("=" * 80)
    log("Step 3 - Final feature matrix summary")
    log("=" * 80)
    log(f"Feature path: {feature_summary['path']}")
    log(f"Latest feature date: {feature_summary['latest_date']}")
    log(f"Rows: {feature_summary['rows']}")
    log(f"Symbols: {feature_summary['symbols']}")
    log("FEATURE_REFRESH_OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
