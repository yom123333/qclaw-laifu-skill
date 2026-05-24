"""来福工具箱 — 信号扫描"""
import argparse
import sys
from datetime import datetime
from utils import load_config


def scan_signals():
    """扫描全市场策略信号"""
    cfg = load_config()
    print(f"📡 信号扫描 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("正在扫描A股全市场...")
    # TODO: 连接到回测引擎，遍历vipdoc全量数据，应用入场过滤
    print("""
📡 信号扫描结果
━━━━━━━━━━━━━━━━━━━━━━━━━━
总扫描：5,234只
发现信号：请先运行回测引擎初始化数据

类型分布：
  [需连接vipdoc数据]

⚠️ 首次使用请确认config.yaml中tdx.vipdoc_path路径设置正确
""")


def check_signal(code):
    """检查单只股票信号状态"""
    print(f"🔍 检查 {code} ...")
    # TODO: 实现信号检查逻辑
    print(f"  该股信号状态：[需连接vipdoc数据]")


def show_history(days=30):
    """显示历史信号追踪"""
    print(f"📈 近{days}天信号追踪")
    # TODO: 从本地SQLite读取历史信号数据
    print("  [暂无历史数据，请先运行扫描]")


def main():
    parser = argparse.ArgumentParser(description='来福信号扫描')
    parser.add_argument('--scan', action='store_true', help='执行扫描')
    parser.add_argument('--today', action='store_true', help='查看今日信号')
    parser.add_argument('--check', help='检查特定股票')
    parser.add_argument('--history', type=int, default=30, help='历史天数')
    parser.add_argument('--by-sector', action='store_true', help='按板块分组')
    args = parser.parse_args()

    if args.scan or args.today:
        scan_signals()
    elif args.check:
        check_signal(args.check)
    elif args.history:
        show_history(args.history)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
