"""
Validate Confidence Engine v1
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alpha_factory.confidence_engine import ConfidenceEngine, load_confidence_snapshot
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))


def validate_confidence_engine():
    """验证 Confidence Engine"""
    print("=" * 60)
    print("CONFIDENCE ENGINE V1 VALIDATION")
    print("=" * 60)

    engine = ConfidenceEngine()
    result, pred_df = engine.run()

    print(f"\n✓ CONFIDENCE_ENGINE_OK")
    print(f"✓ AVG_CONFIDENCE={result['avg_confidence']:.4f}")
    print(f"✓ HIGH_CONF_COUNT={result['high_conf_count']}")
    print(f"✓ MID_CONF_COUNT={result['mid_conf_count']}")
    print(f"✓ LOW_CONF_COUNT={result['low_conf_count']}")

    # 验证文件生成
    snapshot_file = (_REPO_ROOT / 'data/ai_engine/latest_confidence_snapshot.json')
    history_file = (_REPO_ROOT / 'data/ai_engine/confidence_history.csv')

    assert snapshot_file.exists(), "Snapshot file not created"
    assert history_file.exists(), "History file not created"

    print(f"\n✓ Snapshot file: {snapshot_file}")
    print(f"✓ History file: {history_file}")

    # 验证加载
    loaded = load_confidence_snapshot()
    assert loaded is not None, "Failed to load snapshot"
    assert abs(loaded['avg_confidence'] - result['avg_confidence']) < 0.001

    print(f"\n✓ Snapshot reload OK")

    # 验证权重调节
    assert engine.get_confidence_multiplier('high') == 1.3
    assert engine.get_confidence_multiplier('mid') == 1.0
    assert engine.get_confidence_multiplier('low') == 0.6

    print(f"\n✓ WEIGHT_ADJUSTMENT_OK")
    print("\n" + "=" * 60)
    print("CONFIDENCE ENGINE V1 VALIDATION PASSED")
    print("=" * 60)


if __name__ == '__main__':
    validate_confidence_engine()
