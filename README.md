# Godfather — Quantitative Trading System

A production-grade quantitative trading system for US equities, built around a daily alpha-factor pipeline, XGBoost-based ML predictions, and automated paper trading via Alpaca.

> **Paper trading only.** This system is designed and tested exclusively with Alpaca paper trading accounts. It does not support live brokerage accounts out of the box.

---

## What it does

Godfather runs a daily pipeline:

1. **Feature refresh** — builds a cross-sectional alpha factor matrix from price/volume data
2. **ML prediction** — XGBoost dual-model (main + recent overlay) generates stock rankings
3. **Portfolio construction** — top-N rotation with regime-aware position sizing
4. **Order preview** — generates and validates order previews before submission
5. **Execution** — submits orders via Alpaca paper trading API within the 10:00–10:30 ET window
6. **Reconciliation** — post-trade sync and fill verification

The `v91/` directory contains the V9.1 sandbox — a parallel instance for strategy experimentation.

---

## Project structure

```
godfather/
├── alpha_factory/          # Feature engineering & alpha signals
│   ├── alpha_engine.py     # Core factor computation
│   ├── regime_engine.py    # Market regime detection
│   ├── confidence_engine.py # Signal confidence scoring
│   └── run_feature_refresh.py
├── ml_lab/                 # ML model training & prediction
│   ├── walkforward_trainer.py
│   ├── run_fresh_predictions.py
│   └── train_main_model_v10.py
├── paper_trading/          # Execution & broker integration
│   ├── broker_connection.py
│   ├── run_pt44_unified.py # Main daily execution entry point
│   └── INCIDENT_RUNBOOK.md
├── portfolio_lab/          # Portfolio construction research
├── control_center/         # Streamlit monitoring dashboard
│   └── app.py
├── scripts/                # Shell wrappers & service management
│   ├── run_godfather_pt44_full_daily.sh  # Main daily scheduler
│   └── godfather_service_manager.py
├── config/services/        # launchd service definitions
├── runtime_paths.py        # Centralized path resolution
├── .env.example            # Environment variable template
└── v91/                    # V9.1 sandbox (parallel instance)
```

---

## Requirements

- Python 3.10+
- Alpaca paper trading account (free at [alpaca.markets](https://alpaca.markets))
- macOS (launchd service management) or Linux (adapt scripts)
- ~2 GB disk for data lake

```bash
pip install -r requirements.txt
```

---

## Quick setup

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for step-by-step instructions.

```bash
cp .env.example .env.godfather
# Edit .env.godfather with your Alpaca API keys

cp config/broker_connection_config.example.json data/pt4_prep/broker_connection_config.json
# Edit with your Alpaca credentials
```

---

## Running the dashboard (demo mode)

```bash
GODFATHER_DEMO=1 streamlit run control_center/app.py
```

This shows the full UI with sample data — no broker account needed.

---

## Running the full pipeline

```bash
# One-shot manual run (bypasses time window checks)
FORCE_RUN=1 bash scripts/run_godfather_pt44_full_daily.sh

# Scheduled daily run (respects 09:00–10:30 ET window)
bash scripts/run_godfather_pt44_full_daily.sh
```

---

## Security

See [docs/SECURITY_AND_SECRETS.md](docs/SECURITY_AND_SECRETS.md) before committing or deploying.

**Never commit** `.env.godfather` or `broker_connection_config.json` — they contain real API keys.

---

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design details.

---

## Disclaimer

This software is for educational and research purposes. Paper trading results do not guarantee live trading performance. Use at your own risk.
