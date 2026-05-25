.PHONY: env install server dashboard demo demo-all demo-test inspector replay clean-trace

CONDA_ENV ?= agent-frontier
PYTHON ?= conda run -n $(CONDA_ENV) python
PIP ?= conda run -n $(CONDA_ENV) pip
DASHBOARD_PYTHON ?= python
ACCEPTANCE_PYTHON ?= python
INSPECTOR_PYTHON ?= python
REPLAY_PYTHON ?= python
NPX ?= npx.cmd


env:
	conda env update -n $(CONDA_ENV) -f environment.yml --prune

install: env
	$(PIP) install -e .

server:
	$(PYTHON) -m demo1_mcp.server

dashboard:
	$(DASHBOARD_PYTHON) -m demo1_mcp.dashboard

demo: dashboard

demo-all:
	$(ACCEPTANCE_PYTHON) -m demo1_mcp.acceptance --no-live

demo-test:
	$(ACCEPTANCE_PYTHON) -m demo1_mcp.acceptance --no-live $(if $(CASE),--case $(CASE),) $(if $(SERVICE),--service $(SERVICE),) $(if $(METRIC),--metric $(METRIC),) $(if $(WINDOW),--window $(WINDOW),)

inspector:
	$(NPX) @modelcontextprotocol/inspector $(INSPECTOR_PYTHON) -m demo1_mcp.server

replay:
	$(REPLAY_PYTHON) replay.py --trace trace.jsonl --no-delay

clean-trace:
	$(PYTHON) -c "from pathlib import Path; Path('trace.jsonl').write_text('', encoding='utf-8')"
