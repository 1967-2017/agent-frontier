# Agent Frontier

本仓库用于 `Agent 进阶三连` 作业/演示，目前包含 Demo 1：一个可复用的 MCP stdio 运维服务器。

## 项目结构

```text
agent-frontier/
├── Makefile                 # 根目录快捷命令
└── demo1-mcp-server/        # Demo 1：MCP Server
```

## 前置要求

- Windows PowerShell / Windows Terminal
- Miniconda 或 Anaconda
- Node.js / npm / npx
- Conda 环境名：`agent-frontier`

> 说明：本项目在 Windows 下使用 `m2-make`，已写入 `demo1-mcp-server/environment.yml`。执行 `make install` 后即可使用 `make` 命令。

## 快速开始

进入 Demo 目录：

```powershell
cd E:\AAA\Project\agent-frontier\demo1-mcp-server
```

安装依赖：

```powershell
make install
conda activate agent-frontier
```

启动实时 trace 面板：

```powershell
make demo
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

## 根目录快捷命令

在仓库根目录也可以执行：

```powershell
make demo1       # 启动 Demo 1 dashboard
make demo-all    # 运行 Demo 1 全部验收用例
make demo-test   # 运行指定验收用例，支持 CASE/SERVICE/METRIC/WINDOW 参数
```

示例：

```powershell
make demo-test CASE=restart
make demo-test CASE=query_metric SERVICE=payment-api METRIC=p99 WINDOW=10m
```

## Demo 1 文档

详细命令、验收用例和 MCP 能力说明见：

```text
demo1-mcp-server/README.md
```
