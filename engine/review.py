"""来福工具箱 — 每日复盘生成"""
import argparse
from datetime import datetime


TEMPLATE = """━━━━━━━━━━━━━━━━━━━━━━
🔥 每日复盘 · {date} {weekday}
━━━━━━━━━━━━━━━━━━━━━━

💬 一句话定调
{summary}

━━━━━━━━━━━━━━━━━━━━━━
📊 情绪温度计
━━━━━━━━━━━━━━━━━━━━━━
周期阶段：{cycle}
赚钱效应：{breadth}
涨停{up_limit}家 / 跌停{down_limit}家 / 炸板{bomb}家
成交额：{volume}
大盘绿灯：{light}

━━━━━━━━━━━━━━━━━━━━━━
👑 高标梯队
━━━━━━━━━━━━━━━━━━━━━━
{leaders}

━━━━━━━━━━━━━━━━━━━━━━
🎯 主线战场
━━━━━━━━━━━━━━━━━━━━━━
{main_line}

━━━━━━━━━━━━━━━━━━━━━━
🎯 策略信号统计
━━━━━━━━━━━━━━━━━━━━━━
{signal_stats}

━━━━━━━━━━━━━━━━━━━━━━
🗡️ 明日情景推演
━━━━━━━━━━━━━━━━━━━━━━
{scenarios}
"""


def generate_review(date_str=None):
    """生成复盘报告"""
    if date_str:
        date = datetime.strptime(date_str, '%Y-%m-%d')
    else:
        date = datetime.now()

    # TODO: 从i问财获取实时市场数据填充模板
    review = TEMPLATE.format(
        date=date.strftime('%m月%d日'),
        weekday=['周一','周二','周三','周四','周五','周六','周日'][date.weekday()],
        summary='[需连接i问财获取市场数据]',
        cycle='[待分析]',
        breadth='[待获取]',
        up_limit='[待获取]',
        down_limit='[待获取]',
        bomb='[待获取]',
        volume='[待获取]',
        light='🟡',
        leaders='[待获取连板数据]',
        main_line='[待获取板块资金数据]',
        signal_stats='[请先运行 laifu-scanner --scan]',
        scenarios='[待生成]',
    )
    print(review)
    return review


def main():
    parser = argparse.ArgumentParser(description='来福复盘生成')
    parser.add_argument('--today', action='store_true', help='生成今日复盘')
    parser.add_argument('--latest', action='store_true', help='查看最新复盘')
    parser.add_argument('--date', help='指定日期 YYYY-MM-DD')
    parser.add_argument('--export', choices=['md', 'html'], help='导出格式')
    args = parser.parse_args()

    date_str = args.date if args.date else None
    review = generate_review(date_str)

    if args.export:
        ext = args.export
        filename = f"review_{date_str or datetime.now().strftime('%Y%m%d')}.{ext}"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(review)
        print(f"✅ 已导出: {filename}")


if __name__ == '__main__':
    main()
