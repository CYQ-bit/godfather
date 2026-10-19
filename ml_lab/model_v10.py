"""
Model V10 core - shared by training, daily inference and tests.

Fixes over the original V10 scripts:
1. Label matches execution: signal at T close, enter at T+1 open, exit at
   T+1+HORIZON open (the old label was T close -> T+5 close).
2. Purged split: train | embargo | valid (early stop) | embargo | lockbox.
   Embargo >= label span, so no training label touches later periods.
3. Feature selection by rank IC inside the training split only
   (the old code picked the 50 columns with the lowest NaN rate).
4. The fitted model is saved together with its feature list and metadata,
   and refit on all labelled data with the early-stopped iteration count.
5. Daily inference predicts the latest feature date (label is still unknown
   there) and stamps every row with feature_asof / model_id.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

try:
    import lightgbm as lgb
    LGB_OK = True
except ImportError:
    LGB_OK = False

try:
    import xgboost as xgb
    XGB_OK = True
except ImportError:
    XGB_OK = False

REPO_ROOT = Path(__file__).resolve().parent.parent
FEATURE_PATH = REPO_ROOT / "data/feature_store/ml_alpha_matrix.parquet"
MODEL_DIR = REPO_ROOT / "data/ml2_results/models"
MAIN_PRED_PATH = REPO_ROOT / "data/ml2_results/main_predictions_v10.parquet"
OVERLAY_PRED_PATH = REPO_ROOT / "data/ml2_results/recent_overlay_predictions.parquet"

HORIZON = 5     # holding period in trading days
EXEC_LAG = 1    # orders go out the trading day after the signal
LABEL_SPAN = EXEC_LAG + HORIZON

# Trading on predictions older than this is refused (covers 3-day weekends
# plus one holiday).
MAX_FEATURE_AGE_DAYS = 4
MAX_MODEL_AGE_DAYS = 60

PRED_META_COLS = ["feature_asof", "model_id", "trained_through", "generated_at"]


@dataclass
class ModelConfig:
    name: str
    train_days: int
    valid_days: int
    lockbox_days: int
    max_features: int
    embargo_days: int = LABEL_SPAN
    min_coverage: float = 0.8
    params: dict = field(default_factory=dict)
    num_boost_round: int = 300
    early_stopping: int = 30


MAIN_CONFIG = ModelConfig(
    name="main_v10", train_days=378, valid_days=63, lockbox_days=63,
    max_features=50,
    params={"learning_rate": 0.05, "num_leaves": 31, "min_data_in_leaf": 200,
            "feature_fraction": 0.7, "bagging_fraction": 0.8, "bagging_freq": 5},
)
OVERLAY_CONFIG = ModelConfig(
    name="overlay_v10", train_days=84, valid_days=21, lockbox_days=21,
    max_features=30, num_boost_round=200, early_stopping=20,
    params={"learning_rate": 0.08, "num_leaves": 15, "min_data_in_leaf": 200,
            "feature_fraction": 0.6, "bagging_fraction": 0.8, "bagging_freq": 5},
)


# ---------------------------------------------------------------- labels

def build_exec_label(prices: pd.DataFrame, horizon: int = HORIZON,
                     exec_lag: int = EXEC_LAG) -> pd.DataFrame:
    """Open-to-open return from T+exec_lag to T+exec_lag+horizon.

    prices: columns timestamp, symbol, open. Shifts are by row within each
    symbol, i.e. by that symbol's trading days.
    """
    px = prices[["timestamp", "symbol", "open"]].sort_values(["symbol", "timestamp"])
    g = px.groupby("symbol", sort=False)["open"]
    entry = g.shift(-exec_lag)
    exit_ = g.shift(-(exec_lag + horizon))
    out = px[["timestamp", "symbol"]].copy()
    out["label"] = exit_ / entry - 1
    return out.reset_index(drop=True)


# ---------------------------------------------------------------- splits

def purged_split(dates, cfg: ModelConfig) -> dict:
    """Lay out train | gap | valid | gap | lockbox, ending at the last date.

    `dates` must be the sorted unique dates that HAVE a label. Each gap is
    cfg.embargo_days trading dates, so the label of the last training row
    ends before the first validation date.
    """
    dates = pd.DatetimeIndex(sorted(pd.unique(pd.DatetimeIndex(dates))))
    gap = cfg.embargo_days
    need = cfg.train_days + cfg.valid_days + cfg.lockbox_days + 2 * gap
    if len(dates) < need:
        raise ValueError(f"{cfg.name}: need {need} labelled dates, have {len(dates)}")

    end = len(dates)
    lock = dates[end - cfg.lockbox_days:end]
    end -= cfg.lockbox_days + gap
    valid = dates[end - cfg.valid_days:end]
    end -= cfg.valid_days + gap
    train = dates[end - cfg.train_days:end]
    refit = dates[len(dates) - (cfg.train_days + cfg.valid_days + cfg.lockbox_days + 2 * gap):]
    return {"train": train, "valid": valid, "lockbox": lock, "refit": refit}


# ---------------------------------------------------------------- features

def daily_rank_ic(df: pd.DataFrame, col: str, label: str = "label") -> pd.Series:
    """Spearman correlation per date, vectorised (no per-date Python loop)."""
    sub = df[["timestamp", col, label]].dropna()
    if sub.empty:
        return pd.Series(dtype=float)
    g = sub.groupby("timestamp")
    rx, ry = g[col].rank(), g[label].rank()
    ts = sub["timestamp"]
    dx = rx - rx.groupby(ts).transform("mean")
    dy = ry - ry.groupby(ts).transform("mean")
    num = (dx * dy).groupby(ts).sum()
    den = np.sqrt((dx ** 2).groupby(ts).sum() * (dy ** 2).groupby(ts).sum())
    n = ts.groupby(ts).size()
    ic = (num / den.replace(0, np.nan))[n > 2]
    return ic.dropna()


def select_features_by_ic(train: pd.DataFrame, feature_cols: list[str], max_features: int,
                          min_coverage: float = 0.8) -> tuple[list[str], pd.DataFrame]:
    """Rank features by |mean daily rank IC| on the training split only."""
    rows = []
    for col in feature_cols:
        coverage = train[col].notna().mean()
        if coverage < min_coverage:
            continue
        ic = daily_rank_ic(train, col)
        if len(ic) < 20:
            continue
        rows.append({"feature": col, "ic_mean": ic.mean(),
                     "ic_ir": ic.mean() / (ic.std() + 1e-12), "coverage": coverage})
    stats = pd.DataFrame(rows, columns=["feature", "ic_mean", "ic_ir", "coverage"])
    if stats.empty:
        return [], stats
    stats["abs_ir"] = stats["ic_ir"].abs()
    stats = stats.sort_values("abs_ir", ascending=False).reset_index(drop=True)
    return stats["feature"].head(max_features).tolist(), stats


# ---------------------------------------------------------------- model io

def _fit(X_tr, y_tr, X_va, y_va, cfg: ModelConfig, num_round: Optional[int] = None):
    if LGB_OK:
        params = {"objective": "regression", "metric": "l2", "verbosity": -1,
                  "seed": 42, "deterministic": True, "num_threads": 4, **cfg.params}
        dtr = lgb.Dataset(X_tr, label=y_tr)
        if num_round is not None:
            return lgb.train(params, dtr, num_boost_round=max(num_round, 1)), "lightgbm"
        dva = lgb.Dataset(X_va, label=y_va, reference=dtr)
        model = lgb.train(params, dtr, num_boost_round=cfg.num_boost_round, valid_sets=[dva],
                          callbacks=[lgb.early_stopping(cfg.early_stopping, verbose=False),
                                     lgb.log_evaluation(period=-1)])
        return model, "lightgbm"
    if XGB_OK:
        kw = dict(learning_rate=cfg.params.get("learning_rate", 0.05), max_depth=4,
                  subsample=0.8, colsample_bytree=0.7, random_state=42, n_jobs=4)
        if num_round is not None:
            model = xgb.XGBRegressor(n_estimators=max(num_round, 1), **kw)
            model.fit(X_tr, y_tr, verbose=False)
            return model, "xgboost"
        model = xgb.XGBRegressor(n_estimators=cfg.num_boost_round,
                                 early_stopping_rounds=cfg.early_stopping, **kw)
        model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)
        return model, "xgboost"
    raise RuntimeError("Install lightgbm or xgboost.")


def _best_iter(model, backend: str) -> int:
    if backend == "lightgbm":
        return int(model.best_iteration or model.current_iteration())
    return int((model.best_iteration or 0) + 1)


def save_model(model, backend: str, meta: dict, model_dir: Path = MODEL_DIR) -> dict:
    model_dir.mkdir(parents=True, exist_ok=True)
    ext = "txt" if backend == "lightgbm" else "json"
    model_path = model_dir / f"{meta['model_id']}.{ext}"
    model.save_model(str(model_path))
    meta = {**meta, "model_file": model_path.name}
    (model_dir / f"{meta['model_id']}.json").write_text(json.dumps(meta, indent=2, default=str))
    # Pointer to the model daily inference should use.
    (model_dir / f"{meta['name']}_current.json").write_text(json.dumps(meta, indent=2, default=str))
    return meta


def load_current_model(name: str, model_dir: Path = MODEL_DIR):
    pointer = model_dir / f"{name}_current.json"
    if not pointer.exists():
        raise FileNotFoundError(f"No trained model for {name}: {pointer} missing. Run training first.")
    meta = json.loads(pointer.read_text())
    path = model_dir / meta["model_file"]
    if meta["backend"] == "lightgbm":
        if not LGB_OK:
            raise RuntimeError("Model was trained with lightgbm, which is not installed.")
        model = lgb.Booster(model_file=str(path))
    else:
        if not XGB_OK:
            raise RuntimeError("Model was trained with xgboost, which is not installed.")
        model = xgb.XGBRegressor()
        model.load_model(str(path))
    return model, meta


# ---------------------------------------------------------------- train

def train(features: pd.DataFrame, labels: pd.DataFrame, cfg: ModelConfig,
          model_dir: Path = MODEL_DIR, verbose: bool = True) -> dict:
    """features: timestamp, symbol, alpha_*. labels: timestamp, symbol, label."""
    log = print if verbose else (lambda *a, **k: None)
    feature_cols = [c for c in features.columns if c.startswith("alpha_")]
    df = features.merge(labels, on=["timestamp", "symbol"], how="inner")
    df = df[df["label"].notna()]
    split = purged_split(df["timestamp"].unique(), cfg)

    def part(name):
        return df[df["timestamp"].isin(split[name])]

    tr, va, lb = part("train"), part("valid"), part("lockbox")
    feats, ic_stats = select_features_by_ic(tr, feature_cols, cfg.max_features, cfg.min_coverage)
    if not feats:
        raise ValueError(f"{cfg.name}: no feature passed coverage/IC screening")

    model, backend = _fit(tr[feats].to_numpy(np.float32), tr["label"].to_numpy(np.float32),
                          va[feats].to_numpy(np.float32), va["label"].to_numpy(np.float32), cfg)
    best_iter = _best_iter(model, backend)

    # Lockbox: untouched by selection and early stopping.
    lb = lb.copy()
    lb["y_pred"] = model.predict(lb[feats].to_numpy(np.float32))
    model_ic = daily_rank_ic(lb, "y_pred")
    best_single = ic_stats.iloc[0]
    base_ic = daily_rank_ic(lb, best_single["feature"]) * np.sign(best_single["ic_mean"])
    lockbox = {
        "model_ic_mean": float(model_ic.mean()), "model_ic_ir": float(model_ic.mean() / (model_ic.std() + 1e-12)),
        "baseline_feature": best_single["feature"],
        "baseline_ic_mean": float(base_ic.mean()), "n_days": int(len(model_ic)),
        "beats_baseline": bool(model_ic.mean() > base_ic.mean()),
    }

    # Production model: refit on everything labelled, same iteration count.
    rf = part("refit")
    final, _ = _fit(rf[feats].to_numpy(np.float32), rf["label"].to_numpy(np.float32),
                    None, None, cfg, num_round=best_iter)

    trained_through = pd.Timestamp(split["refit"][-1])
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    digest = hashlib.sha1(",".join(feats).encode()).hexdigest()[:8]
    meta = {
        "name": cfg.name,
        "model_id": f"{cfg.name}_{trained_through:%Y%m%d}_{digest}_{stamp}",
        "backend": backend,
        "features": feats,
        "best_iteration": best_iter,
        "label": f"open[T+{EXEC_LAG}] -> open[T+{EXEC_LAG + HORIZON}]",
        "embargo_days": cfg.embargo_days,
        "train": [str(split["train"][0].date()), str(split["train"][-1].date())],
        "valid": [str(split["valid"][0].date()), str(split["valid"][-1].date())],
        "lockbox": [str(split["lockbox"][0].date()), str(split["lockbox"][-1].date())],
        "trained_through": str(trained_through.date()),
        "lockbox_metrics": lockbox,
        "config": asdict(cfg),
        "trained_at": datetime.now().isoformat(timespec="seconds"),
    }
    meta = save_model(final, backend, meta, model_dir)

    log(f"[{cfg.name}] features={len(feats)} best_iter={best_iter} backend={backend}")
    log(f"[{cfg.name}] train {meta['train']} | valid {meta['valid']} | lockbox {meta['lockbox']}")
    log(f"[{cfg.name}] lockbox IC={lockbox['model_ic_mean']:.4f} (IR {lockbox['model_ic_ir']:.2f}) "
        f"vs best single factor {lockbox['baseline_feature']} IC={lockbox['baseline_ic_mean']:.4f}")
    if not lockbox["beats_baseline"]:
        log(f"[{cfg.name}] WARNING: model does not beat the best single factor on the lockbox")
    return meta


# ---------------------------------------------------------------- loaders

def load_feature_matrix(path: Path = FEATURE_PATH, since: Optional[pd.Timestamp] = None,
                        columns: Optional[list[str]] = None) -> pd.DataFrame:
    import pyarrow.parquet as pq
    if not Path(path).exists():
        raise FileNotFoundError(f"Feature matrix not found: {path}")
    chunks = []
    for batch in pq.ParquetFile(path).iter_batches(batch_size=200_000, columns=columns):
        chunk = batch.to_pandas()
        if since is not None:
            chunk = chunk[chunk["timestamp"] >= since]
        if len(chunk):
            chunks.append(chunk)
    if not chunks:
        raise ValueError(f"Feature matrix has no rows since {since}")
    return pd.concat(chunks, ignore_index=True)


def load_open_prices(since: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    import pyarrow.dataset as ds
    from runtime_paths import get_price_lake_dir
    dset = ds.dataset(str(get_price_lake_dir()), format="parquet")
    df = dset.to_table(columns=["timestamp", "symbol", "open"]).to_pandas()
    if since is not None:
        df = df[df["timestamp"] >= since]
    return df


def run_training_cli(cfg: ModelConfig) -> dict:
    print("=" * 70)
    print(f"{cfg.name.upper()} - purged training")
    print("=" * 70)
    # Enough calendar history for train+valid+lockbox+gaps plus slack.
    span = cfg.train_days + cfg.valid_days + cfg.lockbox_days + 2 * cfg.embargo_days + LABEL_SPAN
    since = pd.Timestamp.now().normalize() - pd.Timedelta(days=int(span * 1.6) + 30)
    features = load_feature_matrix(since=since)
    features = features.drop(columns=[c for c in ("target",) if c in features.columns])
    labels = build_exec_label(load_open_prices(since=since))
    return train(features, labels, cfg)


# ---------------------------------------------------------------- inference

def predict_latest(features: pd.DataFrame, model, meta: dict) -> pd.DataFrame:
    """Predict the latest feature date. Raises if model features are missing."""
    missing = [c for c in meta["features"] if c not in features.columns]
    if missing:
        raise ValueError(f"{meta['model_id']}: feature matrix lacks {missing[:5]}")
    asof = pd.Timestamp(features["timestamp"].max())
    today = features[features["timestamp"] == asof]
    if today.empty:
        raise ValueError("No rows at the latest feature date")
    X = today[meta["features"]].to_numpy(np.float32)
    out = today[["timestamp", "symbol"]].copy().reset_index(drop=True)
    out["y_pred"] = model.predict(X)
    out["feature_asof"] = asof.date().isoformat()
    out["model_id"] = meta["model_id"]
    out["trained_through"] = meta["trained_through"]
    out["generated_at"] = datetime.now().isoformat(timespec="seconds")
    return out


def check_prediction_freshness(pred: pd.DataFrame, trading_date: str,
                               max_feature_age_days: int = MAX_FEATURE_AGE_DAYS,
                               max_model_age_days: int = MAX_MODEL_AGE_DAYS) -> Optional[str]:
    """Return None if `pred` is usable for trading_date, else the reason it is not."""
    missing = [c for c in PRED_META_COLS if c not in pred.columns]
    if missing:
        return f"prediction file lacks {missing} (produced by the old mock pipeline?)"
    if pred.empty:
        return "prediction file is empty"
    asofs = pred["feature_asof"].unique()
    if len(asofs) != 1:
        return f"prediction file mixes feature dates {sorted(asofs)[:3]}"
    if pred["model_id"].nunique() != 1:
        return "prediction file mixes model ids"
    td = pd.Timestamp(trading_date).normalize()
    asof = pd.Timestamp(asofs[0])
    if asof >= td:
        return f"feature_asof {asof.date()} is not before trading date {td.date()}"
    if (td - asof).days > max_feature_age_days:
        return f"features are stale: feature_asof {asof.date()}, trading {td.date()}"
    trained = pd.Timestamp(pred["trained_through"].iloc[0])
    if (td - trained).days > max_model_age_days:
        return f"model is stale: trained through {trained.date()}, retrain required"
    return None
