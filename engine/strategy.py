"""来福工具箱 — 策略引擎"""
import sys
import argparse
from utils import load_config, save_config


class LonghuiStrategy:
    """龙回2号策略规则"""

    @staticmethod
    def entry_filters(params=None):
        """入场10层过滤规则"""
        if params is None:
            cfg = load_config()
            params = cfg.get('strategy', {}).get('longhui', {})

        return [
            {
                'name': '时间窗口',
                'rule': f"涨停后{params.get('time_window_min', 3)}-{params.get('time_window_max', 12)}天",
                'param': f"time_window_min={params.get('time_window_min',3)}, time_window_max={params.get('time_window_max',12)}",
                'description': '涨停后第4天为观察起点，排除当天涨停'
            },
            {
                'name': '缩量比',
                'rule': f"{params.get('shrink_ratio_min',0.25)*100:.0f}%-{params.get('shrink_ratio_max',0.55)*100:.0f}%",
                'param': f"shrink_ratio_min={params.get('shrink_ratio_min',0.25)}, shrink_ratio_max={params.get('shrink_ratio_max',0.55)}",
                'description': '当日成交量相对涨停日缩量比例'
            },
            {
                'name': '价格底线',
                'rule': f"不低于涨停日收盘价×{params.get('price_discount',0.98)}",
                'param': f"price_discount={params.get('price_discount',0.98)}",
                'description': '当前价格不低于涨停日收盘价的一定比例'
            },
            {
                'name': 'MA趋势',
                'rule': f"MA{params.get('ma_trend',20)}向上",
                'param': f"ma_trend={params.get('ma_trend',20)}",
                'description': '均线呈上升趋势'
            },
            {
                'name': '趋势角(ang3)',
                'rule': f"ang3 ≥ {params.get('ang3_min',0)}°",
                'param': f"ang3_min={params.get('ang3_min',0)}",
                'description': '3日线性回归角度不向下'
            },
            {
                'name': '偏离度',
                'rule': f"wc={params.get('deviation_wc',0.5)}, tc={params.get('deviation_tc',0.3)}, vc={params.get('deviation_vc',0.2)}",
                'param': f"deviation_wc={params.get('deviation_wc',0.5)}, deviation_tc={params.get('deviation_tc',0.3)}, deviation_vc={params.get('deviation_vc',0.2)}",
                'description': '价格相对成本线的偏离程度判断'
            },
            {
                'name': '趋势线支撑',
                'rule': '当前价位于趋势线上方',
                'param': '',
                'description': '不跌破近期低点形成的趋势线'
            },
            {
                'name': '日跌幅上限',
                'rule': f"单日跌幅 ≤ {-params.get('stop_daily_loss',-0.03)*100:.0f}%",
                'param': f"stop_daily_loss={params.get('stop_daily_loss',-0.03)}",
                'description': '当日不出现异常大跌'
            },
            {
                'name': 'RS跑赢大盘',
                'rule': '相对强度跑赢指数',
                'param': '',
                'description': '个股相对大盘走势更强'
            },
            {
                'name': '大盘绿灯',
                'rule': f"大盘指挥官评分 ≥ {params.get('market_green_light',50)}",
                'param': f"market_green_light={params.get('market_green_light',50)}",
                'description': '市场整体环境健康'
            },
        ]

    @staticmethod
    def exit_rules(params=None):
        """出场6级规则"""
        if params is None:
            cfg = load_config()
            params = cfg.get('strategy', {}).get('longhui', {})

        return [
            {'priority': 1, 'name': '移动止盈', 'trigger': f'ATR×{params.get("exit_atr_multiplier",2.0)}倍追踪', 'description': '价格回撤超过ATR倍数→出场'},
            {'priority': 2, 'name': '布林空', 'trigger': f'价格跌破布林上轨{params.get("exit_bollinger_sigma",2.0)}σ', 'description': '趋势减弱→出场'},
            {'priority': 3, 'name': '缩量滞涨', 'trigger': f'角度<{params.get("exit_shrink_angle",-0.5)}°+缩量', 'description': '量价背离→出场'},
            {'priority': 4, 'name': '放量断板', 'trigger': f'量比>{params.get("exit_volume_ratio",2.0)}倍+跌', 'description': '放量下跌→出场'},
            {'priority': 5, 'name': '破高量结构', 'trigger': f'跌破+冷却{params.get("exit_cooling_days",5)}天', 'description': '关键结构位破位→出场'},
            {'priority': 6, 'name': '破趋势线', 'trigger': f'ATR×{params.get("exit_trendline_atr",2.0)}缓冲', 'description': '最后防线→出场'},
        ]


