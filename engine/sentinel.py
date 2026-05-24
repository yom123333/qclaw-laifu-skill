"""来福工具箱 — 预警哨兵"""
import argparse
import sys
import time
import json
from datetime import datetime
from utils import load_config


ALERT_LOG_PATH = None  # Set at runtime


def start_daemon():
    """启动后台预警监控"""
    cfg = load_config()
    alerts_cfg = cfg.get('alerts', {})

    print("🔔 来福预警哨兵已启动")
    print(f"  入场预警：{'✅' if alerts_cfg.get('enable_entry') else '❌'}")
    print(f"  出场预警：{'✅' if alerts_cfg.get('enable_exit') else '❌'}")
    print(f"  市场预警：{'✅' if alerts_cfg.get('enable_market') else '❌'}")
    print(f"  TTS播报：{'✅' if alerts_cfg.get('tts_enabled') else '❌'}")
    print("  监控中... (Ctrl+C 停止)")
    print()

    # TODO: 实现完整监控循环
    # 1. 每30秒检查信号变化
    # 2. 检查市场大盘状态
    # 3. 有新信号/出场触发时推送通知
    # 4. 通过QClaw/系统通知推送

    try:
        while True:
            time.sleep(30)
            # TODO: implement monitoring logic
            print(f"  [{datetime.now().strftime('%H:%M:%S')}] 正常运行中...")
    except KeyboardInterrupt:
        print("\n👋 哨兵已停止")


def show_status():
    """显示当前预警状态"""
    cfg = load_config()
    alerts = cfg.get('alerts', {})

    print("🔔 预警状态")
    print("=" * 30)
    for k, v in alerts.items():
        if isinstance(v, bool):
            print(f"  {k}: {'✅ 开启' if v else '❌ 关闭'}")
        else:
            print(f"  {k}: {v}")


def show_history(n=50):
    """显示历史预警记录"""
    print(f"📋 最近{n}条预警记录")
    print("=" * 50)
    # TODO: 从本地日志读取历史预警
    print("  [暂无历史预警记录]")


def set_mute(mute_str):
    """设置免打扰时段"""
    cfg = load_config()
    start, end = mute_str.split('-')
    cfg['alerts']['mute_start'] = start
    cfg['alerts']['mute_end'] = end
    from utils import save_config
    save_config(cfg)
    print(f"✅ 免打扰时段已设置: {start} - {end}")


def main():
    parser = argparse.ArgumentParser(description='来福预警哨兵')
    parser.add_argument('--daemon', action='store_true', help='启动后台监控')
    parser.add_argument('--status', action='store_true', help='查看预警状态')
    parser.add_argument('--history', type=int, default=50, help='查看历史预警')
    parser.add_argument('--mute', help='设置免打扰时段 如: 22:00-08:00')
    parser.add_argument('--stop', action='store_true', help='停止哨兵')
    args = parser.parse_args()

    if args.daemon:
        start_daemon()
    elif args.status:
        show_status()
    elif args.history:
        show_history(args.history)
    elif args.mute:
        set_mute(args.mute)
    elif args.stop:
        print("哨兵已停止")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
