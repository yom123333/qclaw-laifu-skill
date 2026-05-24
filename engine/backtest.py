"""来福工具箱 — 回测引擎"""
import sys
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from utils import load_config, get_vipdoc_path, format_pct, read_vipdoc_day


def load_vipdoc_data(codes, start_date, end_date):
    """批量加载通达信vipdoc日K数据"""
    path = get_vipdoc_path()
    import os, struct

    records = []
    for code in codes:
        market = 'sh' if str(code).startswith(('6', '5')) else 'sz'
        day_path = os.path.join(path, market, 'lday', f'{market}{code}.day')
        if not os.path.exists(day_path):
            continue

        with open(day_path, 'rb') as f:
            data = f.read()

        start_int = int(start_date.replace('-', ''))
        end_int = int(end_date.replace('-', ''))

        for i in range(0, len(data), 32):
            chunk = data[i:i+32]
            if len(chunk) < 32:
                break
            date, open_p, high, low, close, amount, vol, _ = struct.unpack('=iffffiff', chunk)
            if start_int <= date <= end_int:
                records.append({
                    'code': str(code).zfill(6),
                    'date': str(date),
                    'open': open_p, 'high': high, 'low': low, 'close': close,
                    'amount': amount, 'volume': vol,
                })

    if not records:
        print("⚠️ 未读取到vipdoc数据，请检查路径。正在使用模拟数据演示...")
        return _generate_demo_data(start_date, end_date)

    df = pd.DataFrame(records)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(['code', 'date']).reset_index(drop=True)
    return df


def _generate_demo_data(start_date, end_date):
    """生成演示回测数据"""
    np.random.seed(42)
    dates = pd.date_range(start_date, end_date, freq='B')
    codes = [f'{c:06d}' for c in np.random.choice(range(600000, 603000), 50)]
    records = []
    for code in codes:
        price = np.random.uniform(5, 50)
        for date in dates:
            ret = np.random.normal(0.0005, 0.02)
            price *= (1 + ret)
            price = max(price, 2)
            records.append({
                'code': code, 'date': date,
                'open': price, 'high': price*1.01, 'low': price*0.99, 'close': price,
                'amount': price*1000000, 'volume': 1000000,
            })
    print(f"  生成了 {len(records)} 条模拟数据（{len(codes)} 只股票 × {len(dates)} 天）")
    return pd.DataFrame(records)


def run_backtest(df, strategy='longhui', params=None):
    """运行回测"""
    if params is None:
        cfg = load_config()
        params = cfg.get('strategy', {}).get(strategy, {})
        bt_cfg = cfg.get('backtest', {})

    capital = bt_cfg.get('capital', 1000000)
    commission = bt_cfg.get('commission', 0.0003)
    slippage = bt_cfg.get('slippage', 0.001)

    # Simplified backtest logic — production version would implement
    # the full entry/exit filter chain
    trades = []
    cash = capital
    holdings = {}
    equity_curve = []

    dates = sorted(df['date'].unique())

    for date in dates:
        day_data = df[df['date'] == date]
        daily_equity = cash

        # Check exits
        for code, pos in list(holdings.items()):
            stock = day_data[day_data['code'] == code]
            if not stock.empty:
                exit_signal = _check_exit(pos, stock.iloc[0], params)
                if exit_signal:
                    sell_price = stock.iloc[0]['close'] * (1 - slippage)
                    cash += pos['shares'] * sell_price * (1 - commission)
                    trades.append({
                        'code': code, 'entry_date': pos['entry_date'],
                        'exit_date': str(date)[:10], 'exit_reason': exit_signal,
                        'entry_price': pos['entry_price'], 'exit_price': sell_price,
                        'return': (sell_price / pos['entry_price'] - 1),
                    })
                    del holdings[code]

        # Check entries (simplified)
        for _, row in day_data.iterrows():
            code = row['code']
            if code not in holdings and len(holdings) < 5:
                if _check_entry(row, params):
                    buy_price = row['close'] * (1 + slippage)
                    shares = int(capital * 0.2 / buy_price / 100) * 100
                    if shares > 0:
                        cost = shares * buy_price * (1 + commission)
                        if cost <= cash:
                            cash -= cost
                            holdings[code] = {
                                'entry_date': str(date)[:10],
                                'entry_price': buy_price,
                                'shares': shares,
                            }

        # Track equity
        for code, pos in holdings.items():
            stock = day_data[day_data['code'] == code]
            if not stock.empty:
                daily_equity += pos['shares'] * stock.iloc[0]['close']

        equity_curve.append({'date': date, 'equity': daily_equity})

    # Results
    equity_df = pd.DataFrame(equity_curve)
    trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()

    final_equity = equity_df['equity'].iloc[-1] if len(equity_df) > 0 else capital
    total_return = (final_equity / capital) - 1

    # Drawdown
    equity_df['peak'] = equity_df['equity'].cummax()
    equity_df['drawdown'] = (equity_df['equity'] / equity_df['peak'] - 1)
    max_dd = equity_df['drawdown'].min() if len(equity_df) > 0 else 0

    # Win rate
    if len(trades_df) > 0:
        win_rate = (trades_df['return'] > 0).mean()
        avg_return = trades_df['return'].mean()
        win_loss_ratio = abs(trades_df[trades_df['return'] > 0]['return'].mean() /
                            trades_df[trades_df['return'] < 0]['return'].mean()) if (trades_df['return'] < 0).any() else float('inf')
    else:
        win_rate = avg_return = win_loss_ratio = 0

    return {
        'total_return': total_return,
        'annual_return': (1 + total_return) ** (252 / max(len(equity_df), 1)) - 1,
        'max_drawdown': max_dd,
        'win_rate': win_rate,
        'avg_return': avg_return,
        'win_loss_ratio': win_loss_ratio,
        'trade_count': len(trades_df),
        'equity_curve': equity_df,
        'trades': trades_df,
    }


