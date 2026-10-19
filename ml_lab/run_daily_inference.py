"""
Daily inference - replaces the mock run_fresh_predictions.py.

Loads the saved main/overlay models, predicts the latest feature date, and
writes the files run_pt44_unified.py reads. Exits non-zero if anything is
missing or stale, so the daily scheduler stops instead of trading on old data.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from ml_lab.model_v10 import (
    FEATURE_PATH, MAIN_CONFIG, MAIN_PRED_PATH, MAX_FEATURE_AGE_DAYS, MODEL_DIR,
    OVERLAY_CONFIG, OVERLAY_PRED_PATH, load_current_model, load_feature_matrix,
    predict_latest,
)


def overlay_columns(pred: pd.DataFrame) -> pd.DataFrame:
    """Confidence buckets from the cross-section of today's overlay scores."""
    out = pred.rename(columns={"y_pred": "overlay_score"})
    mag = out["overlay_score"].abs()
    lo, hi = mag.quantile(0.33), mag.quantile(0.67)
    out["overlay_confidence"] = np.where(mag >= hi, "high", np.where(mag >= lo, "mid", "low"))
    out["overlay_filter_flag"] = np.where(
        (out["overlay_confidence"] == "low") & (out["overlay_score"] < 0), "bad", "ok")
    return out


def run(feature_path: Path = FEATURE_PATH, model_dir: Path = MODEL_DIR,
        main_out: Path = MAIN_PRED_PATH, overlay_out: Path = OVERLAY_PRED_PATH,
        today: pd.Timestamp | None = None) -> dict:
    today = pd.Timestamp(today or pd.Timestamp.now().normalize())
    main_model, main_meta = load_current_model(MAIN_CONFIG.name, model_dir)
    try:
        ov_model, ov_meta = load_current_model(OVERLAY_CONFIG.name, model_dir)
    except FileNotFoundError as exc:
        print(f"⚠️  Overlay disabled: {exc}")
        ov_model, ov_meta = None, None

    cols = sorted(set(main_meta["features"]) | set(ov_meta["features"] if ov_meta else []))
    since = today - pd.Timedelta(days=MAX_FEATURE_AGE_DAYS + 10)
    features = load_feature_matrix(feature_path, since=since, columns=["timestamp", "symbol", *cols])
    asof = pd.Timestamp(features["timestamp"].max())
    if (today - asof.normalize()).days > MAX_FEATURE_AGE_DAYS:
        raise RuntimeError(f"Feature matrix is stale: latest {asof.date()}, today {today.date()}")

    main_pred = predict_latest(features, main_model, main_meta)
    main_out.parent.mkdir(parents=True, exist_ok=True)
    main_pred.to_parquet(main_out, index=False)
    print(f"✅ Main predictions: {len(main_pred)} rows, feature_asof={asof.date()}, model={main_meta['model_id']}")

    if ov_model is not None:
        ov_pred = overlay_columns(predict_latest(features, ov_model, ov_meta))
        ov_pred.to_parquet(overlay_out, index=False)
        print(f"✅ Overlay predictions: {len(ov_pred)} rows, model={ov_meta['model_id']}")
    elif overlay_out.exists():
        overlay_out.unlink()  # never leave an old overlay file around

    return {"feature_asof": asof.date().isoformat(), "rows": len(main_pred),
            "main_model": main_meta["model_id"], "overlay_model": ov_meta["model_id"] if ov_meta else None}


def main() -> int:
    try:
        run()
    except Exception as exc:
        print(f"❌ Daily inference failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
