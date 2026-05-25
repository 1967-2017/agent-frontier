# Agent 进阶三连：MCP × 推理模型 × Computer Use

**周期**：3 天（2026-05-25 → 2026-05-28 EOD）
**模型**：不限，你有什么用什么。每个 demo 在 README 写明实际用了哪家。

---

## 共用要求
- 每个 demo 必须有可见的演示界面（TUI 或 Web 面板）。**纯 print 日志不收。**
- 每个 demo 一份 `trace.jsonl` + `replay.py` 能回放。
- `make demo` 单跑；`make demo-all` 跑全部用例并出汇总面板。
- 禁止：硬编码答案、`if/else` 绕过模型。
---

## Demo 1 ｜ MCP Server

### 任务
用 MCP 协议写一个运维工具 server，能被**任意** MCP 客户端通过 stdio 接入调用。

### 要求

**Tools（stdio transport，4 个）**
- `query_metric(service, metric, window)`
- `tail_log(service, lines, level)`
- `restart_service(service, dry_run=true)` — dry_run 默认 true
- `notify_oncall(service, summary, severity)` — 写入 `notifications.jsonl`

**Resources（2 个）**
- `incident://list`
- `runbook://{service}`

**Prompts（1 个）**
- `oncall-triage(service)`

**客户端**：任选一个能接 stdio MCP 的客户端做演示即可。推荐 [MCP Inspector](https://github.com/modelcontextprotocol/inspector)（官方调试器，浏览器界面，最直观）。README 写清楚你用的是哪个。

**演示界面**：TUI 仪表盘，左半屏实时 trace（tool / resource / prompt 分色），右半屏统计（总调用数 + 工具分布 + 最近参数 diff）。

### 目标（验收用例，全部通过）

| # | 场景 | 通过标准 |
|---|---|---|
| 1 | 客户端发起 tool 调用 `query_metric(payment-api, p99, 15m)` | server 返回结构化时序数据，参数无误 |
| 2 | 同一 server 被第二个客户端（或同客户端重启后）再次接入 | 不改代码即可被调 |
| 3 | 调 `restart_service(payment-api)` | 第一轮 `dry_run=true` 预演 → 显式传 `dry_run=false` 才真重启 |
| 4 | 客户端读取 `incident://list` resource | 走 resource 通道，不是 tool 调用 |
| 5 | 客户端唤出 `oncall-triage(service=payment-api)` prompt | 模板被正确填充 |
| 6 | 关掉 server 进程 | 客户端报清晰错误，不挂死 |

---

## Demo 2 ｜ 推理模型 + Test-Time Compute

### 任务
在同一个评测集上对比 4 种推理策略 × 至少 2 个模型，输出准确率 / 成本 / 延迟报告。

### 要求

**评测集**（自选其一）：
- GSM8K-Hard 100 题
- SWE-bench Verified 10 题
- ARC-AGI-2 30 题
- 自选业务相关评测集（≥ 30 条，必须有标注答案）

**4 种策略，全部必跑**：
1. Baseline：zero-shot，禁 thinking
2. CoT：prompt 加 "think step by step"
3. Native Thinking：开模型原生 thinking（不支持就跳过并说明）
4. Best-of-N=5 + Self-Consistency

**模型**：至少 2 家横向对比。

**演示界面**：实时面板（Streamlit / Gradio / Rich Live）
- 顶部进度条：`策略 3/4 · 题目 27/100 · 已花 $1.23`
- 中部：策略 × 模型 实时指标矩阵
- 底部：最近错题的 thinking 摘要（可折叠）
- 结束：自动弹 accuracy vs cost 散点图

### 目标

输出下面这张表 + 一张散点图 + 一句结论：

| 策略 | 准确率 | 平均 thinking tokens | 平均 wall time | 单题成本 |
|---|---|---|---|---|
| Baseline |  |  |  |  |
| CoT |  |  |  |  |
| Native Thinking |  |  |  |  |
| BoN=5 + SC |  |  |  |  |

结论格式："**本任务最划算的是 X 策略 + Y 模型，因为 ____**"

录屏最后一帧停在散点图 + 结论上。

---

## Demo 3 ｜ Computer Use / Browser Agent

### 任务
做一个看屏幕操作鼠标键盘的 Agent，端到端完成 3 个真实网页/桌面任务。

### 要求

**任务**（4 选 2 + 1 自选）：
- A. arxiv 搜 "MCP protocol"，前 5 篇标题+作者+摘要首句存 csv
- B. GitHub `modelcontextprotocol/servers` 仓库，列所有 `bug` label 的 open issue
- C. 打开 VSCode，新建文件写 fibonacci 函数并保存
- D. 某购物网站搜 "USB-C hub"，按价格升序，截图前 3 个商品
- E. 自选（必须含一次表单填写 + 一次条件分支决策）

**视觉 loop**：截图 → 模型决定动作 → 执行 → 截图 → 循环。
**视觉 grounding**：必须用 Set-of-Mark 或同等方案，不许猜像素坐标。
**Guardrails**：最大 30 步；黑名单 URL；危险动作（提交表单 / 关窗 / 写文件）前打 `[ACTION]` 日志；Ctrl+C 干净退出。

**演示界面**：录屏布局强制左 70% 浏览器/桌面 + 右 30% 决策侧栏
- 当前 step `Step 7 / Max 30`
- 模型一句话推理
- 即将执行的动作（高亮）
- 累计 token / 成本
- 三个任务的状态徽章（⏳ / ✅ / ❌）

### 目标

| # | 场景 | 通过标准 |
|---|---|---|
| 1 | 跑 3 个任务，每个最多重试 1 次 | 至少 2 个一次通过 |
| 2 | 中途断网 5 秒 | Agent 不崩溃，retry 或报失败 |
| 3 | 故意弹窗（cookie / 登录墙） | Agent 识别并处理 |
| 4 | 访问黑名单 URL | 直接拒绝 |
| 5 | `trace.jsonl` 用 replay 脚本回放 | 完整复现操作序列 |

---

## 提交清单

- [ ] 3 个 demo 独立子目录 + README + `.env.example`
- [ ] `make demo` 和 `make demo-all` 都能跑
- [ ] 3 份 `trace.jsonl` + `replay.py`
- [ ] 1 页 cost 报告（3 个 demo 的 token / 钱 / 时间汇总）

