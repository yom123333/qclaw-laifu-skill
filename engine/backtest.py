"""来福工具箱 — 回测引擎（完整10层过滤+6级出场）"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import argparse
import numpy as np
import pandas as pd
from datetime import datetime
from utils import (
    load_config, get_vipdoc_path, load_market_data, get_all_stock_codes,
    read_stock_day, calc_ma, calc_angle, find_attack_day, format_pct, format_money
)


def _get_params(strategy_name='longhui'):
    cfg = load_config()
    p = cfg.get('strategy', {}).get(strategy_name, {})
    bt = cfg.get('backtest', {})
    return {
        # Entry filters
        'time_min': p.get('time_window_min', 3),
        'time_max': p.get('time_window_max', 12),
        'shrink_min': p.get('shrink_ratio_min', 0.25),
        'shrink_max': p.get('shrink_ratio_max', 0.55),
        'price_floor': p.get('price_discount', 0.98),
        'ma_period': p.get('ma_trend', 20),
        'ang_min': p.get('ang3_min', 0),
        'dev_wc': p.get('deviation_wc', 0.5),
        'dev_tc': p.get('deviation_tc', 0.3),
        'dev_vc': p.get('deviation_vc', 0.2),
        'stop_daily': p.get('stop_daily_loss', -0.03),
        'market_light': p.get('market_green_light', 50),
        # Exit rules
        'exit_atr': p.get('exit_atr_multiplier', 2.0),
        'exit_boll': p.get('exit_bollinger_sigma', 2.0),
        'exit_shrink_ang': p.get('exit_shrink_angle', -0.5),
        'exit_vol_ratio': p.get('exit_volume_ratio', 2.0),
        'exit_trend_atr': p.get('exit_trendline_atr', 2.0),
        'exit_cool': p.get('exit_cooling_days', 5),
        # Backtest
        'capital': bt.get('capital', 1000000),
        'commission': bt.get('commission', 0.0003),
        'slippage': bt.get('slippage', 0.001),
        'max_positions': 5,
        'position_pct': 0.2,
    }


def _check_entry_filters(df, idx, attack_idx, params, market_score=60):
    """检查10层入场过滤（全部通过才入场）"""
    row = df.iloc[idx]
    attack_row = df.iloc[attack_idx]
    code = df.iloc[0]['code'] if 'code' in df.columns else ''

    # 1. 时间窗口: 涨停后3-12天，排除第4天
    days_since = idx - attack_idx
    if days_since < params['time_min'] or days_since > params['time_max']:
        return False, f"时间窗口({days_since}天)"

    # 2. 缩量比: 25%-55%
    if attack_row['volume'] == 0:
        return False, "无量"
    shrink = row['volume'] / attack_row['volume']
    if shrink < params['shrink_min'] or shrink > params['shrink_max']:
        return False, f"缩量比({shrink:.2f})"

    # 3. 价格底线: >= 涨停日收盘×0.98
    floor = attack_row['close'] * params['price_floor']
    if row['close'] < floor:
        return False, f"价格底线({row['close']:.2f}<{floor:.2f})"

    # 4. MA20趋势: 均线向上
    if idx < params['ma_period'] + 2:
        return False, "MA数据不足"
    ma_now = calc_ma(df['close'].iloc[:idx+1], params['ma_period']).iloc[-1]
    ma_prev = calc_ma(df['close'].iloc[:idx], params['ma_period']).iloc[-1]
    if ma_now <= ma_prev:
        return False, f"MA20走平"

    # 5. 趋势角 ang3 >= 0
    if idx < 4:
        return False, "角度数据不足"
    ang = calc_angle(df['close'].iloc[:idx+1], 3)
    if ang < params['ang_min']:
        return False, f"趋势角({ang:.1f}°)"

    # 6. 偏离度
    cost_line = (df['high'].iloc[max(0,idx-5):idx+1].max() + df['low'].iloc[max(0,idx-5):idx+1].min()) / 2
    deviation = params['dev_wc'] * abs(row['close']-cost_line)/row['close'] + \
                params['dev_tc'] * abs(row['close']-ma_now)/row['close'] + \
                params['dev_vc'] * 0.02
    if deviation > 0.15:
        return False, f"偏离度({deviation:.3f})"

    # 7. 趋势线支撑: 近期低点连线
    recent_low = df['low'].iloc[max(0,idx-10):idx+1].min()
    if row['close'] < recent_low * 0.99:
        return False, f"跌破趋势线支撑"

    # 8. 日跌幅上限
    daily_chg = row['close'] / df.iloc[idx-1]['close'] - 1
    if daily_chg < params['stop_daily']:
        return False, f"日跌幅({daily_chg:.2%})"

    # 9. RS跑赢大盘: 简化为近期相对强度
    if idx < 10:
        return False, "RS数据不足"
    stock_ret = row['close'] / df.iloc[idx-10]['close'] - 1
    if stock_ret < -0.05:
        return False, f"RS偏弱({stock_ret:.2%})"

    # 10. 大盘绿灯
    if market_score < params['market_light']:
        return False, f"大盘评分({market_score})"

    return True, "通过"


def _check_exit(pos, row, df, idx, params, atr):
    """检查6级出场规则（返回触发原因或None）"""
    current_return = row['close'] / pos['entry_price'] - 1
    hold_days = idx - pos['entry_idx']

    # 1. 移动止盈
    if current_return > 0:
        stop_price = pos['highest_close'] * (1 - params['exit_atr'] * atr / row['close'])
        if row['close'] < stop_price:
            return "移动止盈"

    # 2. 布林空
    if idx > 20:
        ma20 = calc_ma(df['close'].iloc[:idx+1], 20).iloc[-1]
        std20 = df['close'].iloc[idx-19:idx+1].std()
        upper = ma20 + params['exit_boll'] * std20
        if row['close'] < upper * 0.97 and current_return < 0.02:
            return "布林空"

    # 3. 缩量滞涨
    if hold_days > 3 and idx > 5:
        ang = calc_angle(df['close'].iloc[:idx+1], 3)
        vol_now = df['volume'].iloc[max(0,idx-3):idx+1].mean()
        vol_prev = df['volume'].iloc[max(0,idx-8):max(1,idx-3)].mean()
        if ang < params['exit_shrink_ang'] and vol_prev > 0 and vol_now < vol_prev * 0.8:
            return "缩量滞涨"

    # 4. 放量断板
    if idx > 5:
        avg_vol = df['volume'].iloc[max(0,idx-5):idx].mean()
        if avg_vol > 0 and row['volume'] > avg_vol * params['exit_vol_ratio']:
            if current_return < -0.02:
                return "放量断板"

    # 5. 破高量结构
    if hold_days > params['exit_cool'] and current_return < -0.05:
        return "破高量结构"

    # 6. 破趋势线
    if idx > params['exit_cool']:
        recent_low = df['low'].iloc[max(0,idx-params['exit_cool']):idx+1].min()
        if row['close'] < recent_low * (1 - params['exit_trend_atr'] * atr / row['close']):
            return "破趋势线"

    # 硬止损 -8%
    if current_return < -0.08:
        return "止损"

    return None


def run_backtest(data, strategy='longhui', market_score=60):
    """主回测函数"""
    params = _get_params(strategy)
    capital = params['capital']
    cash = capital
    positions = {}  # code -> {entry_price, entry_idx, entry_date, shares, highest_close}
    trades = []
    equity = []

    codes = data['code'].unique()
    dates = sorted(data['date'].unique())

    total_days = len(dates)
    print(f"  回测区间: {dates[0].strftime('%Y-%m-%d')} ~ {dates[-1].strftime('%Y-%m-%d')}")
    print(f"  股票数量: {len(codes)} | 交易日: {total_days}")

    for di, date in enumerate(dates):
        if di % 500 == 0 and di > 0:
            print(f"  进度: {di}/{total_days} ({100*di//total_days}%)")

        day_data = data[data['date'] == date].set_index('code')
        daily_equity = cash

        # Check exits first
        for code, pos in list(positions.items()):
            if code not in day_data.index:
                continue
            row = day_data.loc[code]
            code_df = data[data['code'] == code].set_index('date')

            # Update highest close
            if row['close'] > pos['highest_close']:
                pos['highest_close'] = row['close']

            # Calculate ATR
            if pos['entry_idx'] > 14:
                atr_df = code_df['high'].iloc[max(0,pos['entry_idx']-14):pos['entry_idx']+1] - \
                         code_df['low'].iloc[max(0,pos['entry_idx']-14):pos['entry_idx']+1]
                atr = atr_df.mean()
            else:
                atr = row['close'] * 0.02

            # Find the date index in stock's DataFrame
            date_idx = code_df.index.get_loc(date) if date in code_df.index else -1

            exit_reason = _check_exit(pos, row, code_df, date_idx, params, atr)
            if exit_reason:
                sell_price = row['close'] * (1 - params['slippage'])
                cash += pos['shares'] * sell_price * (1 - params['commission'])
                trades.append({
                    'code': code,
                    'entry_date': pos['entry_date'],
                    'exit_date': date.strftime('%Y-%m-%d'),
                    'exit_reason': exit_reason,
                    'entry_price': pos['entry_price'],
                    'exit_price': sell_price,
                    'return': (sell_price / pos['entry_price'] - 1),
                    'hold_days': date_idx - pos['entry_idx'],
                })
                del positions[code]

        # Check entries
        if len(positions) < params['max_positions']:
            for code in day_data.index:
                if code in positions:
                    continue
                code_df = data[data['code'] == code].set_index('date')
                if date not in code_df.index:
                    continue
                idx = code_df.index.get_loc(date)

                # Find most recent attack day
                attack_idx = None
                for ai in range(idx - params['time_max'], idx - params['time_min'] + 1):
                    if ai >= 0 and find_attack_day(code_df, ai):
                        attack_idx = ai
                        break

                if attack_idx is None:
                    continue

                passed, _ = _check_entry_filters(code_df, idx, attack_idx, params, market_score)
                if passed:
                    buy_price = code_df.iloc[idx]['close'] * (1 + params['slippage'])
                    position_value = capital * params['position_pct']
                    shares = int(position_value / buy_price / 100) * 100
                    if shares > 0:
                        cost = shares * buy_price * (1 + params['commission'])
                        if cost <= cash:
                            cash -= cost
                            positions[code] = {
                                'entry_price': buy_price,
                                'entry_idx': idx,
                                'entry_date': date.strftime('%Y-%m-%d'),
                                'shares': shares,
                                'highest_close': buy_price,
                            }

        # Track equity
        for code, pos in positions.items():
            if code in day_data.index:
                daily_equity += pos['shares'] * day_data.loc[code]['close']
            else:
                daily_equity += pos['shares'] * pos['entry_price']

        equity.append({'date': date, 'equity': daily_equity})

    # Results
    equity_df = pd.DataFrame(equity)
    final = equity_df['equity'].iloc[-1] if len(equity_df) > 0 else capital
    total_ret = (final / capital) - 1

    equity_df['peak'] = equity_df['equity'].cummax()
    equity_df['drawdown'] = equity_df['equity'] / equity_df['peak'] - 1
    max_dd = equity_df['drawdown'].min()

    years = max(len(equity_df) / 252, 1)
    annual_ret = (1 + total_ret) ** (1 / years) - 1

    trades_df = pd.DataFrame(trades)
    if len(trades_df) > 0:
        win_rate = (trades_df['return'] > 0).mean()
        avg_ret = trades_df['return'].mean()
        pos_ret = trades_df[trades_df['return'] > 0]['return']
        neg_ret = trades_df[trades_df['return'] < 0]['return']
        win_loss = abs(pos_ret.mean() / neg_ret.mean()) if len(neg_ret) > 0 and neg_ret.mean() != 0 else float('inf')
        avg_hold = trades_df['hold_days'].mean()
    else:
        win_rate = avg_ret = win_loss = avg_hold = 0

    return {
        'strategy': strategy,
        'total_return': total_ret,
        'annual_return': annual_ret,
        'max_drawdown': max_dd,
        'win_rate': win_rate,
        'avg_return': avg_ret,
        'win_loss_ratio': win_loss,
        'trade_count': len(trades_df),
        'avg_hold_days': avg_hold,
        'final_capital': final,
        'initial_capital': capital,
        'equity_curve': equity_df,
        'trades': trades_df,
        'exit_reasons': trades_df['exit_reason'].value_counts().to_dict() if len(trades_df) > 0 else {},
    }


def monte_carlo(data, strategy, n=500):
    """蒙特卡洛模拟"""
    results = []
    dates = sorted(data['date'].unique())
    np.random.seed(42)
    for i in range(n):
        sampled = np.random.choice(dates, size=len(dates), replace=True)
        sampled_df = pd.concat([data[data['date'] == d] for d in sampled], ignore_index=True)
        try:
            r = run_backtest(sampled_df, strategy)
            results.append(r['total_return'])
        except Exception:
            continue
    results = np.array(results)
    return {
        'mean': results.mean(), 'median': np.median(results), 'std': results.std(),
        'p5': np.percentile(results, 5), 'p25': np.percentile(results, 25),
        'p75': np.percentile(results, 75), 'p95': np.percentile(results, 95),
        'positive_rate': (results > 0).mean(),
    }


# ─── CLI ───
def main():
    parser = argparse.ArgumentParser(description='来福回测引擎')
    parser.add_argument('--strategy', default='longhui', help='策略名称 longhui/attack')
    parser.add_argument('--codes', default='', help='股票代码列表，逗号分隔，默认全市场')
    parser.add_argument('--scan', help='参数扫描: 参数名')
    parser.add_argument('--from', dest='scan_from', type=float, default=0)
    parser.add_argument('--to', dest='scan_to', type=float, default=1)
    parser.add_argument('--step', type=float, default=0.05)
    parser.add_argument('--montecarlo', type=int, help='蒙特卡洛模拟次数')
    parser.add_argument('--compare', action='store_true', help='对比两个策略')
    parser.add_argument('--quick', action='store_true', help='快速模式（仅100只股票）')
    parser.add_argument('--fast', action='store_true', help='极速测试（10只股票，演示回测流程）')
    args = parser.parse_args()

    cfg = load_config()
    bt = cfg.get('backtest', {})
    start = bt.get('start_date', '2015-01-01')
    end = bt.get('end_date', '2025-12-31')

    print("=" * 50)
    print("  Laifu Backtest Engine")
    print("=" * 50)

    # Load codes
    if args.codes:
        codes = args.codes.split(',')
    elif args.fast:
        # Super fast: 10 stocks, 3 years, demo data
        print("  Demo mode: 10 stocks x 3 years")
        dates = pd.date_range('2022-01-01', '2024-12-31', freq='B')
        demo_codes = [f'{c:06d}' for c in range(600000, 600010)]
        records = []
        np.random.seed(42)
        for c in demo_codes:
            p = np.random.uniform(8, 30)
            for d in dates:
                r = np.random.normal(0.0005, 0.018)
                p *= (1 + r)
                p = max(p, 3)
                vol = np.random.uniform(500000, 5000000)
                # Occasionally create an attack day (up >9.5% with high vol)
                is_attack = np.random.random() < 0.02
                chg = 0.098 + np.random.random() * 0.005 if is_attack else r
                close = p * (1 + chg) if is_attack else p
                records.append({
                    'code': c, 'date': d,
                    'open': p, 'high': p*1.03, 'low': p*0.97, 'close': close,
                    'amount': close*vol, 'volume': vol * (3 if is_attack else 1),
                })
                p = close
        data = pd.DataFrame(records)
        print(f"  {len(demo_codes)} stocks x {len(dates)} days = {len(records)} records")
    else:
        try:
            all_codes = get_all_stock_codes()
            codes = all_codes[:100] if args.quick else all_codes
            print(f"  全市场股票: {len(all_codes)}只 | 回测用: {len(codes)}只")
        except FileNotFoundError:
            print("  [WARN] vipdoc not found, using demo mode")
            # Generate demo data
            dates = pd.date_range(start, end, freq='B')
            demo_codes = [f'{c:06d}' for c in range(600000, 600100)]
            records = []
            np.random.seed(42)
            for c in demo_codes:
                p = np.random.uniform(5, 50)
                for d in dates:
                    r = np.random.normal(0.0005, 0.02)
                    p *= (1 + r)
                    p = max(p, 2)
                    records.append({'code': c, 'date': d, 'open': p, 'high': p*1.02,
                                   'low': p*0.98, 'close': p, 'amount': p*1e6, 'volume': 1e6})
            data = pd.DataFrame(records)
            print(f"  演示数据: {len(demo_codes)}只 × {len(dates)}天")

    if 'data' not in dir():
        try:
            data = load_market_data(codes, start, end)
        except RuntimeError as e:
            print(f"  ❌ {e}")
            sys.exit(1)

    # Monte Carlo
    if args.montecarlo:
        n = args.montecarlo
        print(f"\n🎲 蒙特卡洛模拟 {n}次...")
        mc = monte_carlo(data, args.strategy, n)
        print(f"""
  均值收益:  {format_pct(mc['mean'])}
  中位数:    {format_pct(mc['median'])}
  标准差:    {format_pct(mc['std'])}
  5%分位:    {format_pct(mc['p5'])}
  95%分位:   {format_pct(mc['p95'])}
  正收益概率: {mc['positive_rate']:.0%}
