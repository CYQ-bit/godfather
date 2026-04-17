"""
Validate Regime Engine v1
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alpha_factory.regime_engine import RegimeEngine, load_regime_state
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))


def validate_regime_engine():
    """验证 Regime Engine"""
    print("=" * 60)
    print("REGIME ENGINE V1 VALIDATION")
    print("=" * 60)

    engine = RegimeEngine()
    result = engine.run()

    print(f"\n✓ REGIME_ENGINE_OK")
    print(f"✓ REGIME_STATE={result['state_name']}")
    print(f"✓ REGIME_BUDGET_MULTIPLIER={result['budget_multiplier']}")
    print(f"✓ REGIME_HOLD_BUFFER={result['hold_buffer']}")

    print(f"\nFeatures:")
    for k, v in result['features'].items():
        print(f"  {k}: {v:.4f}")

    # 验证文件生成
    state_file = (_REPO_ROOT / 'data/ai_engine/daily_regime_state.json')
    history_file = (_REPO_ROOT / 'data/ai_engine/regime_history.csv')

    assert state_file.exists(), "State file not created"
    assert history_file.exists(), "History file not created"

    print(f"\n✓ State file: {state_file}")
    print(f"✓ History file: {history_file}")

    # 验证加载
    loaded = load_regime_state()
    assert loaded is not None, "Failed to load state"
    assert loaded['state_name'] == result['state_name']

    print(f"\n✓ State reload OK")
    print("\n" + "=" * 60)
    print("REGIME ENGINE V1 VALIDATION PASSED")
    print("=" * 60)


if __name__ == '__main__':
    validate_regime_engine()
