.PHONY: demo1 demo1-all demo1-test demo1-replay demo-all demo-test replay

demo1:
	$(MAKE) -C demo1-mcp-server demo

demo1-all:
	$(MAKE) -C demo1-mcp-server demo-all

demo1-test:
	$(MAKE) -C demo1-mcp-server demo-test CASE="$(CASE)" SERVICE="$(SERVICE)" METRIC="$(METRIC)" WINDOW="$(WINDOW)"

demo1-replay:
	$(MAKE) -C demo1-mcp-server replay

demo-all: demo1-all

demo-test: demo1-test

replay: demo1-replay
