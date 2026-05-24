# 来福 · 龙回2号量化策略工具箱

QClaw 智能体 + Python 引擎。龙回2号和攻守双驱V1两套经过长期回测验证的 A 股量化策略，封装为可运行的本地工具箱。

## 功能

| 模块 | 做什么 |
|------|--------|
| 策略引擎 | 龙回2号10层过滤+6级出场、攻守双驱V1动量+低波 |
| 回测工坊 | 参数扫描、蒙特卡洛模拟、双策略对比 |
| 信号扫描 | 每日收盘前全市场扫描，通过10层过滤出信号 |
| 持仓监控 | 交易时段每5分钟检查出场触发 |
| 市场风险 | 极端波动/日历风险/结构风险实时预警 |
| AI导师 | 分析历史交易，诊断胜率下降原因 |
| 每日复盘 | 收盘后自动生成完整复盘报告 |
| 策略日记 | 个人持仓出入+盈亏自动记录 |

## 快速安装

### 第一步：安装 Python 引擎
```bash
pip install pandas numpy requests pyyaml openai
```
将 `engine/` 目录复制到 `C:\Users\你的用户名\.qclaw\engine\`
将 `config.yaml` 复制到 `C:\Users\你的用户名\.qclaw\config.yaml`

### 第二步：创建 QClaw 智能体
QClaw → 智能体管理 → 新建 → 名称"来福" → 模型选 DeepSeek
将 `来福智能体提示词.txt` 内容粘贴到描述栏 → 保存

### 第三步：测试
在来福对话框输入：
```
运行 cd ~/.qclaw/engine && python strategy.py --show
```

### 第四步：设定时任务
对话中输入 `帮我设置定时任务`，然后复制 `用户手册.md` 中的定时任务配置。

## 文件结构
```
engine/
├── backtest.py    # 回测引擎
├── scanner.py     # 信号扫描
├── monitor.py     # 持仓监控
├── riskmon.py     # 市场风险哨兵
├── coach.py       # AI策略导师
├── review.py      # 每日复盘+策略日记
├── strategy.py    # 参数管理
└── utils.py       # 数据读取

skills/laifu/SKILL.md   # 完整策略知识库
来福智能体提示词.txt      # QClaw粘贴用
config.yaml             # 用户配置
用户手册.md              # 详细教程
```

## 用户须知
- 本工具仅供策略学习研究，不构成投资建议
- 用户独立做出交易决策，自担风险
- 历史回测数据不代表未来表现
