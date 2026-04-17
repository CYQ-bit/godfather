# Architecture

## System overview

Godfather is a daily-batch quantitative trading system. It runs once per trading day, generating predictions pre-market and submitting orders at market open.

```
┌─────────────────────────────────────────────────────────────┐
│                    Daily Pipeline (10:00 ET)                 │
│                                                             │
│  Data Lake ──► Feature Matrix ──► ML Predictions ──► Orders │
│  (prices)      (alpha_factory)    (ml_lab)          (pt44)  │
└─────────────────────────────────────────────────────────────┘
         │                                        │
         ▼                                        ▼
  Regime Engine                          Alpaca Paper API
  Confidence Engine                      Fill Reconciliation
```

---

## Modules

### `alpha_factory/` — Feature engineering

- `alpha_engine.py` — computes cross-sectional alpha factors (momentum, volatility, mean-reversion, etc.)
- `regime_engine.py` — detects market regime (bull/bear/neutral) using rolling statistics
- `confidence_engine.py` — scores signal confidence per stock
- `run_feature_refresh.py` — entry point: reads price data, writes `data/feature_store/ml_alpha_matrix.parquet`

### `ml_lab/` — Machine learning

- `walkforward_trainer.py` — rolling walk-forward cross-validation trainer
- `train_main_model_v10.py` — trains the main XGBoost model (26-week rolling window)
- `train_recent_overlay_v10.py` — trains a recent-data overlay model (8-week window)
- `run_fresh_predictions.py` — generates daily predictions using trained models

Dual-model architecture: main model provides stable long-term signal; overlay model captures recent regime shifts. Final prediction blends both.

### `paper_trading/` — Execution

- `broker_connection.py` — Alpaca API wrapper
- `run_pt44_unified.py` — main execution entry: reads predictions, constructs orders, submits via broker
- `broker_local_sync.py` — syncs broker state to local JSON files
- `broker_recon_adapter.py` — reconciles fills against local ledger
- `hard_stop_rules.py` — circuit breakers (max drawdown, position limits)

### `portfolio_lab/` — Research

Historical research scripts for portfolio construction experiments. Not part of the live pipeline.

### `control_center/` — Dashboard

Streamlit dashboard showing live system state:
- Service health (launchd status)
- Pipeline stage status (feature → prediction → validation → execution)
- Account state (cash, equity, holdings)
- Fill reconciliation status
- Log viewer

Run with `GODFATHER_DEMO=1` for sample data without a broker.

### `scripts/` — Orchestration

Shell wrappers that:
1. Set `QUANT_LAB_DIR` to the repo root
2. Load `.env.godfather`
3. Run the appropriate Python entry point
4. Log to `logs/`

`godfather_service_manager.py` manages launchd plist generation and service lifecycle.

---

## Data flow

```
data/
├── data_lake/              # Input: price/volume data (external)
│   ├── prices/             # Per-ticker OHLCV parquet files
│   └── universe/           # S&P 500 universe CSV
├── feature_store/          # Intermediate: alpha factor matrix
│   └── ml_alpha_matrix.parquet
├── ml2_results/            # Intermediate: ML predictions
│   ├── predictions_8window.parquet
│   └── recent_overlay_predictions.parquet
├── pt4_prep/               # Config: broker credentials
│   └── broker_connection_config.json
├── paper_trading/
│   ├── latest_order_preview.json   # Today's order preview
│   ├── state/                      # Persistent state
│   │   ├── fills_ledger.json
│   │   ├── broker_state.json
│   │   └── daily_run_log.json
│   └── dashboard/                  # Dashboard summary
│       └── dashboard_summary.json
└── ai_engine/              # V10 AI engine state
    ├── daily_regime_state.json
    └── latest_confidence_snapshot.json
```

---

## Scheduling

The main scheduler (`run_godfather_pt44_full_daily.sh`) enforces a time window:

- Before 09:00 ET: skip (too early)
- 09:00–10:00 ET: run feature refresh + predictions, then wait for 10:00
- 10:00–10:30 ET: submit orders
- After 10:30 ET: abort (missed window)

Weekend detection is built in. Use `FORCE_RUN=1` to bypass all time checks.

---

## V9.1 Sandbox

The `v91/` directory is a parallel instance for strategy experimentation. It has its own data directory, logs, and launchd service. It shares the same codebase but runs independently.

Set `GODFATHER_V91_ROOT` to point at the `v91/` directory (or it defaults to `<repo_root>/v91`).
