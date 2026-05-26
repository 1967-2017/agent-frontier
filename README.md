# Agent Frontier

本仓库用于 `Agent 进阶三连` 作业/演示，当前包含两个 demo：

- `demo1-mcp-server`：可复用的 MCP stdio 运维服务器。
- `demo2-reasoning-ttc`：推理模型与 Test-Time Compute 评估看板。

## 项目结构

```text
agent-frontier/
├── README.md
├── Makefile
├── demo1-mcp-server/
└── demo2-reasoning-ttc/
```

## 前置要求

- Windows PowerShell / Windows Terminal
- Miniconda 或 Anaconda
- Conda 环境名：`agent-frontier`
- Node.js / npm / npx（仅 Demo 1 启动 MCP Inspector 时需要）

> 说明：本项目在 Windows 下使用 `m2-make`。创建并激活 Conda 环境后即可使用 `make` 命令。

## 快速开始

### Demo 1：MCP Server

进入 Demo 1 目录：

```powershell
cd E:\AAA\Project\agent-frontier\demo1-mcp-server
```

安装依赖：

```powershell
conda env update -n agent-frontier -f environment.yml --prune
conda run -n agent-frontier pip install -e .
conda activate agent-frontier
```

启动 Demo 1 实时 trace 面板：

```powershell
make demo1
```

另开一个 PowerShell，启动 MCP Inspector：

```powershell
conda activate agent-frontier
cd E:\AAA\Project\agent-frontier\demo1-mcp-server
make inspector
```

浏览器打开 Inspector 输出的地址，建议使用：

```text
http://localhost:6274
```

不要优先使用 `127.0.0.1`，因为 Inspector 在部分 Windows 环境下可能只监听 IPv6 localhost。

### Demo 2：推理模型 + Test-Time Compute

进入 Demo 2 目录：

```powershell
cd E:\AAA\Project\agent-frontier\demo2-reasoning-ttc
```

安装依赖：

```powershell
make install
```

下载数据：

```powershell
make data
```

启动 Streamlit 看板：

```powershell
make demo
```

浏览器打开：

```text
http://localhost:8501
```

快速跑 2 题：

```powershell
make run-2
```

跑 10 题或 100 题：

```powershell
make run-10
make run-100
```

跑完整 demo 并在终端输出汇总面板：

```powershell
make demo-all
```

指定题目数量：

```powershell
make demo-all QUESTIONS=2
make demo-all QUESTIONS=100
```

回放最近一次 trace：

```powershell
make replay
```

生成最近一次报告：

```powershell
make report
```

## Demo 2 说明

Demo 2 使用 GSM8K-Hard 数据集，对比不同策略和模型组合：

- GPT：`gpt-5.5`
- DeepSeek：`deepseek-v4-pro`

策略包括：

- `Baseline`：直接回答，不显式要求推理。
- `CoT`：提示模型 step-by-step 推理。
- `Native Thinking`：使用模型原生 thinking 能力；不支持的模型会被跳过。
- `BoN=5 + SC`：每题生成 5 次答案，再用 majority vote 做 self-consistency。

每次运行会写入：

```text
demo2-reasoning-ttc/outputs/runs/<run_id>/trace.jsonl
demo2-reasoning-ttc/outputs/runs/<run_id>/results.jsonl
demo2-reasoning-ttc/outputs/runs/<run_id>/summary.json
demo2-reasoning-ttc/outputs/runs/<run_id>/metrics.csv
demo2-reasoning-ttc/outputs/runs/<run_id>/report.md
demo2-reasoning-ttc/outputs/runs/<run_id>/scatter.png
demo2-reasoning-ttc/outputs/runs/<run_id>/state.json
```

其中：

- `trace.jsonl` 用于 `make replay` 回放。
- `results.jsonl` 记录每次模型调用和 BoN aggregate 结果。
- `summary.json` / `report.md` / `scatter.png` 用于最终汇总展示。
- `state.json` 用于 Streamlit 看板实时显示进度。

## 根目录快捷命令

在仓库根目录也可以执行：

```powershell
make demo1        # 启动 Demo 1 dashboard
make demo1-all    # 运行 Demo 1 全部验收用例
make demo1-test   # 运行 Demo 1 指定验收用例
make replay1      # 回放 Demo 1 trace.jsonl
```

Demo 2 请进入：

```powershell
cd demo2-reasoning-ttc
```

再执行对应 `make` 命令。

## 详细文档

```text
demo1-mcp-server/README.md
demo2-reasoning-ttc/README.md
```
