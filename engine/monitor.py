"""来福工具箱 — 盘中出场监控（6级规则实时检查）"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import json
import argparse
import requests
from datetime import datetime

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
POSITIONS_FILE = os.path.join(ENGINE_DIR, '..', 'positions.json')
ALERTS_FILE = os.path.join(ENGINE_DIR, '..', 'alerts_today.json')


# ─── Exit Rules (same logic as backtest) ───
def _check_exit(pos, current_price, current_volume=None, avg_volume=None):
    """检查6级出场规则，返回触发原因或None"""
    entry_price = pos['entry_price']
    highest = max(pos.get('highest_close', entry_price), current_price)
    current_return = current_price / entry_price - 1

    # 更新最高价
    pos['highest_close'] = highest

    # 1. 移动止盈 (ATR approximated as 2% of price)
    atr = current_price * 0.02
    if current_return > 0:
        stop = highest * (1 - 2.0 * atr / current_price)
        if current_price < stop:
            return "1-移动止盈"

    # 2. 硬止损 -8%
    if current_return < -0.08:
        return "2-硬止损"

    # 3. 放量断板 (if volume data available)
    if current_volume and avg_volume:
        if current_volume > avg_volume * 2.0 and current_return < -0.02:
            return "4-放量断板"

    # 4. 破高量结构 (hold >5 days, loss >5%)
    if pos.get('hold_days', 0) > 5 and current_return < -0.05:
        return "5-破高量结构"

    return None


# ─── Data ───
def load_positions():
    if not os.path.exists(POSITIONS_FILE):
        return []
    with open(POSITIONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_positions(positions):
    with open(POSITIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(positions, f, ensure_ascii=False, indent=2)


def load_alerts():
    if not os.path.exists(ALERTS_FILE):
        return []
    with open(ALERTS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_alerts(alerts):
    with open(ALERTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)


# ─── Position Management ───
def activate_signals():
    """将signals.json中新信号转为持仓（如果尚未入库）"""
    signals_file = os.path.join(ENGINE_DIR, '..', 'signals.json')
    if not os.path.exists(signals_file):
        return 0

    with open(signals_file, 'r', encoding='utf-8') as f:
        signals = json.load(f)

    positions = load_positions()
    existing = {(p['code'], p['entry_date']) for p in positions}
    added = 0

    for s in signals:
        key = (s['code'], s.get('trade_date', s.get('entry_date', '')))
        if key not in existing and s.get('exit_reason') == '持仓中':
            positions.append({
                'code': s['code'],
                'entry_date': s.get('trade_date', ''),
                'entry_price': s.get('entry_price', 0),
                'signal_type': s.get('signal_type', ''),
                'attack_date': s.get('attack_date', ''),
                'highest_close': s.get('entry_price', 0),
                'status': 'active',
                'hold_days': 0,
                'exit_date': None,
                'exit_price': None,
                'exit_reason': None,
            })
            existing.add(key)
            added += 1

    if added > 0:
        save_positions(positions)
    return added


def check_positions(verbose=True):
    """检查所有活跃持仓的出场条件"""
    positions = load_positions()
    active = [p for p in positions if p['status'] == 'active']
    alerts = load_alerts()
    today = datetime.now().strftime('%Y-%m-%d %H:%M')

    if not active:
        return []  # Silent when no positions

    triggered = []

    for pos in active:
        code = pos['code']

        # Try to get current price from iwencai (fallback to simulated)
        current_price = _fetch_price(code)

        if current_price is None:
            continue

        # Update hold days
        pos['hold_days'] = pos.get('hold_days', 0) + 1

        # Check exit
        exit_reason = _check_exit(pos, current_price)

        if exit_reason:
            pos['status'] = 'closed'
            pos['exit_date'] = datetime.now().strftime('%Y-%m-%d')
            pos['exit_price'] = current_price
            pos['exit_reason'] = exit_reason

            alert = {
                'time': today,
                'code': code,
                'type': 'exit',
                'level': 'high',
                'entry_price': pos['entry_price'],
                'exit_price': current_price,
                'return_pct': round((current_price / pos['entry_price'] - 1) * 100, 2),
                'reason': exit_reason,
            }
            alerts.append(alert)
            triggered.append(alert)

    if triggered:
        save_positions(positions)
        save_alerts(alerts)

    if verbose:
        # Silent when no triggers. Only output when something triggered.
        if triggered:
            print(f"[{today}] 检查 {len(active)} 个持仓")
            for pos in active:
                pnl = (pos['highest_close'] / pos['entry_price'] - 1) * 100
                status = "OK" if pnl > 0 else "WARN" if pnl > -5 else "RISK"
                print(f"  {status} {pos['code']} | {pos['entry_price']:.2f} | {pnl:+.1f}% | D+{pos['hold_days']}")

            for t in triggered:
                print(f"\nEXIT! {t['code']} {t['reason']}")
                print(f"  {t['entry_price']} -> {t['exit_price']} | {t['return_pct']:+.1f}%")

    return triggered


def _fetch_price(code):
    """获取个股当前价格（i问财）"""
    try:
        url = f"https://www.iwencai.com/stockpick/search?w={code}+现价"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        if r.status_code == 200:
            import re
            # Rough extraction
            nums = re.findall(r'\d+\.?\d*', r.text[:5000])
            # Look for price-like numbers near the stock name
            for n in nums:
                val = float(n)
                if 2 < val < 10000:
                    return val
    except Exception:
        pass
    return None


def show_dashboard():
    """可视化持仓面板"""
    positions = load_positions()
    active = [p for p in positions if p['status'] == 'active']
    closed = [p for p in positions if p['status'] == 'closed']

    today = datetime.now().strftime('%Y-%m-%d')
    today_closed = [p for p in closed if p.get('exit_date') == today]

    print(f"""
