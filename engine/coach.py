"""来福工具箱 — AI策略导师（历史数据分析+胜率诊断）"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import json
import argparse
import numpy as np
from datetime import datetime, timedelta

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))

def _load_positions():
    f = os.path.join(ENGINE_DIR, '..', 'positions.json')
    if not os.path.exists(f): return []
    with open(f, 'r', encoding='utf-8') as fp: return json.load(fp)

def _load_signals():
    f = os.path.join(ENGINE_DIR, '..', 'signals.json')
    if not os.path.exists(f): return []
    with open(f, 'r', encoding='utf-8') as fp: return json.load(fp)

def _load_alerts():
    f = os.path.join(ENGINE_DIR, '..', 'alerts_today.json')
    if not os.path.exists(f): return []
    with open(f, 'r', encoding='utf-8') as fp: return json.load(fp)


def analyze_winrate():
    """分析胜率变化趋势"""
    positions = _load_positions()
    closed = [p for p in positions if p['status'] == 'closed' and 'exit_price' in p and p['entry_price'] > 0]

    if len(closed) < 5:
        return {'status': 'insufficient', 'msg': f'仅有{len(closed)}笔已完结交易，需5笔以上才能分析'}

    returns = [(p['exit_price'] / p['entry_price'] - 1) for p in closed]
    wins = sum(1 for r in returns if r > 0)
    total = len(returns)
    overall_wr = wins / total

    # Split into halves to detect trend
    mid = total // 2
    first_half = returns[:mid]
    second_half = returns[mid:]
    first_wr = sum(1 for r in first_half if r > 0) / len(first_half)
    second_wr = sum(1 for r in second_half if r > 0) / len(second_half)
    wr_change = second_wr - first_wr

    # Exit reason analysis
    from collections import Counter
    exit_reasons = Counter(p.get('exit_reason', '?') for p in closed)

    # Signal type analysis
    signal_types = Counter(p.get('signal_type', '?') for p in closed)
    type_returns = {}
    for t in signal_types:
        t_ret = [(p['exit_price']/p['entry_price']-1) for p in closed if p.get('signal_type')==t]
        if t_ret:
            type_returns[t] = {
                'count': len(t_ret),
                'avg_return': np.mean(t_ret),
                'winrate': sum(1 for r in t_ret if r > 0) / len(t_ret),
            }

    # Hold days analysis
    hold_days = [p.get('hold_days', 0) for p in closed if p.get('hold_days', 0) > 0]
    avg_hold = np.mean(hold_days) if hold_days else 0

    return {
        'status': 'ok',
        'total': total, 'wins': wins, 'overall_wr': overall_wr,
        'first_half_wr': first_wr, 'second_half_wr': second_wr,
        'wr_change': wr_change, 'trend': 'up' if wr_change > 0.03 else 'down' if wr_change < -0.03 else 'flat',
        'avg_return': np.mean(returns), 'max_return': max(returns), 'min_return': min(returns),
        'avg_hold': avg_hold,
        'exit_reasons': dict(exit_reasons),
        'type_returns': type_returns,
    }


def analyze_drawdown():
    """分析回撤原因"""
    positions = _load_positions()
    closed = [p for p in positions if p['status'] == 'closed' and 'exit_price' in p and p['entry_price'] > 0]

    if len(closed) < 3:
        return {'status': 'insufficient', 'msg': '数据不足'}

    # Largest losses
    returns = [(p['exit_price'] / p['entry_price'] - 1, p) for p in closed]
    returns.sort()  # worst first

    worst = returns[:5]
    findings = []
    for ret, p in worst:
        if ret < -0.03:
            findings.append({
                'code': p['code'],
                'loss': f'{ret:+.1%}',
                'reason': p.get('exit_reason', '?'),
                'entry': p['entry_date'],
                'hold_days': p.get('hold_days', 0),
            })

    # Check if specific exit reason dominates losses
    from collections import Counter
    loss_reasons = Counter(p.get('exit_reason', '?') for p in closed if p['exit_price']/p['entry_price']-1 < 0)

    return {
        'status': 'ok',
        'worst_trades': findings,
        'loss_reasons': dict(loss_reasons),
        'max_loss': f'{min(r for r,_ in returns):+.1%}',
    }


def suggest_optimization():
    """基于历史数据建议参数优化方向"""
    positions = _load_positions()
    closed = [p for p in positions if p['status'] == 'closed' and 'exit_price' in p]

    if len(closed) < 10:
        return {'status': 'insufficient', 'msg': '需10笔以上交易才能生成优化建议'}

    suggestions = []
    from collections import Counter
    exits = Counter(p.get('exit_reason', '') for p in closed)

    # Exit reason analysis
    trailing = exits.get('1-移动止盈', 0)
    hard_stop = exits.get('2-硬止损', 0)
    volume_exit = exits.get('4-放量断板', 0)

    total = sum(exits.values())

    if hard_stop / total > 0.3:
        suggestions.append({
            'target': '入场时机或硬止损设置',
            'issue': f'硬止损占比{hard_stop/total:.0%}偏高，说明较多持仓入场后直接下跌',
            'suggestion': '尝试收紧入场条件：缩量比上限从55%降到45%，增加趋势角最低要求至2度',
        })

    if trailing / total < 0.3 and total > 10:
        suggestions.append({
            'target': '移动止盈参数',
            'issue': f'移动止盈出场仅占{trailing/total:.0%}，趋势利润没有充分吃到',
            'suggestion': '尝试放宽移动止盈ATR倍数从2.0到2.5，让利润多跑一程',
        })

    if volume_exit / total > 0.25:
        suggestions.append({
            'target': '放量断板出场',
            'issue': f'放量断板占比{volume_exit/total:.0%}偏高，追入后频繁遭遇放量砸盘',
            'suggestion': '入场前增加量价确认：要求入场前一日不是放量下跌日',
        })

    # Signal type quality
    sig_type_ret = {}
    for p in closed:
        t = p.get('signal_type', '?')
        if t not in sig_type_ret:
            sig_type_ret[t] = []
        sig_type_ret[t].append(p['exit_price']/p['entry_price']-1)

    for t, rets in sig_type_ret.items():
        if len(rets) >= 3 and np.mean(rets) < 0:
            suggestions.append({
                'target': f'{t}信号过滤',
                'issue': f'{t}信号近{len(rets)}笔均收益{np.mean(rets):+.1%}为负',
                'suggestion': f'{t}信号出现时，额外检查缩量比是否<40%和偏离度是否<8%',
            })

    return {
        'status': 'ok',
        'suggestions': suggestions,
        'total_analyzed': total,
    }


# ─── CLI ───
def main():
    parser = argparse.ArgumentParser(description='来福 AI 策略导师')
    parser.add_argument('--winrate', action='store_true', help='胜率分析')
    parser.add_argument('--drawdown', action='store_true', help='回撤原因分析')
    parser.add_argument('--optimize', action='store_true', help='参数优化建议')
    parser.add_argument('--full', action='store_true', help='完整诊断报告')
    args = parser.parse_args()

    run_all = not any([args.winrate, args.drawdown, args.optimize])
    if args.full: run_all = True

    print("╔══════════════════════════════════════╗")
    print("║  来福 · AI 策略导师                  ║")
    print(f"║  {datetime.now().strftime('%Y-%m-%d %H:%M')}                       ║")
    print("╚══════════════════════════════════════╝")

    if run_all or args.winrate:
        print("\n【胜率分析】")
        r = analyze_winrate()
        if r['status'] != 'ok':
            print(f"  {r['msg']}")
        else:
            print(f"  总交易: {r['total']}笔 | 胜率: {r['overall_wr']:.1%}")
            print(f"  前半段胜率: {r['first_half_wr']:.1%} → 后半段: {r['second_half_wr']:.1%}")
            trend_cn = {'up': '📈 改善中', 'down': '📉 在下降', 'flat': '➡️ 持平'}
            print(f"  趋势: {trend_cn.get(r['trend'], r['trend'])}")
            print(f"  均收益: {r['avg_return']:+.1%} | 最大: {r['max_return']:+.1%} | 最小: {r['min_return']:+.1%}")
            print(f"  均持仓: {r['avg_hold']:.1f}天")
            if r.get('type_returns'):
                print(f"  信号类型:")
                for t, d in r['type_returns'].items():
                    print(f"    {t}: {d['count']}笔 均{d['avg_return']:+.1%} 胜{d['winrate']:.0%}")
            if r.get('exit_reasons'):
                print(f"  出场分布:")
                for reason, count in r['exit_reasons'].items():
                    print(f"    {reason}: {count}次")

    if run_all or args.drawdown:
        print("\n【回撤诊断】")
        r = analyze_drawdown()
        if r['status'] != 'ok':
            print(f"  {r['msg']}")
        else:
            print(f"  最大单笔亏损: {r['max_loss']}")
            if r.get('worst_trades'):
                print(f"  最大亏损交易:")
                for t in r['worst_trades'][:5]:
                    print(f"    {t['code']} {t['loss']} | {t['reason']} | 持{t['hold_days']}天 | {t['entry']}")
            if r.get('loss_reasons'):
                print(f"  亏损出场原因分布:")
                for reason, count in r['loss_reasons'].items():
                    print(f"    {reason}: {count}次")

    if run_all or args.optimize:
        print("\n【优化建议】")
        r = suggest_optimization()
        if r['status'] != 'ok':
            print(f"  {r['msg']}")
        else:
            print(f"  基于{r['total_analyzed']}笔交易分析:")
            for i, s in enumerate(r.get('suggestions', []), 1):
                print(f"\n  [{i}] {s['target']}")
                print(f"  问题: {s['issue']}")
                print(f"  建议: {s['suggestion']}")
            if not r.get('suggestions'):
                print(f"  ✅ 当前未发现明显需要优化的方向")

    print(f"\n[QClaw: 请基于以上数据，结合NeoData市场环境，给出总结性分析]")


if __name__ == '__main__':
    main()
