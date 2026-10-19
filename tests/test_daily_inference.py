import pandas as pd
import pytest

from ml_lab import model_v10 as mv
from ml_lab import run_daily_inference as rdi
from tests.test_model_v10 import SMALL, make_market


@pytest.fixture
def setup(tmp_path, monkeypatch):
    _, feats, labels = make_market()
    ov_cfg = mv.ModelConfig(**{**SMALL.__dict__, "name": "test_ov"})
    monkeypatch.setattr(rdi, "MAIN_CONFIG", SMALL)
    monkeypatch.setattr(rdi, "OVERLAY_CONFIG", ov_cfg)
    mv.train(feats, labels, SMALL, model_dir=tmp_path, verbose=False)
    fpath = tmp_path / "features.parquet"
    feats.to_parquet(fpath, index=False)
    return tmp_path, fpath, feats, labels, ov_cfg


def test_daily_inference_writes_fresh_files(setup):
    model_dir, fpath, feats, labels, ov_cfg = setup
    mv.train(feats, labels, ov_cfg, model_dir=model_dir, verbose=False)
    asof = feats["timestamp"].max()
    today = asof + pd.Timedelta(days=3)
    out = rdi.run(fpath, model_dir, model_dir / "main.parquet", model_dir / "ov.parquet", today=today)
    main = pd.read_parquet(model_dir / "main.parquet")
    ov = pd.read_parquet(model_dir / "ov.parquet")
    assert out["feature_asof"] == str(asof.date())
    assert mv.check_prediction_freshness(main, str(today.date())) is None
    assert mv.check_prediction_freshness(ov, str(today.date())) is None
    assert {"overlay_score", "overlay_confidence", "overlay_filter_flag"} <= set(ov.columns)


def test_daily_inference_refuses_stale_features(setup):
    model_dir, fpath, feats, *_ = setup
    with pytest.raises(RuntimeError, match="stale"):
        rdi.run(fpath, model_dir, model_dir / "main.parquet", model_dir / "ov.parquet",
                today=feats["timestamp"].max() + pd.Timedelta(days=10))


def test_daily_inference_removes_old_overlay_when_model_missing(setup):
    model_dir, fpath, feats, *_ = setup
    old = model_dir / "ov.parquet"
    pd.DataFrame({"x": [1]}).to_parquet(old)
    rdi.run(fpath, model_dir, model_dir / "main.parquet", old,
            today=feats["timestamp"].max() + pd.Timedelta(days=1))
    assert not old.exists()


def test_daily_inference_fails_without_model(tmp_path):
    with pytest.raises(FileNotFoundError):
        rdi.run(tmp_path / "f.parquet", tmp_path, tmp_path / "m.parquet", tmp_path / "o.parquet")


def test_no_mock_signal_left():
    src = open("ml_lab/run_fresh_predictions.py", encoding="utf-8").read()
    code = src.split('"""', 2)[-1]  # ignore the docstring explaining what was removed
    assert "alpha_0002" not in code and "random" not in code
    for sh in ("scripts/run_godfather_pt44_full_daily.sh", "scripts/run_godfather_pt44_daily.sh"):
        assert "run_daily_inference.py" in open(sh, encoding="utf-8").read()
