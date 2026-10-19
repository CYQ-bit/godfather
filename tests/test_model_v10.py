"""Synthetic-data tests for the V10 training / inference / fail-closed path."""
import numpy as np
import pandas as pd
import pytest

from ml_lab import model_v10 as mv
from ml_lab.model_v10 import ModelConfig

SMALL = ModelConfig(name="test_v10", train_days=200, valid_days=60, lockbox_days=60,
                    max_features=3, num_boost_round=60, early_stopping=10,
                    params={"learning_rate": 0.1, "num_leaves": 7, "min_data_in_leaf": 50})


def make_market(n_sym=80, n_days=450, signal=0.5, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-03", periods=n_days)
    syms = [f"S{i:03d}" for i in range(n_sym)]
    rets = rng.normal(0, 0.02, size=(n_days, n_sym))
    opens = 100 * np.exp(np.cumsum(rets, axis=0))
    prices = pd.DataFrame({"timestamp": np.repeat(dates, n_sym), "symbol": np.tile(syms, n_days),
                           "open": opens.ravel()})
    labels = mv.build_exec_label(prices)
    feats = labels[["timestamp", "symbol"]].copy()
    fut = labels["label"].fillna(0).to_numpy()
    # alpha_0000 carries the (future) label plus noise; the rest is noise.
    feats["alpha_0000"] = signal * fut / 0.045 + rng.normal(0, 1, len(feats))
    for k in range(1, 8):
        feats[f"alpha_{k:04d}"] = rng.normal(0, 1, len(feats))
    return prices, feats, labels


# ---------------------------------------------------------------- label

def test_exec_label_is_open_t1_to_open_t6():
    dates = pd.bdate_range("2024-01-01", periods=10)
    prices = pd.DataFrame({"timestamp": dates, "symbol": "A", "open": np.arange(1.0, 11.0)})
    lab = mv.build_exec_label(prices).set_index("timestamp")["label"]
    assert lab.iloc[0] == pytest.approx(7.0 / 2.0 - 1)   # open[1]=2 -> open[6]=7
    assert lab.iloc[3] == pytest.approx(10.0 / 5.0 - 1)
    assert lab.iloc[4:].isna().all()                       # no future data yet


def test_exec_label_does_not_mix_symbols():
    dates = pd.bdate_range("2024-01-01", periods=8)
    prices = pd.concat([pd.DataFrame({"timestamp": dates, "symbol": s, "open": v})
                        for s, v in (("A", 1.0), ("B", 2.0))])
    lab = mv.build_exec_label(prices)
    assert set(lab["label"].dropna().round(12)) == {0.0}


# ---------------------------------------------------------------- split

def test_purged_split_gaps_cover_label_span():
    dates = pd.bdate_range("2020-01-01", periods=500)
    sp = mv.purged_split(dates, SMALL)
    pos = {d: i for i, d in enumerate(dates)}
    assert pos[sp["valid"][0]] - pos[sp["train"][-1]] > mv.LABEL_SPAN
    assert pos[sp["lockbox"][0]] - pos[sp["valid"][-1]] > mv.LABEL_SPAN
    assert sp["lockbox"][-1] == dates[-1]
    assert len(sp["train"]) == SMALL.train_days


def test_purged_split_rejects_short_history():
    with pytest.raises(ValueError):
        mv.purged_split(pd.bdate_range("2020-01-01", periods=100), SMALL)


# ---------------------------------------------------------------- selection

def test_ic_selection_finds_signal():
    _, feats, labels = make_market()
    df = feats.merge(labels, on=["timestamp", "symbol"]).dropna(subset=["label"])
    cols = [c for c in feats.columns if c.startswith("alpha_")]
    sel, stats = mv.select_features_by_ic(df, cols, 3)
    assert sel[0] == "alpha_0000"
    assert stats.iloc[0]["ic_mean"] > 0.1


def test_daily_rank_ic_matches_pandas_spearman():
    _, feats, labels = make_market(n_days=30)
    df = feats.merge(labels, on=["timestamp", "symbol"]).dropna(subset=["label"])
    fast = mv.daily_rank_ic(df, "alpha_0000")
    slow = df.groupby("timestamp").apply(lambda x: x["alpha_0000"].corr(x["label"], method="spearman"))
    np.testing.assert_allclose(fast.to_numpy(), slow.loc[fast.index].to_numpy(), atol=1e-10)


# ---------------------------------------------------------------- train + infer

@pytest.fixture
def trained(tmp_path):
    _, feats, labels = make_market()
    meta = mv.train(feats, labels, SMALL, model_dir=tmp_path, verbose=False)
    return tmp_path, feats, labels, meta


def test_train_saves_model_and_lockbox_metrics(trained):
    model_dir, _, labels, meta = trained
    assert (model_dir / meta["model_file"]).exists()
    assert (model_dir / "test_v10_current.json").exists()
    assert "alpha_0000" in meta["features"]
    assert meta["lockbox_metrics"]["model_ic_mean"] > 0.1
    last_labelled = labels.dropna(subset=["label"])["timestamp"].max()
    assert meta["trained_through"] == str(last_labelled.date())


def test_train_never_uses_target_column(tmp_path):
    """Old matrices carry a close-to-close 'target'; it must never be a feature."""
    _, feats, labels = make_market()
    feats = feats.merge(labels.rename(columns={"label": "target"}), on=["timestamp", "symbol"])
    meta = mv.train(feats, labels, SMALL, model_dir=tmp_path, verbose=False)
    assert "target" not in meta["features"]


def test_feature_selection_ignores_data_after_training_split(tmp_path):
    """Scrambling valid/lockbox rows must not change which features get picked."""
    _, feats, labels = make_market()
    meta1 = mv.train(feats, labels, SMALL, model_dir=tmp_path / "a", verbose=False)
    train_end = pd.Timestamp(meta1["train"][1])
    rng = np.random.default_rng(1)
    tampered = feats.copy()
    late = tampered["timestamp"] > train_end
    for c in [c for c in feats.columns if c.startswith("alpha_")]:
        tampered.loc[late, c] = rng.normal(0, 1, late.sum())
    meta2 = mv.train(tampered, labels, SMALL, model_dir=tmp_path / "b", verbose=False)
    assert meta1["features"] == meta2["features"]


def test_predict_latest_only_uses_latest_date(trained):
    model_dir, feats, _, _ = trained
    model, meta = mv.load_current_model("test_v10", model_dir)
    pred = mv.predict_latest(feats, model, meta)
    latest = feats["timestamp"].max()
    assert (pred["timestamp"] == latest).all()
    assert pred["symbol"].nunique() == feats["symbol"].nunique()
    assert set(mv.PRED_META_COLS) <= set(pred.columns)

    # Changing earlier rows must not change today's prediction.
    tampered = feats.copy()
    tampered.loc[tampered["timestamp"] < latest, meta["features"]] = 999.0
    pred2 = mv.predict_latest(tampered, model, meta)
    np.testing.assert_allclose(pred["y_pred"], pred2["y_pred"])


def test_predict_latest_rejects_missing_features(trained):
    model_dir, feats, _, _ = trained
    model, meta = mv.load_current_model("test_v10", model_dir)
    with pytest.raises(ValueError):
        mv.predict_latest(feats.drop(columns=[meta["features"][0]]), model, meta)


def test_load_current_model_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        mv.load_current_model("nope", tmp_path)


# ---------------------------------------------------------------- freshness

def _pred(asof="2026-10-16", trained="2026-10-01", **extra):
    df = pd.DataFrame({"symbol": ["A", "B"], "y_pred": [0.1, -0.1], "feature_asof": asof,
                       "model_id": "m1", "trained_through": trained, "generated_at": "x"})
    for k, v in extra.items():
        df[k] = v
    return df


def test_freshness_accepts_prior_business_day():
    assert mv.check_prediction_freshness(_pred("2026-10-16"), "2026-10-19") is None  # Fri -> Mon


@pytest.mark.parametrize("pred,trading,word", [
    (_pred("2026-10-09"), "2026-10-19", "stale"),
    (_pred("2026-10-19"), "2026-10-19", "not before"),
    (_pred(trained="2026-06-01"), "2026-10-19", "retrain"),
    (_pred().drop(columns=["feature_asof"]), "2026-10-19", "lacks"),
    (_pred(model_id=["m1", "m2"]), "2026-10-19", "model ids"),
    (_pred().iloc[0:0], "2026-10-19", "empty"),
])
def test_freshness_rejects(pred, trading, word):
    reason = mv.check_prediction_freshness(pred, trading)
    assert reason is not None and word in reason


def test_freshness_rejects_mixed_dates():
    df = pd.concat([_pred("2026-10-15"), _pred("2026-10-16")])
    assert "mixes feature dates" in mv.check_prediction_freshness(df, "2026-10-19")
