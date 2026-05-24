# 来福量化策略助手 · QClaw 技能包

龙回2号 + 攻守双驱V1 量化策略智能助手。适用于 QClaw 桌面客户端。

## 一键安装

1. 打开 QClaw
2. 技能管理 → 从 GitHub 导入
3. 输入：`[你的GitHub用户名]/qclaw-laifu-skill`
4. 点击导入，完成

## 功能

| 能力 | 怎么用 |
|------|--------|
| 策略规则查询 | "龙回策略胜率多少" "出场规则是什么" |
| 行情数据 | "今天大盘怎么样" "AI板块资金" |
| 信号扫描 | "扫描今天信号"（需要先配Python引擎） |
| 回测分析 | "跑回测" "参数扫描" |
| 复盘报告 | "生成今日复盘" |

## 前置条件（可选）

不配置也能用策略知识和行情查询。回测/扫描需要安装 Python 引擎：

```bash
pip install pandas numpy requests pyyaml openai
```

然后修改 `config.yaml` 填入你的 DeepSeek key 和通达信路径。

## 文件结构

```
qclaw-laifu-skill/
├── SKILL.md       ← QClaw 技能文件（核心）
├── README.md      ← 本文件
├── config.yaml    ← 用户配置模板
└── engine/        ← Python 策略引擎
    ├── strategy.py
    ├── backtest.py
    ├── scanner.py
    └── ...
```
