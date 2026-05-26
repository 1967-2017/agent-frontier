.PHONY: demo1 demo1-all demo1-test replay1 demo2 demo2-all replay2

QUESTIONS ?= 10

demo1:
	$(MAKE) -C demo1-mcp-server demo1

demo1-all:
	$(MAKE) -C demo1-mcp-server demo1-all

demo1-test:
	$(MAKE) -C demo1-mcp-server demo1-test CASE="$(CASE)" SERVICE="$(SERVICE)" METRIC="$(METRIC)" WINDOW="$(WINDOW)"

replay1:
	$(MAKE) -C demo1-mcp-server replay1

demo2:
	$(MAKE) -C demo2-reasoning-ttc demo

demo2-all:
	$(MAKE) -C demo2-reasoning-ttc demo-all QUESTIONS="$(QUESTIONS)"

replay2:
	$(MAKE) -C demo2-reasoning-ttc replay
