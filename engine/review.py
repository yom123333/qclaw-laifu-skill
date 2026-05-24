"""来福工具箱 — 复盘生成器（数据驱动，极简token）"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import json
import argparse
import requests
from datetime import datetime, timedelta

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
SIGNAL_DB = os.path.join(ENGINE_DIR, '..', 'signals.json')
REVIEW_DIR = os.path.join(ENGINE_DIR, '..', 'reviews')


def _load_signals():
    """读取最新信号扫描结果"""
    if not os.path.exists(SIGNAL_DB):
        return []
    with open(SIGNAL_DB, 'r', encoding='utf-8') as f:
        return json.load(f)


def _fetch_iwencai(query, timeout=10):
    """抓i问财数据"""
    try:
        url = f"https://www.iwencai.com/stockpick/search?w={query}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, headers=headers, timeout=timeout)
        r.encoding = 'utf-8'
        return r.text
    except Exception:
        return None


def _extract_number(html, keyword):
    """从i问财HTML中粗略提取数字"""
    if not html:
        return None
    # Simple extraction: find keyword then look for numbers nearby
    idx = html.find(keyword)
    if idx < 0:
        return None
    snippet = html[idx:idx+200]
    import re
    nums = re.findall(r'[-+]?\d+\.?\d*', snippet)
    return nums[0] if nums else None


def _get_market_data():
    """获取市场数据（i问财为主，失败则返回占位符）"""
    data = {
        'sh_index': '--', 'sz_index': '--', 'cyb_index': '--',
        'up_count': '--', 'down_count': '--',
        'up_limit': '--', 'down_limit': '--', 'bomb_rate': '--',
        'turnover': '--', 'turnover_change': '--',
        'north_flow': '--',
        'sector_in': [], 'sector_out': [],
        'leaders': [], 'lhb': [],
    }

    html = _fetch_iwencai('上证指数+深证成指+创业板指+成交额+涨跌家数')
    if html:
        # Very basic extraction — in production use proper parsing
        data['sh_index'] = _extract_number(html, '上证指数') or '--'
        data['sz_index'] = _extract_number(html, '深证成指') or '--'
        data['cyb_index'] = _extract_number(html, '创业板指') or '--'
        up = _extract_number(html, '上涨')
        down = _extract_number(html, '下跌')
        if up and down:
            data['up_count'] = up
            data['down_count'] = down
        data['turnover'] = _extract_number(html, '成交额') or '--'

    return data


def _analyze_signals(signals):
    """分析信号统计"""
    if not signals:
        return {
            'total': 0, 'qiangshi': 0, 'ruoshi': 0,
            'sectors': {}, 'shrink_ranges': {},
            'window_ranges': {},
        }

    stats = {'total': len(signals), 'qiangshi': 0, 'ruoshi': 0,
             'sectors': {}, 'shrink_ranges': {}, 'window_ranges': {}}

    for s in signals:
        t = s.get('signal_type', '')
        if '强势' in t:
            stats['qiangshi'] += 1
        else:
            stats['ruoshi'] += 1

        sr = s.get('shrink_ratio', 0)
        if sr < 0.35:
            stats['shrink_ranges']['25-35%'] = stats['shrink_ranges'].get('25-35%', 0) + 1
        elif sr < 0.50:
            stats['shrink_ranges']['35-50%'] = stats['shrink_ranges'].get('35-50%', 0) + 1
        else:
            stats['shrink_ranges']['50-60%'] = stats['shrink_ranges'].get('50-60%', 0) + 1

        days = s.get('days_since_attack', 0)
        if days <= 5:
            stats['window_ranges']['3-5天'] = stats['window_ranges'].get('3-5天', 0) + 1
        elif days <= 8:
            stats['window_ranges']['6-8天'] = stats['window_ranges'].get('6-8天', 0) + 1
        else:
            stats['window_ranges']['9-12天'] = stats['window_ranges'].get('9-12天', 0) + 1

    return stats


def _get_summary(market_data, signal_stats):
    """生成一句话定调（极简DeepSeek调用或不调）"""
    try:
        # Try DeepSeek for a good summary
        from utils import get_deepseek_client
        client = get_deepseek_client()
        if client:
            prompt = f"""今日A股市场概况：上证{market_data.get('sh_index','--')}，涨{market_data.get('up_count','--')}家跌{market_data.get('down_count','--')}家，成交{market_data.get('turnover','--')}亿。策略信号{signal_stats.get('total',0)}个。用一句话（20-30字）总结今日市场核心矛盾。不要任何前缀。"""
            r = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role":"user","content":prompt}],
                max_tokens=60,
            )
            return r.choices[0].message.content.strip()
    except Exception:
        pass
    return "市场数据待获取"


def generate(today=None):
    """生成完整复盘报告"""
    if today is None:
        today = datetime.now()

    date_str = today.strftime('%Y-%m-%d')
    weekdays = ['周一','周二','周三','周四','周五','周六','周日']
    weekday = weekdays[today.weekday()]

    # 1. Load signals
    all_signals = _load_signals()
    today_signals = [s for s in all_signals if s.get('trade_date') == date_str]

    # 2. Get market data
    market = _get_market_data()

    # 3. Analyze signals
    sig_stats = _analyze_signals(today_signals)

    # 4. Generate summary
    summary = _get_summary(market, sig_stats)

    # 5. Format sector distribution
    sector_lines = ""
    if sig_stats['sectors']:
        for sector, count in sorted(sig_stats['sectors'].items(), key=lambda x: -x[1])[:5]:
            sector_lines += f"  · {sector}: {count}个\n"
    else:
        sector_lines = "  [需i问财板块数据]\n"

    # 6. Format shrink distribution
    shrink_lines = ""
    for k, v in sig_stats['shrink_ranges'].items():
        if v > 0:
            shrink_lines += f"  · {k}: {v}个\n"
    if not shrink_lines:
        shrink_lines = "  暂无数据\n"

    # 7. Format window distribution
    window_lines = ""
    for k, v in sig_stats['window_ranges'].items():
        if v > 0:
            window_lines += f"  · {k}: {v}个\n"
    if not window_lines:
        window_lines = "  暂无数据\n"

    review = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 每日复盘 · {today.strftime('%m月%d日')} {weekday}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 一句话定调
{summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 情绪温度计
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
上证指数：{market.get('sh_index', '--')}
深证成指：{market.get('sz_index', '--')}
创业板指：{market.get('cyb_index', '--')}
上涨{market.get('up_count', '--')}家 / 下跌{market.get('down_count', '--')}家
涨停{market.get('up_limit', '--')}家 / 跌停{market.get('down_limit', '--')}家
成交额：{market.get('turnover', '--')}亿{market.get('turnover_change', '')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👑 高标梯队
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{chr(10).join(market.get('leaders', ['[需NeoData连板数据]']))}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 主线战场
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
板块资金流入TOP3：
{chr(10).join(market.get('sector_in', ['[需NeoData板块资金数据]']))}

板块资金流出TOP3：
{chr(10).join(market.get('sector_out', ['[需NeoData板块资金数据]']))}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🐉 游资龙虎榜
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{chr(10).join(market.get('lhb', ['[需NeoData龙虎榜数据]']))}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 龙回2号策略信号统计
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
今日信号：{sig_stats['total']}个（强势吸 {sig_stats['qiangshi']} / 弱势吸 {sig_stats['ruoshi']}）

板块分布：
{sector_lines}
缩量区间：
{shrink_lines}
涨停天窗口：
{window_lines}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 本报告由来福策略工具箱自动生成，仅供策略学习参考，不构成投资建议。
"""

    # Save to file
    os.makedirs(REVIEW_DIR, exist_ok=True)
    filename = os.path.join(REVIEW_DIR, f"{date_str}_每日复盘.md")
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(review)

    return review, filename


