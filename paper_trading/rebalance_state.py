"""Persistent trading-session counter for the five-session rebalance cadence."""

import json
from pathlib import Path


def preview_rebalance_state(trading_date, state_file, frequency=5):
    """Return today's provisional session counter without mutating disk."""
    state = {"last_session_date": None, "last_rebalance_date": None,
             "sessions_since_rebalance": frequency}
    path = Path(state_file)
    if path.exists():
        with path.open('r') as f:
            state.update(json.load(f))

    if state.get("last_session_date") != trading_date:
        if state.get("last_rebalance_date") is None:
            state["sessions_since_rebalance"] = frequency
        else:
            state["sessions_since_rebalance"] = int(state.get("sessions_since_rebalance", 0)) + 1
        state["last_session_date"] = trading_date

    state["rebalance_due"] = int(state["sessions_since_rebalance"]) >= frequency
    return state


def commit_rebalance_state(state, rebalanced, state_file):
    """Persist a completed market session; reset the counter after rebalance."""
    saved = dict(state)
    saved.pop("rebalance_due", None)
    if rebalanced:
        saved["last_rebalance_date"] = saved["last_session_date"]
        saved["sessions_since_rebalance"] = 0
    path = Path(state_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp.json")
    temp.write_text(json.dumps(saved, indent=2), encoding="utf-8")
    temp.replace(path)
    return saved
