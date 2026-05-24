# 来福引擎 · 最终清单

## 保留（7个核心文件）

| 文件 | 用途 | 状态 |
|------|------|------|
| `backtest.py` | 回测引擎（10层过滤+6级出场+蒙特卡洛+参数扫描） | ✅ 完成 |
| `scanner.py` | 信号扫描（全市场+详细通过原因+自动入库） | ✅ 完成 |
| `monitor.py` | 出场监控+持仓管理面板 | ✅ 完成 |
| `riskmon.py` | 市场风险哨兵（极端预警+日历+结构风险+分析建议） | ✅ 完成 |
| `review.py` | 每日复盘（市场数据+信号统计+模板填充） | ✅ 完成 |
| `strategy.py` | 策略参数管理+规则展示 | ✅ 完成 |
| `utils.py` | vipdoc读取+指标计算+配置管理 | ✅ 完成 |

## 新增（2个，不建新Agent）

| 文件 | 用途 | 怎么触发 |
|------|------|---------|
| `coach.py` 🆕 | AI策略导师——分析positions.json历史，找胜率下降/回撤扩大原因 | 用户对话触发 `python coach.py` |
| `briefing.py` 🆕 | 盘前简报——合并进riskmon：`python riskmon.py --premarket` | cron 08:55 |

## 不需要新增的（已有或合并）

| 功能 | 做法 | 原因 |
|------|------|------|
| 策略日记 | ❌ 不单建，加到 `review.py --personal` | review已有信号统计，加个--personal读positions.json输出个人持仓总结即可 |
| 盘前简报 | ❌ 不单建，加到 `riskmon.py --premarket` | riskmon已有日历检查，加--premarket查隔夜外盘+今日日历+预期 |

## 砍掉（已删除）

| 文件 | 原因 |
|------|------|
| `iwencai.py` | QClaw NeoData更好 |
| `sentinel.py` | QClaw cron替代 |
| `notification_service.py` | QClaw原生推送 |
| `sentinel_poller.py` | QClaw定时引擎替代 |
| `desktop/` 整个目录 | pywebview方案已放弃 |

## 最终引擎（8个文件）

```
engine/
├── backtest.py    ← 回测
├── scanner.py     ← 信号扫描
├── monitor.py     ← 出场监控+持仓管理
├── riskmon.py     ← 市场风险+盘前简报
├── review.py      ← 每日复盘+策略日记
├── coach.py       ← AI策略导师 🆕
├── strategy.py    ← 参数管理
└── utils.py       ← 数据+工具
```

## 每日定时任务（最终版）

| 时间 | 命令 | 说明 |
|------|------|------|
| 08:55 | `python riskmon.py --premarket` | 盘前简报（隔夜美股+日历+预期） |
| 09:25 | NeoData快照 + `python riskmon.py --calendar` | 开盘快照+日历风险 |
| 09:30-15:00 | `python riskmon.py --check` 每3分钟 | 市场极端监控（静默） |
| 09:30-15:00 | `python monitor.py --activate && python monitor.py --check` 每5分钟 | 出场监控（静默） |
| 14:45 | `python scanner.py --scan --quick && python monitor.py --activate` | 收盘扫描 |
| 15:30 | `python review.py --today --personal` | 策略日记（个人持仓总结） |
| 20:00 | `python review.py --today` | 每日复盘（完整市场报告） |
