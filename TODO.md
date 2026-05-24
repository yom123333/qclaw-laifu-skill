# 来福策略工具箱 · 最终清单

## 砍掉（QClaw 内置更好）

- [ ] 删除 `engine/iwencai.py` — QClaw NeoData 更准更快
- [ ] 删除 `engine/sentinel.py` — QClaw cron + 弹窗替代
- [ ] 删除 `engine/notification_service.py` — QClaw 原生推送
- [ ] 删除 `engine/sentinel_poller.py` — QClaw 定时引擎替代
- [ ] 删除 `desktop/` 整个目录 — pywebview 方案已放弃

## 保留并完善（QClaw 做不到的）

### 1. 智能体提示词
- [ ] 精简提示词（砍掉 i问财 URL，改为告诉 AI 用 NeoData）
- [ ] 保留完整策略规则、回测数据、引擎命令、行为约束

### 2. 回测引擎 `engine/backtest.py`
- [ ] 已有：10层过滤 + 6级出场 + 蒙特卡洛 + 参数扫描
- [ ] 测试：确认能读 vipdoc 跑出真实结果

### 3. 信号扫描 `engine/scanner.py`
- [ ] 已有：全市场遍历 + 信号输出 + 历史追踪
- [ ] 测试：确认能扫出真实信号

### 4. 复盘生成 `engine/review.py` 【需重写】
- [ ] QClaw cron 定时触发（如每个交易日 15:30）
- [ ] 从 NeoData 拿市场数据（涨跌家数/涨停跌停/板块资金/龙虎榜）
- [ ] 从 scanner.py 拿信号扫描结果
- [ ] 按复盘模板填入数据，生成结构化报告
- [ ] 通过 QClaw 推送到微信

### 5. 策略参数管理 `engine/strategy.py`
- [ ] 已有：参数展示/修改/重置

### 6. 数据读取 `engine/utils.py`
- [ ] 已有：vipdoc 二进制读取、指标计算、配置管理

### 7. 配置文件 `config.yaml`
- [ ] DeepSeek key（用户自己填）
- [ ] 通达信 vipdoc 路径
- [ ] 回测参数
- [ ] 预警阈值

## 新增

### 8. 用户安装指南 `README.md`
- [ ] 30秒安装（粘贴提示词）
- [ ] 引擎安装（pip install + 配置）
- [ ] 复盘自动推送设置（QClaw cron 教程）
- [ ] 常见问题 FAQ

### 9. 复盘自动推送 — QClaw cron 配置
- [ ] 写一段给 QClaw 看的 cron 配置指令（用户粘贴到对话即可）
- [ ] 每个交易日 15:30 自动运行复盘脚本
- [ ] 结果推送到微信

## 最终文件结构

```
qclaw-laifu-skill/
├── 来福智能体提示词.txt    ← 复制粘贴到QClaw，30秒装好
├── README.md              ← 完整安装教程
├── config.yaml            ← 用户配置模板
├── engine/
│   ├── backtest.py        ← 回测引擎（核心）
│   ├── scanner.py         ← 信号扫描（核心）
│   ├── review.py          ← 复盘生成（核心）
│   ├── strategy.py        ← 策略参数管理
│   └── utils.py           ← vipdoc读取+工具函数
└── LICENSE.md             ← 许可协议
```
