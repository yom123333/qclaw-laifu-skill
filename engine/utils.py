"""来福工具箱 — 数据读取 & 配置管理"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import struct
import yaml
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

TOOLBOX_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = TOOLBOX_ROOT / "config.yaml"


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_config(cfg):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)


def get_vipdoc_path():
    """获取通达信vipdoc路径，自动探测常见安装位置"""
    cfg = load_config()
    path = cfg.get('tdx', {}).get('vipdoc_path', '')
    if path and os.path.exists(path):
        return path
    candidates = [
        r"C:\zd_zsone\T0002\vipdoc",
        r"C:\new_tdx\T0002\vipdoc",
        r"D:\zd_zsone\T0002\vipdoc",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError("未找到通达信vipdoc，请在config.yaml设置tdx.vipdoc_path")


def read_stock_day(code, market=None):
    """读取单只股票全部日K数据，返回DataFrame"""
    if market is None:
        market = 'sh' if str(code).startswith(('6', '5')) else 'sz'

    vipdoc = get_vipdoc_path()
    day_file = os.path.join(vipdoc, market, 'lday', f'{market}{code}.day')

    if not os.path.exists(day_file):
        return None

    with open(day_file, 'rb') as f:
        raw = f.read()

    records = []
    for i in range(0, len(raw), 32):
        chunk = raw[i:i+32]
        if len(chunk) < 32:
            break
        date_int, op, hi, lo, cl, amt, vol, _ = struct.unpack('=iffffiff', chunk)

        # Validate date
        if date_int < 19900101 or date_int > 20991231:
            continue

        records.append({
            'date': pd.Timestamp(str(date_int)),
            'open': op, 'high': hi, 'low': lo, 'close': cl,
            'amount': amt, 'volume': vol,
        })

    if not records:
        return None

    df = pd.DataFrame(records).sort_values('date').reset_index(drop=True)
    df['code'] = str(code).zfill(6)
    return df


def load_market_data(codes, start_date, end_date):
    """批量加载多只股票日K数据"""
    all_data = []
    for i, code in enumerate(codes):
        code_str = str(code).zfill(6)
        df = read_stock_day(code_str)
        if df is not None:
            df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
            if len(df) > 0:
                all_data.append(df)
        if (i + 1) % 500 == 0:
            print(f"  已加载 {i+1}/{len(codes)} 只股票...")

    if not all_data:
        raise RuntimeError("未读取到任何数据，请检查vipdoc路径")

    return pd.concat(all_data, ignore_index=True)


def get_all_stock_codes():
    """获取vipdoc中所有股票代码"""
    vipdoc = get_vipdoc_path()
    codes = set()
    for market in ['sh', 'sz']:
        lday_dir = os.path.join(vipdoc, market, 'lday')
        if not os.path.exists(lday_dir):
            continue
        for fname in os.listdir(lday_dir):
            if fname.endswith('.day'):
                code = fname.replace(market, '').replace('.day', '')
                if code.isdigit() and len(code) == 6:
                    codes.add(code)
    return sorted(codes)


def calc_ma(series, window):
    """计算移动平均"""
    return series.rolling(window).mean()


def calc_angle(series, window=3):
    """计算线性回归角度（度）"""
    if len(series) < window:
        return np.nan
    x = np.arange(window)
    y = series.iloc[-window:].values
    slope = np.polyfit(x, y, 1)[0]
    return np.degrees(np.arctan(slope))


def calc_deviation(close, cost_line, ma20):
    """计算偏离度"""
    if ma20 == 0:
        return 0
    wc = abs(close - cost_line) / close if close != 0 else 0
    tc = abs(close - ma20) / close if close != 0 else 0
    return 0.5 * wc + 0.3 * tc + 0.2 * (wc + tc) / 2


def find_attack_day(df, idx, vol_ratio_min=2.0):
    """判断某天是否为攻击日（涨停放量）"""
    if idx < 20:
        return False
    row = df.iloc[idx]
    # 涨停判断：涨幅>9.5% 或 收盘=涨停价
    prev_close = df.iloc[idx - 1]['close']
    if prev_close == 0:
        return False
    chg = (row['close'] / prev_close - 1)
    if chg < 0.095:
        return False
    # 放量判断
    avg_vol = df.iloc[idx-20:idx]['volume'].mean()
    if avg_vol == 0:
        return False
    return row['volume'] / avg_vol >= vol_ratio_min


def format_pct(v):
    """格式化百分比"""
    return f"{v*100:+.2f}%" if isinstance(v, float) else v


def format_money(v):
    """格式化金额"""
    if abs(v) >= 1e8:
        return f"{v/1e8:.2f}亿"
    elif abs(v) >= 1e4:
        return f"{v/1e4:.0f}万"
    return f"{v:.2f}"
