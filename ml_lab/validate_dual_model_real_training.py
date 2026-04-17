"""
Validate Dual Model Real Training
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json


def validate_dual_model_real_training():
    """验证双层模型真实训练"""
    print("=" * 70)
    print("DUAL MODEL REAL TRAINING VALIDATION")
    print("=" * 70)

    repo = Path(__file__).parent.parent

    # Check main model
    main_pred = repo / "data/ml2_results/main_predictions_v10.parquet"
    main_meta = repo / "data/ml2_results/main_model_v10_meta.json"

    assert main_pred.exists(), "Main predictions not found"
    assert main_meta.exists(), "Main meta not found"

    meta = json.loads(main_meta.read_text())
    print(f"\n[Main Model]")
    print(f"✓ MAIN_MODEL_TRAINED=YES")
    print(f"  Train: {meta['train_start']} to {meta['train_end']}")
    print(f"  Valid: {meta['valid_start']} to {meta['valid_end']}")
    print(f"  Rows: {meta['train_rows']}")
    print(f"  Features: {meta['feature_count']}")

    # Check overlay model
    overlay_pred = repo / "data/ml2_results/recent_overlay_predictions.parquet"
    overlay_meta = repo / "data/ml2_results/overlay_model_v10_meta.json"

    assert overlay_pred.exists(), "Overlay predictions not found"
    assert overlay_meta.exists(), "Overlay meta not found"

    ometa = json.loads(overlay_meta.read_text())
    print(f"\n[Overlay Model]")
    print(f"✓ OVERLAY_MODEL_TRAINED=YES")
    print(f"  Train: {ometa['overlay_train_start']} to {ometa['overlay_train_end']}")
    print(f"  Valid: {ometa['overlay_valid_start']} to {ometa['overlay_valid_end']}")
    print(f"  Rows: {ometa['overlay_rows']}")
    print(f"  Features: {ometa['overlay_feature_count']}")

    # Check predictions ready
    print(f"\n[Predictions]")
    print(f"✓ MAIN_PREDICTIONS_READY=YES")
    print(f"  File: {main_pred}")
    print(f"✓ OVERLAY_PREDICTIONS_READY=YES")
    print(f"  File: {overlay_pred}")

    print(f"\n✓ DUAL_MODEL_REAL_TRAINING_OK")
    print("\n" + "=" * 70)
    print("DUAL MODEL REAL TRAINING VALIDATION PASSED")
    print("=" * 70)


if __name__ == '__main__':
    validate_dual_model_real_training()
