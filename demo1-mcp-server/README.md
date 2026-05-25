# Demo 1｜MCP Server

本 Demo 实现了一个可复用的 MCP stdio 运维服务器，用于 `Agent 进阶三连` 作业/演示。服务器暴露 MCP Tools、Resources 和 Prompts，可通过 MCP Inspector 调用，也支持一键自动验收。

## 1. 模型与客户端

- Server 本身不依赖大模型，不绕过 MCP client，也不硬编码模型回答。
- 推荐客户端：MCP Inspector。
- 传输方式：stdio。
- 运行环境：Conda 环境 `agent-frontier`，Python 3.11。

## 2. 安装依赖

在本目录执行：

```powershell
cd E:\AAA\Project\agent-frontier\demo1-mcp-server
conda env update -n agent-frontier -f environment.yml --prune
conda run -n agent-frontier pip install -e .
conda activate agent-frontier
```

也可以使用快捷命令：

```powershell
make install
conda activate agent-frontier
```

`make install` 会执行：

```powershell
conda env update -n agent-frontier -f environment.yml --prune
conda run -n agent-frontier pip install -e .
```

> Windows 说明：`environment.yml` 已包含 `m2-make`，用于在 Windows/Conda 环境中提供 `make` 命令。

## 3. 常用命令

### 3.1 启动实时 dashboard

```powershell
make demo
```

该命令启动 TUI dashboard，用于观察 `trace.jsonl` 中的 MCP 调用事件。

### 3.2 启动 MCP Inspector

另开一个 PowerShell：

```powershell
conda activate agent-frontier
cd E:\AAA\Project\agent-frontier\demo1-mcp-server
make inspector
```

然后在浏览器打开 Inspector 输出的地址，建议使用：

```text
http://localhost:6274
```

如果使用 `127.0.0.1:6274` 连接失败，请改用 `localhost:6274`。

### 3.3 直接启动 MCP server

```powershell
make server
```

### 3.4 清空 trace

```powershell
make clean-trace
```

### 3.5 回放 trace

```powershell
make replay
```

或：

```powershell
python replay.py --trace trace.jsonl --no-delay
```

## 4. 一键验收命令

### 4.1 运行全部验收用例

```powershell
make demo-all
```

`demo-all` 会运行 6 个验收用例，并输出左右自适应的 summary 面板：

- 左侧：real-time trace
- 右侧：验收状态汇总

窗口较窄时会自动切换成上下布局，避免表格被挤压。

### 4.2 运行指定验收用例

```powershell
make demo-test CASE=1
make demo-test CASE=query_metric
make demo-test CASE=restart
make demo-test CASE=resource
make demo-test CASE=prompt
make demo-test CASE=shutdown
```

也支持多个用例：

```powershell
make demo-test CASE=1,3,5
```

### 4.3 自定义测试输入

`query_metric` 用例支持自定义参数：

```powershell
make demo-test CASE=query_metric SERVICE=payment-api METRIC=p99 WINDOW=10m
```

通用参数：

| 参数 | 说明 | 默认值 |
|---|---|---|
| `CASE` | 指定用例编号或别名 | 全部用例 |
| `SERVICE` | 服务名 | `payment-api` |
| `METRIC` | 指标名 | `p99` |
| `WINDOW` | 时间窗口 | `15m` |

支持的 `CASE`：

| CASE | 对应用例 |
|---|---|
| `1`, `query_metric`, `query` | 调用 `query_metric` tool |
| `2`, `reconnect` | 第二客户端/重连验证 |
| `3`, `restart`, `restart_service` | `restart_service` dry-run 安全验证 |
| `4`, `resource`, `incident` | 读取 `incident://list` resource |
| `5`, `prompt`, `oncall` | 获取 `oncall-triage` prompt |
| `6`, `shutdown`, `error` | 关闭 server 后错误处理验证 |

## 5. MCP Tools

### `query_metric(service, metric, window)`

查询服务指标，返回结构化时序数据。

示例：

```json
{
  "service": "payment-api",
  "metric": "p99",
  "window": "15m"
}
```

### `tail_log(service, lines, level)`

读取指定服务日志。

### `restart_service(service, dry_run=true)`

预演或执行服务重启。

默认：

```json
{
  "service": "payment-api"
}
```

返回应包含：

```json
{
  "dry_run": true,
  "executed": false
}
```

显式执行：

```json
{
  "service": "payment-api",
  "dry_run": false
}
```

返回应包含：

```json
{
  "dry_run": false,
  "executed": true
}
```

> MCP Inspector 中布尔参数的 optional toggle 可能表示“是否传该字段”。如果取消勾选后字段被省略，server 会使用默认值 `dry_run=true`。要真执行，必须显式传入 `dry_run=false`。

### `notify_oncall(service, summary, severity)`

写入 on-call 通知记录。

## 6. MCP Resources

### `incident://list`

读取 incident 列表。该能力应通过 MCP Resource 通道调用，不是 Tool 调用。

### `runbook://{service}`

读取指定服务的 runbook，例如：

```text
runbook://payment-api
```

## 7. MCP Prompt

### `oncall-triage(service)`

生成 on-call triage prompt 模板。

示例参数：

```json
{
  "service": "payment-api"
}
```

返回模板中应包含 `payment-api`，并指导客户端/模型使用 MCP tools 和 resources 完成排障。

## 8. 手动验收清单

| # | 场景 | 通过标准 |
|---|---|---|
| 1 | 客户端发起 tool 调用 `query_metric(payment-api, p99, 15m)` | server 返回结构化时序数据，参数无误 |
| 2 | 同一 server 被第二个客户端或同客户端重启后再次接入 | 不改代码即可被调用 |
| 3 | 调用 `restart_service(payment-api)` | 默认 `dry_run=true` 预演；显式 `dry_run=false` 才真重启 |
| 4 | 客户端读取 `incident://list` resource | 走 Resource 通道，不是 Tool 调用 |
| 5 | 客户端唤出 `oncall-triage(service=payment-api)` prompt | 模板被正确填充 |
| 6 | 关掉 server 进程 | 客户端显示清晰错误，例如 `Connection closed` / `ClosedResourceError`，不挂死，不假装成功 |

## 9. Trace 与 Dashboard

所有 tool/resource/prompt/server 事件都会追加写入：

```text
trace.jsonl
```

`make demo` 会读取该文件并显示实时 trace 与统计面板；`make replay` 会按历史顺序回放已有 trace，便于演示和复盘。

如果 dashboard 在某些 PowerShell 环境下刷新异常，可以直接运行：

```powershell
python -m demo1_mcp.dashboard
```

或切换到 Windows Terminal / VS Code Terminal。
