"""来福工具箱 — 通用工具"""
import os
import yaml
from pathlib import Path

TOOLBOX_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = TOOLBOX_ROOT / "config.yaml"


def load_config():
    """加载用户配置文件"""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"配置文件未找到: {CONFIG_PATH}\n请复制 config.yaml.example 为 config.yaml 并填写配置")
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_config(cfg):
    """保存配置"""
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)


def get_vipdoc_path():
    """获取通达信vipdoc路径"""
    cfg = load_config()
    path = cfg.get('tdx', {}).get('vipdoc_path', '')
    if not path or not os.path.exists(path):
        # 尝试常见路径
        candidates = [
            r"C:\zd_zsone\T0002\vipdoc",
            r"C:\new_tdx\T0002\vipdoc",
            r"D:\zd_zsone\T0002\vipdoc",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        raise FileNotFoundError("未找到通达信vipdoc目录，请在config.yaml中设置tdx.vipdoc_path")
    return path


def get_deepseek_client():
    """初始化DeepSeek客户端"""
    cfg = load_config()
    api_key = cfg.get('deepseek', {}).get('api_key', '')
    base_url = cfg.get('deepseek', {}).get('base_url', 'https://api.deepseek.com')

    if not api_key or api_key == 'sk-your-key-here':
        return None

    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url=base_url)


def format_money(amount):
    """格式化金额"""
    if abs(amount) >= 1e8:
        return f"{amount/1e8:.2f}亿"
    elif abs(amount) >= 1e4:
        return f"{amount/1e4:.0f}万"
    return f"{amount:.2f}"


def format_pct(value):
    """格式化百分比"""
    return f"{value*100:+.2f}%"


def read_vipdoc_day(code, date_str):
    """读取单只股票单日日K数据"""
    # code format: sh600326 or sz002951
    path = get_vipdoc_path()
    market = 'sh' if code.startswith('6') else 'sz'
    # vipdoc day file: e.g. vipdoc/sz/lday/sz002951.day
    day_path = os.path.join(path, market, 'lday', f'{market}{code}.day')
    if not os.path.exists(day_path):
        return None

    import struct
    with open(day_path, 'rb') as f:
        data = f.read()

    target_date = int(date_str.replace('-', ''))
    record_size = 32
    for i in range(0, len(data), record_size):
        record = data[i:i+record_size]
        if len(record) < record_size:
            break
        date, open_p, high, low, close, amount, vol, _ = struct.unpack('=iffffiff', record)
        if date == target_date:
            return {
                'date': date_str,
                'open': open_p,
                'high': high,
                'low': low,
                'close': close,
                'amount': amount,
                'volume': vol,
            }
    return None