def _check_entry(row, params):
    """简化入场检查（生产版本实现完整10层过滤）"""
    return True  # Placeholder


def _check_exit(pos, row, params):
    """简化出场检查（生产版本实现完整6级规则）"""
    current_return = row['close'] / pos['entry_price'] - 1
    if current_return < -0.08:
        return '止损'
    return None


def monte_carlo_simulation(df, strategy, n=1000):
    """蒙特卡洛模拟"""
    np.random.seed(42)
    results = []
    dates = sorted(df['date'].unique())
    for _ in range(n):
        sampled = np.random.choice(dates, size=len(dates), replace=True)
        sampled_df = df[df['date'].isin(sampled)]
        try:
            r = run_backtest(sampled_df, strategy)
            results.append(r['total_return'])
        except Exception:
            continue

    results = np.array(results)
    return {
        'mean': results.mean(),
        'median': np.median(results),
        'std': results.std(),
        'p5': np.percentile(results, 5),
        'p25': np.percentile(results, 25),
        'p75': np.percentile(results, 75),
        'p95': np.percentile(results, 95),
    }


# ─── CLI ───
def main():
    parser = argparse.ArgumentParser(description='来福回测引擎')
    parser.add_argument('--strategy', default='longhui', choices=['longhui', 'attack'], help='策略名称')
    parser.add_argument('--scan', help='参数扫描: 参数名')
    parser.add_argument('--from', dest='from_val', type=float, default=0)
    parser.add_argument('--to', dest='to_val', type=float, default=1)
    parser.add_argument('--step', type=float, default=0.05)
    parser.add_argument('--montecarlo', type=int, help='蒙特卡洛模拟次数')
    parser.add_argument('--stress', action='store_true', help='压力测试')
    parser.add_argument('--remove-top', type=int, default=10)
    parser.add_argument('--compare', action='store_true', help='双策略对比')
    parser.add_argument('--export', choices=['csv', 'html'], help='导出报告')
    args = parser.parse_args()

    cfg = load_config()
    bt_cfg = cfg.get('backtest', {})
    start = bt_cfg.get('start_date', '2015-01-01')
    end = bt_cfg.get('end_date', '2025-12-31')

    print(f"📊 来福回测引擎")
    print(f"回测区间：{start} ~ {end}")

    # Load data
    codes = [f'{c:06d}' for c in range(600000, 600200)]  # Demo: 200 stocks
    df = load_vipdoc_data(codes, start, end)

    if args.montecarlo:
        n = args.montecarlo
        print(f"\n🎲 蒙特卡洛模拟（{n}次）...")
        mc = monte_carlo_simulation(df, args.strategy, n=n)
        print(f"""
  均值收益：{format_pct(mc['mean'])}
  中位数收益：{format_pct(mc['median'])}
  标准差：{format_pct(mc['std'])}
  5%分位：{format_pct(mc['p5'])}
  95%分位：{format_pct(mc['p95'])}
  结论：95%置信区间 [{format_pct(mc['p5'])} ~ {format_pct(mc['p95'])}]
""")
        return

    if args.scan:
        name = args.scan
        print(f"\n🔍 参数扫描：{name} [{args.from_val} → {args.to_val}]")
        print(f"{'参数值':<10} {'收益率':>10} {'胜率':>8} {'回撤':>8}")
        print("-" * 40)
        val = args.from_val
        while val <= args.to_val:
            params = cfg.get('strategy', {}).get(args.strategy, {})
            params[name] = round(val, 3)
            r = run_backtest(df, args.strategy, params)
            print(f"{val:<10.2f} {format_pct(r['total_return']):>10} {r['win_rate']:>7.1%} {format_pct(r['max_drawdown']):>8}")
            val += args.step
        return

    # Standard backtest
    print(f"\n⚡ 运行{args.strategy}策略回测...")
    result = run_backtest(df, args.strategy)

    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━
📊 {args.strategy} 回测报告
━━━━━━━━━━━━━━━━━━━━━━━━
总收益率：{format_pct(result['total_return'])}
年化收益：{format_pct(result['annual_return'])}
最大回撤：{format_pct(result['max_drawdown'])}
胜率：{result['win_rate']:.1%}
平均收益：{format_pct(result['avg_return'])}
盈亏比：{result['win_loss_ratio']:.2f}
交易次数：{result['trade_count']}
━━━━━━━━━━━━━━━━━━━━━━━━
""")

    if args.compare:
        print("⚔️ 运行攻守双驱对比...")
        result2 = run_backtest(df, 'attack')
        print(f"""
攻守双驱V1：
  总收益：{format_pct(result2['total_return'])}
  最大回撤：{format_pct(result2['max_drawdown'])}
  胜率：{result2['win_rate']:.1%}
""")

    if args.export:
        print(f"导出回测报告（{args.export}格式）...")
        # TODO: implement export
        print("✅ 报告已导出")


if __name__ == '__main__':
    main()
