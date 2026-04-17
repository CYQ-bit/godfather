# Security & Secrets Guide

## What must never be committed

| File | Contains |
|------|----------|
| `.env.godfather` | Alpaca API keys, Telegram tokens |
| `.env.godfather_v91` | V9.1 sandbox credentials |
| `data/pt4_prep/broker_connection_config.json` | Alpaca API key + secret |
| `v91/data/pt4_prep/broker_connection_config.json` | V9.1 broker credentials |

These are all listed in `.gitignore`. **Never force-add them.**

---

## Setting up secrets safely

Always use the provided example files as templates:

```bash
# Environment variables
cp .env.example .env.godfather

# Broker config
cp config/broker_connection_config.example.json \
   data/pt4_prep/broker_connection_config.json
```

Then edit the copies with your real credentials. The example files contain only placeholder values and are safe to commit.

---

## Verifying no secrets are staged

Before any commit:

```bash
# Check for API key patterns
git diff --cached | grep -E "(PKTEST|PKPAPER|SKTEST|SKPAPER|bot[0-9]+:)"

# Check for .env files
git status | grep "\.env"

# Full scan
grep -r "APCA_API_KEY_ID\s*=\s*[A-Z0-9]\{10\}" . --include="*.py" --include="*.json" --include="*.sh"
```

---

## Rotating exposed credentials

If you accidentally commit credentials:

1. **Immediately** revoke the key at [app.alpaca.markets](https://app.alpaca.markets) → API Keys
2. Generate a new key pair
3. Update your local `.env.godfather` and `broker_connection_config.json`
4. Remove the secret from git history:
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch path/to/secret/file" \
     --prune-empty --tag-name-filter cat -- --all
   git push origin --force --all
   ```
5. Assume the old key is compromised — check Alpaca account for unauthorized activity

---

## Telegram bot security

The Telegram bot token in `.env.godfather` grants full control of your bot. If exposed:

1. Revoke via [@BotFather](https://t.me/BotFather): `/mybots` → select bot → API Token → Revoke
2. Generate a new token
3. Update `.env.godfather`

---

## Alpaca paper trading vs live trading

This system is configured for **paper trading only** (`base_url: https://paper-api.alpaca.markets`). Paper trading credentials are separate from live trading credentials. Even if paper credentials are exposed, they cannot access real funds.

To use live trading, you would need to:
1. Change `base_url` to `https://api.alpaca.markets`
2. Use live API credentials (not paper)
3. Thoroughly audit all risk controls before doing so

**This is not recommended without extensive testing.**
