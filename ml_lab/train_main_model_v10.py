"""
Train Main Model V10.

Purged split (train | embargo | valid | embargo | lockbox), IC-based feature
selection on the training split, execution-aligned label, and a saved model
that ml_lab/run_daily_inference.py loads every day. See ml_lab/model_v10.py.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml_lab.model_v10 import MAIN_CONFIG, run_training_cli


def main():
    meta = run_training_cli(MAIN_CONFIG)
    print(f"MODEL_ID={meta['model_id']}")
    print("✓ MAIN_MODEL_TRAINED=YES")
    return meta


if __name__ == "__main__":
    main()
