# Demo 3 ｜ Browser Agent / Computer Use

Demo 3 implements a Playwright browser agent with Set-of-Mark grounding. The loop is:

```text
screenshot -> mark visible controls -> model chooses JSON action -> guardrails -> Playwright action -> trace
```

The default model is `gpt-5.5` via an OpenAI-compatible chat completions endpoint. `deepseek-v4-pro` configuration is reserved for later switching; if the endpoint does not support vision input, the run fails clearly instead of using hardcoded behavior.

## Tasks

- `ebay`: live eBay search for `USB-C hub`, sort by price plus shipping lowest first, capture the first 3 organic product detail pages.
- `github-issues`: live GitHub UI for `modelcontextprotocol/servers` open issues with the `bug` label.
- `local-form`: local controllable support form requiring form filling and a visible conditional branch decision.
- `modal-wall`: live Cookiebot consent page; identify the cookie popup and reject/dismiss non-essential cookies.

CSV artifacts are written from the model's final structured `finish` payload.

## Setup

```powershell
conda env update -n agent-frontier -f environment.yml --prune
conda run -n agent-frontier python -m pip install -e .
conda run -n agent-frontier python -m playwright install chromium
```

Or:

```powershell
make install
make browsers
```

Copy `.env.example` to `.env` and fill the provider settings:

```env
DEMO3_PROVIDER=openai
DEMO3_MODEL=gpt-5.5
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
DEMO3_DASHBOARD_REFRESH_SECONDS=1.5
DEMO3_INPUT_PRICE_PER_1M=0
DEMO3_OUTPUT_PRICE_PER_1M=0
```

`输入 tokens` / `输出 tokens` come from the model gateway's `usage` field. If the OpenAI-compatible gateway does not return usage, Demo 3 records `0` rather than fabricating a value. Cost is estimated from `DEMO3_INPUT_PRICE_PER_1M` and `DEMO3_OUTPUT_PRICE_PER_1M`; keep them at `0` when the gateway price is unknown.

## Run

Start the 70/30 dashboard:

```powershell
make demo
```

Open:

```text
http://localhost:8503
```

Run all tasks from CLI:

```powershell
make run-all
```

Run summary panel:

```powershell
make demo-all
```

Replay latest trace:

```powershell
make replay
```

## Outputs

Each run writes:

```text
outputs/runs/<run_id>/trace.jsonl
outputs/runs/<run_id>/state.json
outputs/runs/<run_id>/summary.json
outputs/runs/<run_id>/screenshots/
outputs/runs/<run_id>/artifacts/
```

The latest run pointer is `outputs/latest.json`. A Windows-safe top-level copy of the latest trace is also written to `trace.jsonl`.

## Guardrails

- Maximum 30 steps per task.
- One retry per task.
- Configurable login/payment/account/destructive URL blacklist.
- Submit/save/delete/confirm/close-like actions are logged with `[ACTION]` before execution.
- Ctrl+C writes an interrupt trace and closes browser/local server.

## Browser check

```powershell
conda run -n agent-frontier python -m demo3_browser_agent.runner --check-browser
```

If eBay or GitHub cannot be reached with Playwright during verification, stop and decide whether to replace the task or add a fallback.
