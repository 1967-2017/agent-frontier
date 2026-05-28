.PHONY: install browsers demo run-all demo-all replay replay-cli clean-trace

CONDA_ENV ?= agent-frontier
PYTHON ?= conda run -n $(CONDA_ENV) python
STREAMLIT ?= conda run --no-capture-output -n $(CONDA_ENV) streamlit
TASKS ?= ebay,github-issues,local-form

install:
	conda env update -n $(CONDA_ENV) -f environment.yml --prune
	$(PYTHON) -m pip install -e .
	$(PYTHON) -m playwright install chromium

browsers:
	$(PYTHON) -m playwright install chromium

demo:
	$(info Starting Demo3 dashboard at http://localhost:8503)
	DEMO3_MODE=interactive $(STREAMLIT) run src/demo3_browser_agent/dashboard.py --server.headless true --server.port 8503

run-all:
	$(PYTHON) -m demo3_browser_agent.runner --tasks $(TASKS)

demo-all:
	$(info Starting Demo3 dashboard in all-scenarios mode at http://localhost:8503)
	DEMO3_MODE=all $(STREAMLIT) run src/demo3_browser_agent/dashboard.py --server.headless true --server.port 8503

replay:
	$(info Starting Demo3 replay dashboard at http://localhost:8503)
	DEMO3_MODE=replay $(STREAMLIT) run src/demo3_browser_agent/dashboard.py --server.headless true --server.port 8503

replay-cli:
	$(PYTHON) replay.py --latest --no-delay

clean-trace:
	$(PYTHON) -c "from pathlib import Path; Path('trace.jsonl').write_text('', encoding='utf-8')"
