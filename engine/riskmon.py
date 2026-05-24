"""来福工具箱 — 市场风险哨兵（极端预警+日历风险+结构风险）"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import json
import argparse
import requests
from datetime import datetime, timedelta

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── Calendar ───
def _is_futures_settlement_day(today=None):
    """判断是否为股指期货交割日（每月第三个周五）"""
    if today is None:
        today = datetime.now()
    if today.weekday() != 4:  # 不是周五
        return False
    # 第三个周五: 日期在15-21之间
    return 15 <= today.day <= 21

def _is_holiday_proximity(today=None):
    """长假前3天（简易版，需手动补充实际假期）"""
    if today is None:
        today = datetime.now()
    month, day = today.month, today.day
    # 春节前（1月底-2月初）
    if month == 1 and day >= 25:
        return True, "春节前"
    if month == 2 and day <= 3:
        return True, "春节前"
    # 国庆前
    if month == 9 and day >= 28:
        return True, "国庆前"
    # 五一前
    if month == 4 and day >= 28:
        return True, "五一前"
    return False, ""

def _is_quarter_end(today=None):
    """季末"""
    if today is None:
        today = datetime.now()
    return today.month in (3, 6, 9, 12) and today.day >= 25

def check_calendar_risks():
    """检查日历风险"""
    risks = []
    now = datetime.now()

    if _is_futures_settlement_day(now):
        risks.append({
            'level': 'high',
            'type': '股指期货交割日',
            'detail': '今天下午波动率将异常放大，趋势信号容易假突破。移动止盈线适当收紧。',
            'action': '14:00后对新入场信号保持警惕，已持仓的收紧移动止盈ATR倍数至1.5',
        })

    is_holiday, name = _is_holiday_proximity(now)
    if is_holiday:
        risks.append({
            'level': 'medium',
            'type': f'{name}窗口期',
            'detail': '资金避险撤退中，缩量不一定是"回调到位"，可能是无人接盘。',
            'action': '缩量比解读需谨慎，不宜仅凭缩量入场。等待节后确认信号更安全。',
        })

    if _is_quarter_end(now):
        risks.append({
            'level': 'medium',
            'type': '季末流动性波动',
            'detail': '基金排名+银行MPA考核，流动性异常。北向资金和成交额波动加大。',
            'action': '关注北向资金日内趋势，尾盘可能出现异常拉升或砸盘。',
        })

    if now.weekday() == 4:  # 周五
        risks.append({
            'level': 'low',
            'type': '周末持仓风险',
            'detail': '隔两夜，容易出政策/外围黑天鹅。',
            'action': '周五新入场信号，仓位适当降低。',
        })

    return risks


# ─── Market Data via iwencai ───
def _fetch_iwencai(query):
    try:
        url = f"https://www.iwencai.com/stockpick/search?w={query}"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
        r.encoding = 'utf-8'
        return r.text
    except Exception:
        return None

def _extract_numbers(html, keywords):
    """Extract multiple numbers from iwencai HTML"""
    import re
    if not html:
        return {}
    results = {}
    for kw in keywords:
        idx = html.find(kw)
        if idx >= 0:
            snippet = html[max(0,idx-100):idx+300]
            nums = re.findall(r'[-+]?\d+\.?\d*', snippet)
            if nums:
                results[kw] = float(nums[0])
    return results


# ─── Risk Checks ───
def check_market_extremes():
    """检查市场极端情况"""
    alerts = []
    html = _fetch_iwencai('上证指数涨跌幅+跌停家数+涨停家数+炸板率+成交额+北向资金净买入')

    if not html:
        return [{'level': 'low', 'type': '数据获取失败', 'detail': 'i问财暂时不可用，风险监控暂停', 'action': '等待自动重试'}]

    nums = _extract_numbers(html, ['上证指数', '跌停家数', '涨停家数', '炸板', '成交额', '北向资金'])

    # 极端波动
    sh_pct = nums.get('上证指数', 0)
    if abs(sh_pct) > 2:
        alerts.append({
            'level': 'high',
            'type': f'上证指数{"暴涨" if sh_pct>0 else "暴跌"} {sh_pct:+.1f}%',
            'detail': f'市场极端波动，大盘绿灯可能失效。{"急速拉升容易追高被套" if sh_pct>0 else "恐慌杀跌中信号大面积破位"}。',
            'action': f'{"暂停新开仓，已持仓检查趋势线是否仍有效。移动止盈收紧。" if sh_pct<0 else "不追高，等待回调确认。现有持仓享受趋势。"}',
        })

    # 跌停潮
    down_limit = nums.get('跌停家数', 0)
    if down_limit > 50:
        alerts.append({
            'level': 'high',
            'type': f'跌停潮 {int(down_limit)}家',
            'detail': '恐慌情绪蔓延，赚钱效应崩溃。过滤10"大盘绿灯"不满足，策略信号大面积失效。',
            'action': '暂停所有新入场。已持仓逐一检查：是否破趋势线？是否放量？是否有跌停风险？',
        })
    elif down_limit > 30:
        alerts.append({
            'level': 'medium',
            'type': f'跌停偏多 {int(down_limit)}家',
            'detail': '市场亏钱效应扩散，情绪转弱。',
            'action': '新入场需额外谨慎，缩量比和趋势角条件从严（缩量<45%，ang3>2度）。',
        })

    # 涨停冰点
    up_limit = nums.get('涨停家数', 100)
    if up_limit < 20:
        alerts.append({
            'level': 'high',
            'type': f'涨停冰点 {int(up_limit)}家',
            'detail': '追涨情绪归零。龙回策略依赖的"涨停基因"逻辑前提动摇——连涨停板都没人打了。',
            'action': '暂停入场扫描。等待涨停家数恢复至30+。现有持仓不必恐慌，低情绪环境不意味着必然下跌。',
        })

    # 炸板率
    bomb_key = [k for k in nums if '炸板' in k]
    if bomb_key and up_limit > 0:
        # Can't directly get bomb rate from simple extraction, skip
        pass

    # 北向大幅流出
    north = nums.get('北向资金', 0)
    if north < -80:
        alerts.append({
            'level': 'high',
            'type': f'北向资金大幅流出 {north:.0f}亿',
            'detail': '外资加速撤离，通常是系统性风险信号。历史上北向单日流出超80亿后，3日内继续下跌概率约65%。',
            'action': '全线收紧。已持仓浮盈的考虑减1/3。新入场暂停。等待北向回流确认。',
        })
    elif north < -50:
        alerts.append({
            'level': 'medium',
            'type': f'北向流出 {north:.0f}亿',
            'detail': '外资连续撤离，关注后续趋势。',
            'action': '持仓正常监控，新入场暂缓等待回流信号。',
        })

    return alerts


def check_structure_risks():
    """检查市场结构风险（连板梯队+信号池内部）"""
    alerts = []

    # 信号池内部风险
    positions_file = os.path.join(ENGINE_DIR, '..', 'positions.json')
    if os.path.exists(positions_file):
        with open(positions_file, 'r', encoding='utf-8') as f:
            positions = json.load(f)

        active = [p for p in positions if p['status'] == 'active']

        # 强势吸占比
        if active:
            qiangshi = len([p for p in active if '强势' in p.get('signal_type', '')])
            ratio = qiangshi / len(active)
            if ratio < 0.2 and len(active) >= 5:
                alerts.append({
                    'level': 'medium',
                    'type': f'信号质量滑坡（强势吸仅{ratio:.0%}）',
                    'detail': f'当前{len(active)}个活跃信号中仅{qiangshi}个强势吸。弱势吸占比过高说明缩量不够极致，入场质量下降。',
                    'action': '对弱势吸信号加强监控，缩量比和趋势角条件从严。优先关注强势吸信号。',
                })

    return alerts


# ─── Output ───
def run_all_checks():
    """运行所有风险检查并输出报告"""
    now = datetime.now()
    trading = 9 <= now.hour < 15 or (now.hour == 9 and now.minute >= 30)

    print(f"╔══════════════════════════════════════╗")
    print(f"║  来福 · 市场风险哨兵                  ║")
    print(f"║  {now.strftime('%Y-%m-%d %H:%M')}                      ║")
    print(f"║  交易时段: {'是' if trading else '否'}                          ║")
    print(f"╚══════════════════════════════════════╝")

    all_alerts = []

    # 日历风险（仅盘前检查一次即可）
    cal_risks = check_calendar_risks()
    all_alerts.extend(cal_risks)

    # 市场极端（交易时段每3分钟）
    mkt_alerts = check_market_extremes()
    all_alerts.extend(mkt_alerts)

    # 结构风险
    struct_alerts = check_structure_risks()
    all_alerts.extend(struct_alerts)

    # 按级别排列
    high = [a for a in all_alerts if a['level'] == 'high']
    medium = [a for a in all_alerts if a['level'] == 'medium']
    low = [a for a in all_alerts if a['level'] == 'low']

    if high:
        print(f"\n🔴 高风险预警 ({len(high)}条)")
        print("━" * 45)
        for a in high:
            print(f"\n  ⚠️ {a['type']}")
            print(f"  分析: {a['detail']}")
            print(f"  建议: {a['action']}")

    if medium:
        print(f"\n🟡 中风险提醒 ({len(medium)}条)")
        print("━" * 45)
        for a in medium:
            print(f"\n  📌 {a['type']}")
            print(f"  分析: {a['detail']}")
            print(f"  建议: {a['action']}")

    if low:
        print(f"\n🟢 低风险提示 ({len(low)}条)")
        print("━" * 45)
        for a in low:
            print(f"  · {a['type']}: {a['detail']}")

    if not all_alerts:
        # Silent mode: no output when everything is normal
        pass

    print(f"\n{'━'*45}")
    print(f"下次检查: {now + timedelta(minutes=3)} (3分钟后)")

    return all_alerts


def check_premarket():
    """盘前简报：隔夜美股+今日日历+预期"""
    now = datetime.now()
    cal = check_calendar_risks()
    weekday = ['周一','周二','周三','周四','周五','周六','周日'][now.weekday()]

    print(f"╔══════════════════════════════════════╗")
    print(f"║  来福 · 盘前简报                      ║")
    print(f"║  {now.strftime('%Y-%m-%d')} {weekday}                        ║")
    print(f"╚══════════════════════════════════════╝")

    # Calendar
    if cal:
        print(f"\n📅 今日日历风险:")
        for c in cal:
            print(f"  [{c['level']}] {c['type']}")
            print(f"  建议: {c['action']}")
    else:
        print(f"\n📅 今日无特殊日历事件")

    # Try to get overnight US market
    print(f"\n🌍 隔夜外盘（请用NeoData补充）:")
    print(f"  需检查: 美股三大指数涨跌 / A50期货 / 人民币汇率 / VIX")

    # Today's expectation
    print(f"\n📋 今日关注:")
    print(f"  1. 昨日涨停家数+封板率 → 判断今日追涨情绪")
    print(f"  2. 北向资金昨日方向 → 连续流出需警惕")
    print(f"  3. 昨日成交额 → 缩量环境降低预期")
    print(f"  4. 持仓中信号 → 检查是否有临近出场的（浮亏>5%或持>15天）")

    # Check positions near exit
    positions_file = os.path.join(ENGINE_DIR, '..', 'positions.json')
    if os.path.exists(positions_file):
        with open(positions_file, 'r', encoding='utf-8') as f:
            positions = json.load(f)
        active = [p for p in positions if p['status'] == 'active']
        if active:
            risky = [p for p in active if p.get('hold_days', 0) > 12]
            print(f"\n⚠️ 持仓提醒:")
            print(f"  活跃持仓: {len(active)}个")
            if risky:
                print(f"  持仓超12天: {len(risky)}个 → 关注是否接近破高量出场")

    print(f"\n[QClaw: 请用NeoData补充隔夜美股+今日预期具体数据]")


def main():
    parser = argparse.ArgumentParser(description='来福市场风险哨兵')
    parser.add_argument('--check', action='store_true', help='运行一次风险检查')
    parser.add_argument('--calendar', action='store_true', help='仅检查日历风险')
    parser.add_argument('--premarket', action='store_true', help='盘前简报')
    parser.add_argument('--daemon', type=int, help='持续监控（每N秒）')
    args = parser.parse_args()

    if args.check or (not args.calendar and not args.daemon and not args.premarket):
        run_all_checks()

    if args.premarket:
        check_premarket()
        return

    if args.calendar:
        risks = check_calendar_risks()
        if risks:
            for r in risks:
                print(f"[{r['level']}] {r['type']}: {r['detail']}")
        else:
            print("今日无特殊日历风险")

    if args.daemon:
        import time
        interval = args.daemon
        print(f"🔔 风险哨兵启动，每{interval}秒检查 (Ctrl+C 停止)")
        try:
            while True:
                run_all_checks()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n哨兵已停止")


if __name__ == '__main__':
    main()
