"""
Train Main Model V10 - Real Training (24-month window)
"""
from __future__ import annotations

import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from datetime import datetime, timedelta

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

REPO_ROOT = Path(__file__).parent.parent
FEATURE_PATH = REPO_ROOT / "data/feature_store/ml_alpha_matrix.parquet"
OUT_PATH     = REPO_ROOT / "data/ml2_results/main_predictions_v10.parquet"
MODEL_PATH   = REPO_ROOT / "data/ml2_results/main_model_v10_meta.json"

TRAIN_MONTHS = 21  # Actual calendar months
VALID_MONTHS = 3
MAX_FEATURES = 50   # 取 top-N 降噪


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
    # 选 NaN 率最低的 top-N 列
    nan_rate = df[alpha_cols].isna().mean()
    selected = nan_rate.nsmallest(max_f).index.tolist()
    return selected


def train_model(X_tr, y_tr, X_va, y_va, feat_cols):
    if LGB_OK:
        dtrain = lgb.Dataset(X_tr, label=y_tr)
        dvalid = lgb.Dataset(X_va, label=y_va, reference=dtrain)
        params = {
            "objective": "regression", "metric": "rmse",
            "learning_rate": 0.05, "num_leaves": 63,
            "feature_fraction": 0.7, "bagging_fraction": 0.8,
            "bagging_freq": 5, "n_jobs": -1, "verbosity": -1,
        }
        model = lgb.train(params, dtrain, num_boost_round=300,
                          valid_sets=[dvalid],
                          callbacks=[lgb.early_stopping(30, verbose=False),
                                     lgb.log_evaluation(period=-1)])
        return model, "lightgbm"

    if XGB_OK:
        model = xgb.XGBRegressor(n_estimators=300, learning_rate=0.05,
                                  max_depth=6, subsample=0.8,
                                  colsample_bytree=0.7, verbosity=0,
                                  early_stopping_rounds=30, n_jobs=-1)
        model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)
        return model, "xgboost"

    raise RuntimeError("No ML library available. Install lightgbm or xgboost.")


def main():
    print("=" * 70)
    print("MAIN MODEL V10 — REAL TRAINING")
    print("=" * 70)

    now = pd.Timestamp(datetime.now().date())
    train_start = now - pd.DateOffset(months=TRAIN_MONTHS)
    train_end   = now - pd.DateOffset(months=VALID_MONTHS)
    valid_start = train_end
    valid_end   = now

    print(f"\nTRAIN_START={train_start.date()}")
    print(f"TRAIN_END  ={train_end.date()}")
    print(f"VALID_START={valid_start.date()}")
    print(f"VALID_END  ={valid_end.date()}")

    print("\nLoading training data...")
    df_tr = load_window(train_start, train_end)
    df_va = load_window(valid_start, valid_end)

    print(f"TRAIN_ROWS={len(df_tr)}")
    print(f"VALID_ROWS={len(df_va)}")

    feat_cols = select_features(df_tr, MAX_FEATURES)
    print(f"FEATURE_COUNT={len(feat_cols)}")

    # Clean
    df_tr = df_tr.dropna(subset=feat_cols + ["target"])
    df_va = df_va.dropna(subset=feat_cols + ["target"])

    X_tr = df_tr[feat_cols].values.astype(np.float32)
    y_tr = df_tr["target"].values.astype(np.float32)
    X_va = df_va[feat_cols].values.astype(np.float32)
    y_va = df_va["target"].values.astype(np.float32)

    print("\nTraining main model...")
    model, backend = train_model(X_tr, y_tr, X_va, y_va, feat_cols)
    print(f"Backend: {backend}")

    # Predict on validation set → save as main predictions
    if backend == "lightgbm":
        preds = model.predict(X_va)
    else:
        preds = model.predict(X_va)

    out_df = df_va[["timestamp", "symbol"]].copy()
    out_df["y_pred"] = preds
    out_df["y_true"] = y_va
    out_df["window_id"] = 999
    out_df["model"] = "main_v10"
    out_df["train_start"] = str(train_start.date())
    out_df["train_end"] = str(train_end.date())

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(OUT_PATH, index=False)

    # Save meta
    meta = {
        "train_start": str(train_start.date()),
        "train_end": str(train_end.date()),
        "valid_start": str(valid_start.date()),
        "valid_end": str(valid_end.date()),
        "train_rows": len(df_tr),
        "valid_rows": len(df_va),
        "feature_count": len(feat_cols),
        "backend": backend,
        "model_save_path": str(OUT_PATH),
        "trained_at": datetime.now().isoformat(),
    }
    MODEL_PATH.write_text(json.dumps(meta, indent=2))

    print(f"\nMODEL_SAVE_PATH={OUT_PATH}")
    print(f"✓ MAIN_MODEL_TRAINED=YES")
    print(f"✓ MAIN_PREDICTIONS_READY=YES")
    print(f"\nRows saved: {len(out_df)}")
    print("=" * 70)
    return meta


if __name__ == "__main__":
    main()