class AttackDefendStrategy:
    """攻守双驱V1策略"""

    @staticmethod
    def summary(params=None):
        if params is None:
            cfg = load_config()
            params = cfg.get('strategy', {}).get('attack_defend', {})

        return {
            'attack': {
                'strategy': '动量轮动',
                'window': f"{params.get('momentum_window', 20)}日",
                'description': '选取动量最强的前N只标的'
            },
            'defend': {
                'strategy': '低波防御',
                'window': f"{params.get('lowvol_window', 60)}日",
                'description': '选取波动率最低的前N只标的'
            },
            'rebalance': f"每{params.get('rebalance_days', 20)}日换仓",
        }


# ─── CLI ───
def main():
    parser = argparse.ArgumentParser(description='来福策略引擎')
    parser.add_argument('--show', action='store_true', help='显示策略规则')
    parser.add_argument('--status', action='store_true', help='显示当前参数')
    parser.add_argument('--set', nargs=2, metavar=('KEY', 'VALUE'), help='设置参数，如: --set longhui.shrink_ratio_min 0.30')
    parser.add_argument('--reset', action='store_true', help='恢复默认参数')
    args = parser.parse_args()

    if args.show:
        print("🔬 龙回2号策略引擎")
        print("=" * 50)
        print("\n📥 入场过滤（10层）：")
        for f in LonghuiStrategy.entry_filters():
            print(f"  [{f['name']}] {f['rule']}")
            if f['description']:
                print(f"    → {f['description']}")
        print("\n📤 出场规则（6级）：")
        for e in LonghuiStrategy.exit_rules():
            print(f"  {e['priority']}. {e['name']} — {e['trigger']}")
        print("\n⚔️ 攻守双驱V1：")
        adv = AttackDefendStrategy.summary()
        print(f"  攻策：{adv['attack']['strategy']}（{adv['attack']['window']}）")
        print(f"  守策：{adv['defend']['strategy']}（{adv['defend']['window']}）")
        print(f"  换仓：{adv['rebalance']}")
        return

    if args.status:
        cfg = load_config()
        lh = cfg.get('strategy', {}).get('longhui', {})
        print("🔬 当前策略参数")
        print("=" * 50)
        for k, v in lh.items():
            print(f"  {k}: {v}")
        return

    if args.set:
        key, value = args.set
        cfg = load_config()
        strategy, param = key.split('.', 1)
        try:
            value = float(value) if '.' in value else int(value)
        except ValueError:
            pass
        cfg['strategy'][strategy][param] = value
        save_config(cfg)
        print(f"✅ {key} = {value}")
        return

    if args.reset:
        # Reset to defaults
        default_cfg = load_config()
        default_cfg['strategy']['longhui'] = {
            'time_window_min': 3, 'time_window_max': 12,
            'shrink_ratio_min': 0.25, 'shrink_ratio_max': 0.55,
            'price_discount': 0.98, 'ma_trend': 20,
            'ang3_min': 0,
            'deviation_wc': 0.5, 'deviation_tc': 0.3, 'deviation_vc': 0.2,
            'stop_daily_loss': -0.03, 'market_green_light': 50,
            'exit_atr_multiplier': 2.0, 'exit_bollinger_sigma': 2.0,
            'exit_shrink_angle': -0.5, 'exit_volume_ratio': 2.0,
            'exit_trendline_atr': 2.0, 'exit_cooling_days': 5,
        }
        save_config(default_cfg)
        print("✅ 已恢复默认参数")
        return

    parser.print_help()


if __name__ == '__main__':
    main()
