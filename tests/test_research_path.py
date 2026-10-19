from datetime import timedelta

import pandas as pd
import pytest

from ml_lab.oos_backtester import OOSBacktester


def test_walkforward_windows_have_embargo():
    pl = pytest.importorskip("polars")
    pytest.importorskip("xgboost")
    from ml_lab.walkforward_trainer import WalkForwardTrainer

    dates = pd.date_range("2020-01-01", "2023-12-31", freq="D")
    df = pl.from_pandas(pd.DataFrame({"timestamp": dates, "symbol": "A"}))
    windows = WalkForwardTrainer(train_months=12, test_months=2, embargo_days=10).generate_windows(df)
    assert windows
    for _, train_end, test_start, _ in windows:
        assert test_start - train_end == timedelta(days=10)


def test_backtest_charges_cost_on_turnover_only():
    dates = pd.bdate_range("2024-01-01", periods=20)
    rows = [{"timestamp": d, "symbol": f"S{i}", "y_pred": i, "y_true": 0.0}
            for d in dates for i in range(10)]
    pf = OOSBacktester().create_portfolio(pd.DataFrame(rows), top_pct=0.2, bottom_pct=0.2,
                                          holding_days=5, cost_bps=10)
    # Same names every period: build cost once (2 legs x full turnover x 2 sides), then nothing.
    assert pf["cost"].iloc[0] == pytest.approx(2 * 2 * 10 / 1e4)
    assert (pf["cost"].iloc[1:] == 0).all()
    assert pf["ls_return"].iloc[0] < 0