def main():
    parser = argparse.ArgumentParser(description='来福复盘生成器')
    parser.add_argument('--today', action='store_true', help='生成今日复盘')
    parser.add_argument('--latest', action='store_true', help='查看最新复盘')
    parser.add_argument('--date', help='指定日期 YYYY-MM-DD')
    parser.add_argument('--export', choices=['md', 'html'], default='md', help='导出格式')
    parser.add_argument('--summary-only', action='store_true', help='只生成一句话定调')
    args = parser.parse_args()

    if args.date:
        today = datetime.strptime(args.date, '%Y-%m-%d')
    elif args.latest:
        if os.path.exists(REVIEW_DIR):
            files = sorted(os.listdir(REVIEW_DIR))
            if files:
                latest = os.path.join(REVIEW_DIR, files[-1])
                with open(latest, 'r', encoding='utf-8') as f:
                    print(f.read())
                return
        print("暂无历史复盘")
        return
    else:
        today = datetime.now()

    review, filename = generate(today)

    if args.summary_only:
        # Just print the one-liner
        for line in review.split('\n'):
            if '一句话定调' in review:
                continue
            if line.strip() and not line.startswith('━') and not line.startswith('🔥'):
                print(line.strip())
                break
        return

    print(review)
    print(f"\n✅ 复盘已保存: {filename}")


if __name__ == '__main__':
    main()
