"""
Daily inference - replaces the mock run_fresh_predictions.py.

Loads the saved main/overlay models, predicts the latest feature date, and
writes the files run_pt44_unified.py reads. Exits non-zero if anything is
missing or stale, so the daily scheduler stops instead of trading on old data.
"""
from __future__ import annotations

import sys
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from ml_lab.model_v10 import (
    FEATURE_PATH, MAIN_CONFIG, MAIN_PRED_PATH, MAX_FEATURE_AGE_DAYS, MODEL_DIR,
    OVERLAY_CONFIG, OVERLAY_PRED_PATH, load_current_model, load_feature_matrix,
    predict_latest, validate_latest_cross_section,
)


def overlay_columns(pred: pd.DataFrame) -> pd.DataFrame:
    """Confidence buckets from the cross-section of today's overlay scores."""
    out = pred.copy()
    out["overlay_score"] = out["y_pred"]
    mag = out["overlay_score"].abs()
    lo, hi = mag.quantile(0.33), mag.quantile(0.67)
    out["overlay_confidence"] = np.where(mag >= hi, "high", np.where(mag >= lo, "mid", "low"))
    out["overlay_filter_flag"] = np.where(
        (out["overlay_confidence"] == "low") & (out["overlay_score"] < 0), "bad", "ok")
    return out


def run(feature_path: Path = FEATURE_PATH, model_dir: Path = MODEL_DIR,
        main_out: Path = MAIN_PRED_PATH, overlay_out: Path = OVERLAY_PRED_PATH,
        today: pd.Timestamp | None = None) -> dict:
    today = pd.Timestamp(
        today or pd.Timestamp.now(tz=ZoneInfo("America/New_York")).normalize().tz_localize(None)
    )
    main_model, main_meta = load_current_model(MAIN_CONFIG.name, model_dir)
    ov_model, ov_meta = load_current_model(OVERLAY_CONFIG.name, model_dir)

    cols = sorted(set(main_meta["features"]) | set(ov_meta["features"]))
    since = today - pd.Timedelta(days=MAX_FEATURE_AGE_DAYS + 10)
    features = load_feature_matrix(feature_path, since=since, columns=["timestamp", "symbol", *cols])
    asof = pd.Timestamp(features["timestamp"].max())
    if (today - asof.normalize()).days > MAX_FEATURE_AGE_DAYS:
        raise RuntimeError(f"Feature matrix is stale: latest {asof.date()}, today {today.date()}")
    coverage = validate_latest_cross_section(features)

    def write_atomic(frame: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp.parquet")
        if temp.exists():
            temp.unlink()
        frame.to_parquet(temp, index=False)
        temp.replace(path)

    main_pred = predict_latest(features, main_model, main_meta, generated_at=today)
    ov_pred = overlay_columns(predict_latest(features, ov_model, ov_meta, generated_at=today))
    write_atomic(main_pred, main_out)
    write_atomic(ov_pred, overlay_out)
    print(f"✅ Main predictions: {len(main_pred)} rows, feature_asof={asof.date()}, model={main_meta['model_id']}")
    print(f"✅ Overlay predictions: {len(ov_pred)} rows, model={ov_meta['model_id']}")
    print(f"✅ Universe coverage: {coverage['latest_symbols']}/{coverage['baseline_symbols']} "
          f"({coverage['coverage_ratio']:.1%})")

    return {"feature_asof": asof.date().isoformat(), "rows": len(main_pred),
            "main_model": main_meta["model_id"], "overlay_model": ov_meta["model_id"],
            **coverage}


def main() -> int:
    try:
        run()
    except Exception as exc:
        print(f"❌ Daily inference failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
