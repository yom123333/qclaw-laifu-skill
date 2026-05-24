"""来福工具箱 — 信号扫描器（全市场+单股检查+历史追踪）"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import argparse
import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from utils import (
    load_config, get_vipdoc_path, get_all_stock_codes, read_stock_day,
    calc_ma, calc_angle, find_attack_day, format_pct
)

SIGNAL_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'signals.json')


def _check_entry(df, idx, attack_idx, params, market_score=60):
    """10层过滤检查（同回测引擎）"""
    row = df.iloc[idx]
    attack_row = df.iloc[attack_idx]

    days = idx - attack_idx
    if days < params.get('time_window_min', 3) or days > params.get('time_window_max', 12):
        return False

    if attack_row['volume'] == 0:
        return False
    shrink = row['volume'] / attack_row['volume']
    if shrink < params.get('shrink_ratio_min', 0.25) or shrink > params.get('shrink_ratio_max', 0.55):
        return False

    floor = attack_row['close'] * params.get('price_discount', 0.98)
    if row['close'] < floor:
        return False

    if idx < 22:
        return False
    ma_now = calc_ma(df['close'].iloc[:idx+1], 20).iloc[-1]
    ma_prev = calc_ma(df['close'].iloc[:idx], 20).iloc[-1]
    if ma_now <= ma_prev:
        return False

    if idx < 4:
        return False
    ang = calc_angle(df['close'].iloc[:idx+1], 3)
    if ang < params.get('ang3_min', 0):
        return False

    recent_low = df['low'].iloc[max(0,idx-10):idx+1].min()
    if row['close'] < recent_low * 0.99:
        return False

    daily_chg = row['close'] / df.iloc[idx-1]['close'] - 1
    if daily_chg < params.get('stop_daily_loss', -0.03):
        return False

    if market_score < params.get('market_green_light', 50):
        return False

    return True


def scan_all(quick=False):
    """全市场信号扫描"""
    cfg = load_config()
    params = cfg.get('strategy', {}).get('longhui', {})

    try:
        codes = get_all_stock_codes()
    except FileNotFoundError:
        if quick:
            # Demo mode: generate mock signals for testing
            print("  [Demo] No vipdoc, generating sample signals...")
            import numpy as np
            np.random.seed(42)
            demo_codes = np.random.choice([f'{c:06d}' for c in range(600000, 603000)], 20)
            today = datetime.now()
            demo_signals = []
            for i, code in enumerate(demo_codes):
                d = today - timedelta(days=np.random.randint(1, 12))
                demo_signals.append({
                    'code': code, 'name': '', 'signal_type': '弱势吸' if i % 3 == 0 else '强势吸',
                    'trade_date': d.strftime('%Y-%m-%d'),
                    'entry_price': round(np.random.uniform(8, 45), 2),
                    'attack_date': (d - timedelta(days=np.random.randint(3,12))).strftime('%Y-%m-%d'),
                    'shrink_ratio': round(np.random.uniform(0.28, 0.52), 2),
                    'days_since_attack': np.random.randint(3, 12),
                    'exit_reason': '持仓中',
                })
            return sorted(demo_signals, key=lambda x: x['trade_date'], reverse=True)
        print("[ERROR] vipdoc not found. Set tdx.vipdoc_path in config.yaml")
        return []

    if quick:
        codes = codes[:200]

    print(f"📡 扫描 {len(codes)} 只股票...")
    signals = []
    today = datetime.now()

    for i, code in enumerate(codes):
        if (i + 1) % 500 == 0:
            print(f"  进度: {i+1}/{len(codes)} | 已发现 {len(signals)} 个信号")

        df = read_stock_day(code)
        if df is None or len(df) < 30:
            continue

        # Check last few days for signals
        last_idx = len(df) - 1
        for idx in range(max(0, last_idx - 15), last_idx):
            if idx < 22:
                continue

            # Find attack day
            attack_idx = None
            for ai in range(idx - params.get('time_window_max', 12),
                           idx - params.get('time_window_min', 3) + 1):
                if ai >= 0 and find_attack_day(df, ai):
                    attack_idx = ai
                    break
            if attack_idx is None:
                continue

            if _check_entry(df, idx, attack_idx, params):
                row = df.iloc[idx]
                attack_row = df.iloc[attack_idx]
                shrink = row['volume'] / attack_row['volume'] if attack_row['volume'] > 0 else 0

                signals.append({
                    'code': code,
                    'name': '',
                    'signal_type': '弱势吸' if shrink < 0.4 else '强势吸',
                    'trade_date': row['date'].strftime('%Y-%m-%d'),
                    'entry_price': round(row['close'], 2),
                    'attack_date': attack_row['date'].strftime('%Y-%m-%d'),
                    'shrink_ratio': round(shrink, 3),
                    'days_since_attack': idx - attack_idx,
                    'exit_reason': '持仓中',
                })
                break  # One signal per stock

    # Sort by date
    signals.sort(key=lambda x: x['trade_date'], reverse=True)
    return signals


def print_signal_report(signals):
    """格式化输出信号报告"""
    if not signals:
        print("\n📡 今日暂无符合策略条件的信号")
        return

    print(f"\n{'='*50}")
    print(f"📡 来福信号扫描 · {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*50}")
    print(f"活跃信号: {len(signals)} 个")

    types = {}
    for s in signals:
        t = s['signal_type']
        types[t] = types.get(t, 0) + 1
    print("类型: " + " | ".join(f"{k}:{v}" for k, v in types.items()))

    shrink_ranges = {'25-35%': 0, '35-50%': 0, '50-60%': 0}
    for s in signals:
        sr = s['shrink_ratio']
        if sr < 0.35: shrink_ranges['25-35%'] += 1
        elif sr < 0.50: shrink_ranges['35-50%'] += 1
        else: shrink_ranges['50-60%'] += 1
    print("缩量: " + " | ".join(f"{k}:{v}" for k, v in shrink_ranges.items() if v > 0))

    print(f"\n{'代码':<8} {'类型':<8} {'入场日':<12} {'入场价':<8} {'缩量比':<8} {'窗口':<6}")
    print("-" * 52)
    for s in signals:
        print(f"{s['code']:<8} {s['signal_type']:<8} {s['trade_date']:<12} "
              f"¥{s['entry_price']:<7} {s['shrink_ratio']:.0%}{'':<5} {s['days_since_attack']}天")


def save_signals(signals):
    """保存信号到本地数据库"""
    existing = []
    if os.path.exists(SIGNAL_DB):
        with open(SIGNAL_DB, 'r', encoding='utf-8') as f:
            existing = json.load(f)

    # Merge: update existing, add new
    existing_codes = {(s['code'], s['trade_date']) for s in existing}
    for s in signals:
        key = (s['code'], s['trade_date'])
        if key not in existing_codes:
            existing.append(s)
            existing_codes.add(key)

    with open(SIGNAL_DB, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    return existing


def show_history(days=30):
    """显示历史信号追踪"""
    if not os.path.exists(SIGNAL_DB):
        print("暂无历史信号数据，请先运行 --scan")
        return

    with open(SIGNAL_DB, 'r', encoding='utf-8') as f:
        all_signals = json.load(f)

    if not all_signals:
        print("暂无历史信号")
        return

    # Recent signals
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    recent = [s for s in all_signals if s['trade_date'] >= cutoff]

    active = [s for s in recent if s.get('exit_reason') == '持仓中']
    exited = [s for s in recent if s.get('exit_reason') != '持仓中']

    print(f"\n📈 近{days}天信号追踪")
    print(f"{'='*50}")
    print(f"总计: {len(recent)} | 持仓中: {len(active)} | 已出场: {len(exited)}")

    if exited:
        returns = []
        for s in exited:
            if 'exit_price' in s and s['entry_price'] > 0:
                returns.append(s['exit_price'] / s['entry_price'] - 1)
        if returns:
            print(f"出场上均收益: {format_pct(np.mean(returns))}")
            print(f"出场胜率: {(np.array(returns)>0).mean():.0%}")


def main():
    parser = argparse.ArgumentParser(description='来福信号扫描器')
    parser.add_argument('--scan', action='store_true', help='全市场扫描')
    parser.add_argument('--quick', action='store_true', help='快速扫描（200只）')
    parser.add_argument('--today', action='store_true', help='查看今日信号')
    parser.add_argument('--check', help='检查特定股票代码')
    parser.add_argument('--history', type=int, default=30, help='查看历史信号天数')
    parser.add_argument('--by-sector', action='store_true', help='按板块分组（需联网）')
    args = parser.parse_args()

    if args.scan or args.today:
        signals = scan_all(quick=args.quick)
        all_signals = save_signals(signals)
        print_signal_report(signals)

    elif args.check:
        code = args.check.strip()
        df = read_stock_day(code)
        if df is None:
            print(f"❌ 未找到 {code} 的数据")
            return
        print(f"🔍 {code} 最近20个交易日:")
        print(df.tail(20)[['date', 'close', 'volume']].to_string(index=False))

        # Quick signal check
        params = load_config().get('strategy', {}).get('longhui', {})
        last_idx = len(df) - 1
        found = False
        for idx in range(max(0, last_idx - 12), last_idx + 1):
            attack_idx = None
            for ai in range(idx - 12, idx - 2):
                if ai >= 0 and find_attack_day(df, ai):
                    attack_idx = ai
                    break
            if attack_idx and _check_entry(df, idx, attack_idx, params):
                row = df.iloc[idx]
                attack_row = df.iloc[attack_idx]
                print(f"\n✅ 检测到信号！")
                print(f"  攻击日: {attack_row['date'].strftime('%Y-%m-%d')} "
                      f"涨停价: ¥{attack_row['close']:.2f}")
                print(f"  信号日: {row['date'].strftime('%Y-%m-%d')} "
                      f"入场价: ¥{row['close']:.2f}")
                shrink = row['volume'] / attack_row['volume'] if attack_row['volume'] > 0 else 0
                print(f"  缩量比: {shrink:.1%} | 窗口: {idx-attack_idx}天")
                found = True
                break
        if not found:
            print(f"\n❌ 该股当前不满足龙回2号入场条件")

    elif args.history:
        show_history(args.history)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
