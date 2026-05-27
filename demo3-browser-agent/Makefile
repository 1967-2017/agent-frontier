.PHONY: install browsers demo run-all demo-all replay clean-trace

CONDA_ENV ?= agent-frontier
PYTHON ?= conda run -n $(CONDA_ENV) python
STREAMLIT ?= conda run --no-capture-output -n $(CONDA_ENV) streamlit
TASKS ?= arxiv,github-issues,local-form

install:
	conda env update -n $(CONDA_ENV) -f environment.yml --prune
	$(PYTHON) -m pip install -e .
	$(PYTHON) -m playwright install chromium

browsers:
	$(PYTHON) -m playwright install chromium

demo:
	$(info Starting Demo3 dashboard at http://localhost:8503)
	$(STREAMLIT) run src/demo3_browser_agent/dashboard.py --server.headless true --server.port 8503

run-all:
	$(PYTHON) -m demo3_browser_agent.runner --tasks $(TASKS)

demo-all:
	$(PYTHON) -m demo3_browser_agent.demo_all

replay:
	$(PYTHON) replay.py --latest --no-delay

clean-trace:
	$(PYTHON) -c "from pathlib import Path; Path('trace.jsonl').write_text('', encoding='utf-8')"
