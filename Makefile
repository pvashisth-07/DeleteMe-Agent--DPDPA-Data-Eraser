.PHONY: install test lint preflight run-all demo

PYTHON ?= python

install:
	pip install -r requirements.txt

test:
	pytest tests

lint:
	python -m py_compile agents/**/*.py shared/*.py mcp/*.py scripts/*.py

preflight:
	python scripts/preflight.py

run-all:
	python -m agents.concierge.agent

demo:
	python scripts/demo.py
