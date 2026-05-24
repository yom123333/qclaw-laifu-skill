# 来福 · 龙回2号策略助手

QClaw 智能体，一键安装。

## 安装（30秒）

1. QClaw → 新建智能体 → 名称填"来福" → 模型选 DeepSeek
2. 打开 `来福智能体提示词.txt` → 全选复制
3. 粘贴到智能体的"描述/提示词"栏 → 保存
4. 开始对话

## 功能

- 龙回2号完整策略规则（10层过滤+6级出场）
- 攻守双驱V1策略
- 历史回测数据
- 大盘红绿灯
- i问财行情查询

## 进阶（可选）

基础版粘贴提示词就能用。如需回测计算和信号扫描，额外安装 Python 引擎：

```bash
pip install pandas numpy requests pyyaml
```

将 `engine/` 目录复制到 `~/.openclaw/engine/`，修改 `config.yaml` 填入 DeepSeek key 和通达信路径。