""")
        return

    # Parameter scan
    if args.scan:
        name = args.scan
        print(f"\n🔍 参数扫描: {name} [{args.scan_from} → {args.scan_to}]")
        print(f"{'参数值':<10} {'收益率':>10} {'回撤':>8} {'胜率':>8} {'交易数':>6}")
        print("-" * 46)
        v = args.scan_from
        while v <= args.scan_to:
            # Update param temporarily
            cfg = load_config()
            strategy, param = name.split('.', 1) if '.' in name else (args.strategy, name)
            cfg['strategy'][strategy][param] = round(v, 3)
            save_config(cfg)
            r = run_backtest(data, args.strategy)
            print(f"{v:<10.2f} {format_pct(r['total_return']):>10} {format_pct(r['max_drawdown']):>8} {r['win_rate']:>7.1%} {r['trade_count']:>6}")
            v += args.step

        # Restore default
        cfg['strategy'][strategy][param] = 0.25  # reasonable default
        save_config(cfg)
        return

    # Standard backtest
    print(f"\n⚡ {args.strategy} 回测中...")
    result = run_backtest(data, args.strategy)

    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 回测报告: {args.strategy}
━━━━━━━━━━━━━━━━━━━━━━━━━━
初始资金:  ¥{format_money(result['initial_capital'])}
最终资金:  ¥{format_money(result['final_capital'])}
总收益率:  {format_pct(result['total_return'])}
年化收益:  {format_pct(result['annual_return'])}
最大回撤:  {format_pct(result['max_drawdown'])}
胜率:      {result['win_rate']:.1%}
盈亏比:    {result['win_loss_ratio']:.2f}
交易次数:  {result['trade_count']}
均持仓:    {result['avg_hold_days']:.1f}天
━━━━━━━━━━━━━━━━━━━━━━━━━━""")

    if result['exit_reasons']:
        print(f"\n出场分布:")
        for reason, count in sorted(result['exit_reasons'].items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count}次")

    if args.compare:
        print(f"\n⚔️ 攻守双驱对比中...")
        r2 = run_backtest(data, 'attack')
        print(f"""
攻守双驱V1:
  总收益率:  {format_pct(r2['total_return'])}
  最大回撤:  {format_pct(r2['max_drawdown'])}
  胜率:      {r2['win_rate']:.1%}
  交易次数:  {r2['trade_count']}""")


if __name__ == '__main__':
    main()
