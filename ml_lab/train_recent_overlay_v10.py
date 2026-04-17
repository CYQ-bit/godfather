"""
Train Recent Overlay V10 - Real Training (6-month window)
"""
from __future__ import annotations

import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from datetime import datetime

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

REPO_ROOT    = Path(__file__).parent.parent
FEATURE_PATH = REPO_ROOT / "data/feature_store/ml_alpha_matrix.parquet"
OUT_PATH     = REPO_ROOT / "data/ml2_results/recent_overlay_predictions.parquet"
MODEL_PATH   = REPO_ROOT / "data/ml2_results/overlay_model_v10_meta.json"
SNAP_PATH    = REPO_ROOT / "data/ai_engine/latest_overlay_snapshot.json"

TRAIN_MONTHS = 5  # Actual calendar months
VALID_MONTHS = 1
MAX_FEATURES = 30   # 更轻量


def load_window(ts_min: pd.Timestamp, ts_max: pd.Timestamp) -> pd.DataFrame:
    pf = pq.ParquetFile(FEATURE_PATH)
    chunks = []
    for batch in pf.iter_batches(batch_size=200_000):
        chunk = batch.to_pandas()
        chunk = chunk[(chunk["timestamp"] >= ts_min) & (chunk["timestamp"] < ts_max)]
        if len(chunk):
            chunks.append(chunk)
    return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()


def select_features(df: pd.DataFrame, max_f: int) -> list[str]:
    alpha_cols = [c for c in df.columns if c.startswith("alpha_")]
    nan_rate = df[alpha_cols].isna().mean()
    return nan_rate.nsmallest(max_f).index.tolist()


def train_model(X_tr, y_tr, X_va, y_va):
    if LGB_OK:
        dtrain = lgb.Dataset(X_tr, label=y_tr)
        dvalid = lgb.Dataset(X_va, label=y_va, reference=dtrain)
        params = {
            "objective": "regression", "metric": "rmse",
            "learning_rate": 0.08, "num_leaves": 31,
            "feature_fraction": 0.6, "bagging_fraction": 0.8,
            "bagging_freq": 5, "n_jobs": -1, "verbosity": -1,
        }
        model = lgb.train(params, dtrain, num_boost_round=200,
                          valid_sets=[dvalid],
                          callbacks=[lgb.early_stopping(20, verbose=False),
                                     lgb.log_evaluation(period=-1)])
        return model, "lightgbm"

    if XGB_OK:
        model = xgb.XGBRegressor(n_estimators=200, learning_rate=0.08,
                                  max_depth=5, subsample=0.8,
                                  colsample_bytree=0.6, verbosity=0,
                                  early_stopping_rounds=20, n_jobs=-1)
        model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)
        return model, "xgboost"

    raise RuntimeError("No ML library available.")


def compute_overlay_confidence(preds: np.ndarray) -> pd.Series:
    """用预测值绝对值作为 confidence 代理"""
    s = pd.Series(np.abs(preds))
    lo, hi = s.quantile(0.33), s.quantile(0.67)
    def bucket(v):
        if v >= hi:   return "high"
        if v >= lo:   return "mid"
        return "low"
    return s.map(bucket)


def main():
    print("=" * 70)
    print("RECENT OVERLAY V10 — REAL TRAINING")
    print("=" * 70)

    now = pd.Timestamp(datetime.now().date())
    train_start = now - pd.DateOffset(months=TRAIN_MONTHS)
    train_end   = now - pd.DateOffset(months=VALID_MONTHS)
    valid_start = train_end
    valid_end   = now

    print(f"\nOVERLAY_TRAIN_START={train_start.date()}")
    print(f"OVERLAY_TRAIN_END  ={train_end.date()}")
    print(f"OVERLAY_VALID_START={valid_start.date()}")
    print(f"OVERLAY_VALID_END  ={valid_end.date()}")

    print("\nLoading overlay training data...")
    df_tr = load_window(train_start, train_end)
    df_va = load_window(valid_start, valid_end)

    print(f"OVERLAY_ROWS (train)={len(df_tr)}")
    print(f"OVERLAY_ROWS (valid)={len(df_va)}")

    feat_cols = select_features(df_tr, MAX_FEATURES)
    print(f"OVERLAY_FEATURE_COUNT={len(feat_cols)}")

    df_tr = df_tr.dropna(subset=feat_cols + ["target"])
    df_va = df_va.dropna(subset=feat_cols + ["target"])

    X_tr = df_tr[feat_cols].values.astype(np.float32)
    y_tr = df_tr["target"].values.astype(np.float32)
    X_va = df_va[feat_cols].values.astype(np.float32)
    y_va = df_va["target"].values.astype(np.float32)

    print("\nTraining overlay model...")
    model, backend = train_model(X_tr, y_tr, X_va, y_va)
    print(f"Backend: {backend}")

    if backend == "lightgbm":
        preds = model.predict(X_va)
    else:
        preds = model.predict(X_va)

    out_df = df_va[["timestamp", "symbol"]].copy()
    out_df["overlay_score"]      = preds
    out_df["y_true"]             = y_va
    out_df["overlay_confidence"] = compute_overlay_confidence(preds)
    # filter flag: low confidence + negative score = bad
    out_df["overlay_filter_flag"] = (
        (out_df["overlay_confidence"] == "low") & (out_df["overlay_score"] < 0)
    ).map({True: "bad", False: "ok"})
    out_df["overlay_prediction_date"] = str(valid_end.date())
    out_df["model"] = "overlay_v10"
    out_df["train_start"] = str(train_start.date())
    out_df["train_end"]   = str(train_end.date())

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(OUT_PATH, index=False)

    meta = {
        "overlay_train_start": str(train_start.date()),
        "overlay_train_end":   str(train_end.date()),
        "overlay_valid_start": str(valid_start.date()),
        "overlay_valid_end":   str(valid_end.date()),
        "overlay_rows":        len(df_tr),
        "overlay_feature_count": len(feat_cols),
        "backend": backend,
        "overlay_model_save_path": str(OUT_PATH),
        "trained_at": datetime.now().isoformat(),
    }
    MODEL_PATH.write_text(json.dumps(meta, indent=2))

    snap = {
        **meta,
        "high_conf_count": int((out_df["overlay_confidence"] == "high").sum()),
        "low_conf_count":  int((out_df["overlay_confidence"] == "low").sum()),
        "filtered_count":  int((out_df["overlay_filter_flag"] == "bad").sum()),
    }
    SNAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAP_PATH.write_text(json.dumps(snap, indent=2))

    print(f"\nOVERLAY_MODEL_SAVE_PATH={OUT_PATH}")
    print(f"✓ OVERLAY_MODEL_TRAINED=YES")
    print(f"✓ OVERLAY_PREDICTIONS_READY=YES")
    print(f"  High conf: {snap['high_conf_count']}")
    print(f"  Low  conf: {snap['low_conf_count']}")
    print(f"  Filtered : {snap['filtered_count']}")
    print(f"\nRows saved: {len(out_df)}")
    print("=" * 70)
    return meta


if __name__ == "__main__":
    main()