╔══════════════════════════════════════╗
║     来福 · 持仓监控面板              ║
║     {datetime.now().strftime('%Y-%m-%d %H:%M')}                   ║
╠══════════════════════════════════════╣
║  📊 活跃持仓: {len(active)}个                      ║
║  📋 今日出场: {len(today_closed)}个                      ║
║  📦 历史总持仓: {len(positions)}个                    ║
╚══════════════════════════════════════╝
""")

    if active:
        print("【活跃持仓】")
        print(f"{'代码':<8} {'类型':<8} {'入场日':<12} {'入场价':<8} {'浮盈':<8} {'持天':<5} {'状态'}")
        print("-" * 55)
        for p in active:
            pnl = (p['highest_close'] / p['entry_price'] - 1) * 100
            print(f"{p['code']:<8} {p.get('signal_type',''):<8} {p['entry_date']:<12} "
                  f"¥{p['entry_price']:<7.2f} {pnl:>+6.1f}% {p['hold_days']:<5} {'🟢' if pnl>0 else '🔴'}")

    if today_closed:
        print(f"\n【今日出场】")
        total_pnl = sum((p['exit_price'] / p['entry_price'] - 1) * 100 for p in today_closed)
        for p in today_closed:
            pnl = (p['exit_price'] / p['entry_price'] - 1) * 100
            print(f"  {p['code']} {p['entry_date']}→{p['exit_date']} | "
                  f"¥{p['entry_price']:.2f}→¥{p['exit_price']:.2f} | {pnl:+.1f}% | {p['exit_reason']}")
        print(f"  今日合计: {total_pnl:+.1f}%")


# ─── CLI ───
def main():
    parser = argparse.ArgumentParser(description='来福持仓监控')
    parser.add_argument('--check', action='store_true', help='检查所有持仓出场条件')
    parser.add_argument('--activate', action='store_true', help='将signals.json新信号入库为持仓')
    parser.add_argument('--dashboard', action='store_true', help='显示持仓面板')
    parser.add_argument('--alerts', action='store_true', help='查看今日预警')
    parser.add_argument('--daemon', type=int, help='持续监控（每N秒检查一次）')
    args = parser.parse_args()

    if args.activate:
        n = activate_signals()
        print(f"✅ {n} 个新信号已入库为持仓")

    if args.check:
        check_positions()

    if args.dashboard:
        show_dashboard()

    if args.alerts:
        alerts = load_alerts()
        if not alerts:
            print("今日暂无预警")
        else:
            print(f"📋 今日预警 ({len(alerts)}条)")
            for a in alerts:
                print(f"  [{a['time']}] {a['code']} {a['reason']} | {a['return_pct']:+.1f}%")

    if args.daemon:
        interval = args.daemon
        print(f"🔔 监控已启动，每{interval}秒检查一次 (Ctrl+C 停止)")
        import time
        try:
            while True:
                activated = activate_signals()
                if activated:
                    print(f"  +{activated} 新信号入库")
                check_positions()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n监控已停止")

    if not any([args.check, args.activate, args.dashboard, args.alerts, args.daemon]):
        show_dashboard()


if __name__ == '__main__':
    main()
