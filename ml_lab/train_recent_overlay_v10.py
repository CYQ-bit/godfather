"""
Train Recent Overlay V10 (short window). Same purged pipeline as the main
model; see ml_lab/model_v10.py. Daily overlay scores come from
ml_lab/run_daily_inference.py.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml_lab.model_v10 import OVERLAY_CONFIG, run_training_cli


def main():
    meta = run_training_cli(OVERLAY_CONFIG)
    print(f"MODEL_ID={meta['model_id']}")
    print("✓ OVERLAY_MODEL_TRAINED=YES")
    return meta


if __name__ == "__main__":
    main()
