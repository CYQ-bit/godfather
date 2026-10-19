import pandas as pd
import pytest

from alpha_factory.confidence_engine import ConfidenceEngine
from paper_trading.position_sizing_v10 import apply_v10_adjustments
from paper_trading.rebalance_state import (
    commit_rebalance_state,
    preview_rebalance_state,
)


def test_lowest_confidence_value_is_in_low_bucket():
    pred = pd.DataFrame({"symbol": ["A", "B", "C"], "y_pred": [0.1, 0.2, 0.3]})
    result = ConfidenceEngine().compute_confidence(pred).set_index("symbol")
    assert str(result.loc["A", "confidence_bucket"]) == "low"


def test_regime_multiplier_changes_total_exposure():
    target = pd.DataFrame({"stock_code": ["A", "B"], "target_weight": [0.5, 0.5]})
    confidence = pd.DataFrame({
        "symbol": ["A", "B"],
        "confidence_bucket": ["mid", "mid"],
        "confidence_score": [1.0, 1.0],
    })
    regime = {"budget_multiplier": 0.2, "hold_buffer": 0.5, "state_name": "risk_off"}
    result = apply_v10_adjustments(target, regime=regime, conf_df=confidence)
    assert result["weight_v10"].sum() == pytest.approx(0.2)


def test_rebalance_counter_persists_five_processed_sessions(tmp_path):
    state_file = tmp_path / "rebalance.json"
    dates = pd.bdate_range("2026-10-19", periods=6).strftime("%Y-%m-%d").tolist()

    first = preview_rebalance_state(dates[0], state_file=state_file)
    assert first["rebalance_due"] is True
    commit_rebalance_state(first, rebalanced=True, state_file=state_file)

    for date in dates[1:5]:
        state = preview_rebalance_state(date, state_file=state_file)
        assert state["rebalance_due"] is False
        commit_rebalance_state(state, rebalanced=False, state_file=state_file)

    fifth = preview_rebalance_state(dates[5], state_file=state_file)
    assert fifth["rebalance_due"] is True


def test_rebalance_preview_is_read_only(tmp_path):
    state_file = tmp_path / "rebalance.json"
    state = preview_rebalance_state("2026-10-19", state_file=state_file)
    assert state["rebalance_due"] is True
    assert not state_file.exists()
