# Quickstart Guide

## Prerequisites

- Python 3.10+
- Alpaca paper trading account (free at [alpaca.markets](https://alpaca.markets))
- macOS or Linux

---

## 1. Clone and set up environment

```bash
git clone https://github.com/CYQ-bit/godfather.git
cd godfather
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 2. Configure secrets

```bash
cp .env.example .env.godfather
```

Edit `.env.godfather`:

```bash
# Alpaca paper trading credentials
APCA_API_KEY_ID=your_alpaca_key_id
APCA_API_SECRET_KEY=your_alpaca_secret_key
APCA_BASE_URL=https://paper-api.alpaca.markets

# Optional: Telegram alerts
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Create broker connection config:

```bash
mkdir -p data/pt4_prep
cp config/broker_connection_config.example.json data/pt4_prep/broker_connection_config.json
```

Edit `data/pt4_prep/broker_connection_config.json` with your Alpaca credentials.

---

## 3. Set up data lake

The system needs a price data lake. Set the path via environment variable:

```bash
export GODFATHER_DATA_LAKE_ROOT=/path/to/your/data_lake
```

Or place data in `data/data_lake/` (relative to repo root).

The data lake expects:
```
data_lake/
├── prices/          # Daily OHLCV parquet files per ticker
└── universe/
    └── sp500_universe.csv
```

---

## 4. Run the dashboard (demo mode)

No data or broker needed:

```bash
GODFATHER_DEMO=1 streamlit run control_center/app.py
```

Open http://localhost:8501

---

## 5. Run the pipeline manually

```bash
# Refresh features
python alpha_factory/run_feature_refresh.py

# Generate predictions
python ml_lab/run_fresh_predictions.py

# Run full daily pipeline (bypasses time window)
FORCE_RUN=1 bash scripts/run_godfather_pt44_full_daily.sh
```

---

## 6. Schedule as a daily service (macOS launchd)

```bash
# Set GODFATHER_ROOT in your environment first
export GODFATHER_ROOT=$(pwd)

# Bootstrap launchd services
bash scripts/bootstrap_godfather_all.sh

# Check status
bash scripts/check_godfather_status.sh
```

The main scheduler (`pt44`) runs daily at market open (09:00–10:30 ET).

---

## Environment variables reference

| Variable | Required | Description |
|----------|----------|-------------|
| `GODFATHER_ROOT` | No | Path to V9.0 repo root (defaults to script-relative) |
| `GODFATHER_V91_ROOT` | No | Path to V9.1 sandbox root |
| `GODFATHER_DATA_LAKE_ROOT` | No | Path to price data lake |
| `GODFATHER_UNIVERSE_PATH` | No | Path to universe CSV |
| `GODFATHER_DEMO` | No | Set to `1` for demo mode dashboard |
| `APCA_API_KEY_ID` | Yes | Alpaca API key |
| `APCA_API_SECRET_KEY` | Yes | Alpaca secret key |
| `APCA_BASE_URL` | No | Alpaca base URL (default: paper) |
| `TELEGRAM_BOT_TOKEN` | No | Telegram bot token for alerts |
| `TELEGRAM_CHAT_ID` | No | Telegram chat ID for alerts |
