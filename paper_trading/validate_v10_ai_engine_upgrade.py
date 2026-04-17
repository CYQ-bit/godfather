"""
V10.0 AI Engine Upgrade - 总验证
"""
import sys
from pathlib import Path
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))
sys.path.insert(0, str(Path(__file__).parent.parent))


def validate_v10_ai_engine_upgrade():
    """V10.0 总验证"""
    print("=" * 70)
    print("GODFATHER V10.0 AI ENGINE UPGRADE - FINAL VALIDATION")
    print("=" * 70)

    results = {}

    # 1. Regime Engine
    print("\n[1/5] Validating Regime Engine...")
    try:
        from alpha_factory.regime_engine import load_regime_state
        regime = load_regime_state()
        assert regime is not None
        assert 'state_name' in regime
        results['REGIME_ENGINE_OK'] = True
        print("✓ REGIME_ENGINE_OK")
    except Exception as e:
        results['REGIME_ENGINE_OK'] = False
        print(f"✗ REGIME_ENGINE_FAILED: {e}")

    # 2. Confidence Engine
    print("\n[2/5] Validating Confidence Engine...")
    try:
        from alpha_factory.confidence_engine import load_confidence_snapshot
        conf = load_confidence_snapshot()
        assert conf is not None
        assert 'avg_confidence' in conf
        results['CONFIDENCE_ENGINE_OK'] = True
        print("✓ CONFIDENCE_ENGINE_OK")
    except Exception as e:
        results['CONFIDENCE_ENGINE_OK'] = False
        print(f"✗ CONFIDENCE_ENGINE_FAILED: {e}")

    # 3. Position Sizing V10
    print("\n[3/5] Validating Position Sizing V10...")
    try:
        from paper_trading.position_sizing_v10 import apply_v10_adjustments
        import pandas as pd
        test_df = pd.DataFrame({'symbol': ['AAPL'], 'target_weight': [1.0]})
        result = apply_v10_adjustments(test_df)
        assert 'weight_v10' in result.columns
        results['POSITION_SIZING_V10_OK'] = True
        print("✓ POSITION_SIZING_V10_OK")
    except Exception as e:
        results['POSITION_SIZING_V10_OK'] = False
        print(f"✗ POSITION_SIZING_V10_FAILED: {e}")

    # 4. Short Interest
    print("\n[4/5] Validating Short Interest...")
    try:
        from alpha_factory.external_data_short_interest import ShortInterestDataProvider
        provider = ShortInterestDataProvider()
        data = provider.load_latest()
        assert data is not None
        results['SHORT_INTEREST_FEATURES_OK'] = True
        print("✓ SHORT_INTEREST_FEATURES_OK")
    except Exception as e:
        results['SHORT_INTEREST_FEATURES_OK'] = False
        print(f"✗ SHORT_INTEREST_FAILED: {e}")

    # 5. Dashboard
    print("\n[5/5] Validating Dashboard...")
    try:
        app_file = (_REPO_ROOT / 'control_center/app.py')
        content = app_file.read_text()
        assert 'render_v10_ai_engine_status' in content
        results['DASHBOARD_V10_OK'] = True
        print("✓ DASHBOARD_V10_OK")
    except Exception as e:
        results['DASHBOARD_V10_OK'] = False
        print(f"✗ DASHBOARD_FAILED: {e}")

    # 总结
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    for key, val in results.items():
        status = "✓ PASS" if val else "✗ FAIL"
        print(f"{status} - {key}")

    all_pass = all(results.values())
    print("\n" + "=" * 70)
    if all_pass:
        print("✓ V10_AI_ENGINE_UPGRADE_OK")
        print("=" * 70)
        return True
    else:
        print("✗ V10_AI_ENGINE_UPGRADE_FAILED")
        print("=" * 70)
        return False


if __name__ == '__main__':
    success = validate_v10_ai_engine_upgrade()
    sys.exit(0 if success else 1)
