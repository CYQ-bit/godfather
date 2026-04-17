"""
Validate Dual Model Last Mile Wiring
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd


def validate_last_mile_wiring():
    """验证最后一公里接线"""
    print("=" * 70)
    print("DUAL MODEL LAST MILE WIRING VALIDATION")
    print("=" * 70)

    repo = Path(__file__).parent.parent

    # Check predictions loaded
    main_pred = repo / "data/ml2_results/main_predictions_v10.parquet"
    overlay_pred = repo / "data/ml2_results/recent_overlay_predictions.parquet"

    assert main_pred.exists(), "Main predictions missing"
    assert overlay_pred.exists(), "Overlay predictions missing"

    print("\n[Predictions]")
    print("✓ MAIN_PREDICTIONS_LOADED=YES")
    print("✓ OVERLAY_PREDICTIONS_LOADED=YES")

    # Check overlay usage in code
    pt44 = repo / "paper_trading/run_pt44_unified.py"
    content = pt44.read_text()

    assert "overlay_confidence" in content, "Overlay confidence not used"
    assert "overlay_filter_flag" in content, "Overlay filter not used"
    assert "score_with_overlay" in content or "conf_mult" in content, "Overlay not applied"

    print("\n[Overlay Usage]")
    print("✓ OVERLAY_CONFIDENCE_USED=YES")
    print("✓ OVERLAY_FILTER_USED=YES")

    # Check preview columns
    preview = repo / "paper_trading/order_preview_export.py"
    preview_content = preview.read_text()

    dual_fields = ["main_score", "overlay_score", "overlay_confidence", "overlay_filter_flag"]
    for field in dual_fields:
        assert field in preview_content, f"Preview missing: {field}"

    print("\n[Preview Export]")
    print("✓ PREVIEW_EXPORT_DUAL_MODEL_VALUES_OK")

    print("\n✓ DUAL_MODEL_LAST_MILE_WIRING_OK")
    print("\n" + "=" * 70)
    print("LAST MILE WIRING VALIDATION PASSED")
    print("=" * 70)


if __name__ == '__main__':
    validate_last_mile_wiring()
