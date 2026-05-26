# Demo 2 ｜ 推理模型 + Test-Time Compute

本 demo 用 GSM8K-Hard 数据集评估不同推理策略与模型组合，重点观察 Test-Time Compute 对准确率、耗时和估算成本的影响。

当前对比两个模型提供方：

- GPT：`gpt-5.5`
- DeepSeek：`deepseek-v4-pro`

## 重要约束

- 不硬编码答案。
- 不使用绕过模型调用的 `if/else` 逻辑。
- Prompt 只使用数据集的 `input` 字段。
- 数据集的 `target` 字段只用于评分。
- 数据集的 `code` 字段不会发送给模型。
- token 和成本是 demo 估算值，基于 prompt/output 长度，不代表供应商真实计费。
- 最终价值结论只使用准确率和真实 wall time，不使用估算 token/cost。

## 数据集

GSM8K-Hard 数据源：

```text
https://raw.githubusercontent.com/usail-hkust/benchmark_inference_time_computation_LLM/011e76db/data/gsm8k/gsmhardv2.jsonl
```

字段说明：

- `input`：题目文本。
- `target`：标准答案，仅用于评分。
- `code`：忽略，不发送给模型。

## 模型

- GPT：`gpt-5.5`
- DeepSeek：`deepseek-v4-pro`

环境变量：

```bash
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
```

如果使用 OpenAI-compatible 代理，请将 `*_BASE_URL` 配置为对应代理的 `/v1` 基础路径，具体路径以代理服务要求为准。

## 推理策略

- `Baseline`：零样本直接回答，不显式要求推理。
- `CoT`：Prompt 中包含 `Think step by step`，要求模型逐步推理。
- `Native Thinking`：使用模型原生 thinking 能力；不支持的模型会被跳过。
  - `thinking: {type: enabled}`
  - `reasoning_effort: high`
- `BoN=5 + SC`：每题真实调用模型 5 次，再通过 majority vote 做 self-consistency。

## 命令

安装依赖：

```bash
make install
```

下载数据：

```bash
make data
```

启动 Streamlit 看板：

```bash
make demo
```

浏览器访问：

```text
http://localhost:8501
```

快速跑 2 题：

```bash
make run-2
```

跑 10 题：

```bash
make run-10
```

跑 100 题：

```bash
make run-100
```

跑完整 demo 并输出终端汇总面板：

```bash
make demo-all
```

默认题数是 10，也可以指定：

```bash
make demo-all QUESTIONS=2
make demo-all QUESTIONS=100
```

回放最近一次 trace：

```bash
make replay
```

生成最近一次报告：

```bash
make report
```

## Streamlit 看板

`make demo` 会启动实时看板。看板支持：

- 选择题目数量：2 / 10 / 100。
- 点击 `Run Evaluation` 后后台运行评测。
- 实时显示进度条、耗时和估算成本。
- 实时展示策略 × 模型指标矩阵。
- `BoN=5 + SC` 在完成列展示当前 sample，例如 `sample 1/5`。
- 实时展示最近错题的 thinking 摘要。
- 运行完成后展示一句话结论和 `Accuracy vs Estimated Cost` 散点图。

## 输出文件

每次运行会写入：

```text
outputs/runs/<run_id>/trace.jsonl
outputs/runs/<run_id>/results.jsonl
outputs/runs/<run_id>/summary.json
outputs/runs/<run_id>/metrics.csv
outputs/runs/<run_id>/report.md
outputs/runs/<run_id>/scatter.png
outputs/runs/<run_id>/state.json
```

说明：

- `trace.jsonl`：事件流，用于 `make replay` 回放。
- `results.jsonl`：每次模型调用结果；`BoN=5 + SC` 也会额外写入 `sample_index = 0` 的 majority-vote aggregate 结果。
- `summary.json`：最终汇总数据，包含 `one_line_conclusion`。
- `metrics.csv`：最终指标表。
- `report.md`：Markdown 报告。
- `scatter.png`：Accuracy vs Estimated Cost 散点图。
- `state.json`：运行状态，供 Streamlit 实时刷新使用。

## 最终指标

最终矩阵包含：

```markdown
| 策略 | 模型 | 状态 | 完成 | 正确 | 准确率 | 平均 wall time | 平均 thinking tokens | 单题成本 | 总成本 |
```

结论格式：

```markdown
本任务最划算的是 X 策略 + Y 模型，因为 ____
```

## 注意事项

- `make replay` 需要先有至少一次运行结果，否则没有 `outputs/latest.json` 可读取。
- 如果刚清空 outputs，需要先运行 `make run-2`、`make demo-all` 或在网页中点击 `Run Evaluation`。
- 历史运行记录不会自动纳入新 run；run id 使用微秒级时间戳，避免旧结果污染新运行。
