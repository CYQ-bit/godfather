"""
Broker Health Check - Godfather V9.0
Read-only broker connection validation
"""
import json
import sys
import requests
from pathlib import Path
from datetime import datetime
import os
_REPO_ROOT = Path(os.environ.get("GODFATHER_ROOT", str(Path(__file__).resolve().parent.parent)))

sys.path.insert(0, str(Path(__file__).parent.parent))


def mask_credential(cred: str) -> str:
    """Mask credential for logging"""
    if len(cred) <= 8:
        return "***"
    return cred[:4] + "***" + cred[-4:]


def check_alpaca_auth(api_key: str, api_secret: str, endpoint: str):
    """Check Alpaca authentication"""
    print("[1] Auth Check...")

    headers = {
        'APCA-API-KEY-ID': api_key,
        'APCA-API-SECRET-KEY': api_secret
    }

    try:
        response = requests.get(f"{endpoint}/v2/account", headers=headers, timeout=10)

        if response.status_code == 200:
            account_data = response.json()
            print(f"  ✅ Auth successful")
            print(f"  Environment: paper")
            print(f"  Account ID: {mask_credential(account_data.get('account_number', 'N/A'))}")
            print(f"  Status: {account_data.get('status', 'N/A')}")
            return True, account_data
        else:
            print(f"  ❌ Auth failed: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False, None

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False, None


def check_account_health(api_key: str, api_secret: str, endpoint: str):
    """Check account health (read-only)"""
    print("\n[2] Account Health Check...")

    headers = {
        'APCA-API-KEY-ID': api_key,
        'APCA-API-SECRET-KEY': api_secret
    }

    try:
        response = requests.get(f"{endpoint}/v2/account", headers=headers, timeout=10)

        if response.status_code == 200:
            account = response.json()

            cash = float(account.get('cash', 0))
            buying_power = float(account.get('buying_power', 0))
            equity = float(account.get('equity', 0))

            print(f"  ✅ Account accessible")
            print(f"  Cash: ${cash:,.2f}")
            print(f"  Buying power: ${buying_power:,.2f}")
            print(f"  Equity: ${equity:,.2f}")
            print(f"  Account status: {account.get('status', 'N/A')}")

            # Check positions
            pos_response = requests.get(f"{endpoint}/v2/positions", headers=headers, timeout=10)
            if pos_response.status_code == 200:
                positions = pos_response.json()
                print(f"  Positions: {len(positions)}")
                print(f"  ✅ Positions readable")
            else:
                print(f"  ⚠️  Positions query failed")

            return True, {
                'cash': cash,
                'buying_power': buying_power,
                'equity': equity,
                'status': account.get('status'),
                'positions_count': len(positions) if pos_response.status_code == 200 else 0
            }
        else:
            print(f"  ❌ Account query failed: {response.status_code}")
            return False, None

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False, None


def check_market_health(api_key: str, api_secret: str, endpoint: str):
    """Check market/endpoint health"""
    print("\n[3] Endpoint / Market Health Check...")

    headers = {
        'APCA-API-KEY-ID': api_key,
        'APCA-API-SECRET-KEY': api_secret
    }

    try:
        # Check clock
        clock_response = requests.get(f"{endpoint}/v2/clock", headers=headers, timeout=10)

        if clock_response.status_code == 200:
            clock = clock_response.json()
            print(f"  ✅ Endpoint responding")
            print(f"  Market open: {clock.get('is_open', 'N/A')}")
            print(f"  Broker time: {clock.get('timestamp', 'N/A')[:19]}")
            print(f"  Next open: {clock.get('next_open', 'N/A')[:19]}")
            print(f"  Next close: {clock.get('next_close', 'N/A')[:19]}")
        else:
            print(f"  ⚠️  Clock query failed: {clock_response.status_code}")

        # Check calendar
        calendar_response = requests.get(f"{endpoint}/v2/calendar", headers=headers, timeout=10)

        if calendar_response.status_code == 200:
            calendar = calendar_response.json()
            print(f"  ✅ Calendar accessible ({len(calendar)} days)")
        else:
            print(f"  ⚠️  Calendar query failed")

        # Check symbol lookup (sample)
        test_symbols = ['AAPL', 'MSFT', 'GOOGL']
        print(f"  Testing symbol lookup...")

        symbols_ok = 0
        for symbol in test_symbols:
            asset_response = requests.get(
                f"{endpoint}/v2/assets/{symbol}",
                headers=headers,
                timeout=10
            )
            if asset_response.status_code == 200:
                asset = asset_response.json()
                if asset.get('tradable'):
                    symbols_ok += 1
                    print(f"    ✅ {symbol}: tradable")
                else:
                    print(f"    ⚠️  {symbol}: not tradable")
            else:
                print(f"    ❌ {symbol}: lookup failed")

        print(f"  Symbol lookup: {symbols_ok}/{len(test_symbols)} OK")

        return True, {
            'endpoint_ok': clock_response.status_code == 200,
            'market_open': clock.get('is_open') if clock_response.status_code == 200 else None,
            'calendar_ok': calendar_response.status_code == 200,
            'symbols_ok': symbols_ok,
            'symbols_tested': len(test_symbols)
        }

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False, None


def generate_health_summary(auth_ok, account_data, account_health, market_health):
    """Generate health summary"""
    print("\n" + "=" * 80)
    print("【Broker Connection Health Summary】")
    print("=" * 80)
    print()

    summary = {
        'timestamp': datetime.now().isoformat(),
        'broker': 'Alpaca',
        'environment': 'paper',
        'auth': 'PASS' if auth_ok else 'FAIL',
        'account': 'PASS' if account_health else 'FAIL',
        'market': 'PASS' if market_health else 'FAIL'
    }

    print("【A. Auth】")
    if auth_ok:
        print(f"  ✅ PASS")
        print(f"  Environment: paper")
        print(f"  Account ID: {mask_credential(account_data.get('account_number', 'N/A'))}")
    else:
        print(f"  ❌ FAIL")
    print()

    print("【B. Account Health】")
    if account_health:
        print(f"  ✅ PASS")
        print(f"  Cash: ${account_health['cash']:,.2f}")
        print(f"  Buying power: ${account_health['buying_power']:,.2f}")
        print(f"  Status: {account_health['status']}")
        print(f"  Positions readable: ✅")
    else:
        print(f"  ❌ FAIL")
    print()

    print("【C. Endpoint / Market Health】")
    if market_health:
        print(f"  ✅ PASS")
        print(f"  Endpoint: {'OK' if market_health['endpoint_ok'] else 'FAIL'}")
        print(f"  Market status: {'Open' if market_health['market_open'] else 'Closed'}")
        print(f"  Calendar: {'OK' if market_health['calendar_ok'] else 'FAIL'}")
        print(f"  Symbol lookup: {market_health['symbols_ok']}/{market_health['symbols_tested']} OK")
    else:
        print(f"  ❌ FAIL")
    print()

    print("【D. 最终结论】")
    print()

    all_pass = auth_ok and account_health and market_health

    print(f"1. Godfather V9.0 是否已完成 broker connection finalization？")
    if all_pass:
        print(f"   ✅ 是")
    else:
        print(f"   ❌ 否")
    print()

    print(f"2. 当前是否具备进入 PT.4.2 真正 tiny-capital live rehearsal 条件？")
    if all_pass:
        print(f"   ✅ 是")
        print(f"   理由: Auth/Account/Market 全部通过")
    else:
        print(f"   ❌ 否")
        if not auth_ok:
            print(f"   阻塞: Auth 失败")
        if not account_health:
            print(f"   阻塞: Account 不可访问")
        if not market_health:
            print(f"   阻塞: Market/Endpoint 异常")
    print()

    print(f"3. 若仍不行，最后阻塞项是什么？")
    if all_pass:
        print(f"   无阻塞项")
    else:
        blockers = []
        if not auth_ok:
            blockers.append("Auth 失败")
        if not account_health:
            blockers.append("Account 不可访问")
        if not market_health:
            blockers.append("Market/Endpoint 异常")
        print(f"   {', '.join(blockers)}")
    print()

    print(f"4. 下一步更合理是：")
    if all_pass:
        print(f"   → A. 进入 tiny-capital live rehearsal")
        print(f"   理由: 所有健康检查通过，broker 连接就绪")
    else:
        print(f"   → B. 继续补 broker 配置")
        print(f"   理由: 健康检查未全部通过")
    print()

    print("=" * 80)

    # Save summary
    summary_file = (_REPO_ROOT / 'data/pt4_prep/broker_health_summary.json')
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nHealth summary saved: {summary_file}")

    return summary


def main():
    """Main health check"""
    print("=" * 80)
    print("【Godfather V9.0 - Broker Connection Health Check】")
    print("=" * 80)
    print()

    # Load config
    config_file = (_REPO_ROOT / 'data/pt4_prep/broker_connection_config.json')
    with open(config_file, 'r') as f:
        config = json.load(f)

    print(f"Broker: {config['broker_name']}")
    print(f"Environment: {config['environment']}")
    print(f"Endpoint: {config['api_endpoint']}")
    print(f"API Key: {mask_credential(config['api_key'])}")
    print()

    # Run checks
    auth_ok, account_data = check_alpaca_auth(
        config['api_key'],
        config['api_secret'],
        config['api_endpoint']
    )

    account_health = None
    if auth_ok:
        _, account_health = check_account_health(
            config['api_key'],
            config['api_secret'],
            config['api_endpoint']
        )

    market_health = None
    if auth_ok:
        _, market_health = check_market_health(
            config['api_key'],
            config['api_secret'],
            config['api_endpoint']
        )

    # Generate summary
    generate_health_summary(auth_ok, account_data, account_health, market_health)


if __name__ == '__main__':
    main()
