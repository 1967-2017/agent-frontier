.PHONY: install data demo run-2 run-10 run-100 demo-all replay report

CONDA_ENV ?= agent-frontier
QUESTIONS ?= 10
PYTHON ?= conda run -n $(CONDA_ENV) python
STREAMLIT ?= conda run --no-capture-output -n $(CONDA_ENV) streamlit

install:
	conda env update -n $(CONDA_ENV) -f environment.yml --prune
	$(PYTHON) -m pip install -e .

data:
	$(PYTHON) -m demo2_reasoning.dataset download --limit 100

demo:
	$(info Starting Demo2 dashboard at http://localhost:8501)
	$(STREAMLIT) run src/demo2_reasoning/dashboard.py --server.headless true --server.port 8501

run-2:
	$(PYTHON) -m demo2_reasoning.runner --questions 2

run-10:
	$(PYTHON) -m demo2_reasoning.runner --questions 10

run-100:
	$(PYTHON) -m demo2_reasoning.runner --questions 100

demo-all:
	$(PYTHON) -m demo2_reasoning.demo_all --questions $(QUESTIONS)

replay:
	$(PYTHON) replay.py --latest --no-delay

report:
	$(PYTHON) -m demo2_reasoning.report --latest
