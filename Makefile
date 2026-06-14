# Basic Makefile for the Àkàndé application.
#
# Common targets:
#   make install         install the runtime + dev extras into the active venv
#   make test            run pytest with coverage gate
#   make lint            run flake8
#   make typecheck       run mypy
#   make audit           run bandit + pip-audit
#   make regression      tear down everything + fresh install + full test sweep
#   make smoke           fast smoke pass (imports + CLI --help)
#   make run             launch the TUI / classic CLI
#   make clean           remove build artefacts

# Copyright (C) 2023-2026 Sebastien Rousseau.
# Apache-2.0 / MIT — see LICENSE-*.

.PHONY: help install dev test lint typecheck audit smoke regression run clean

help:
	@echo "Common targets:"
	@echo "  install      runtime + dev install into the active venv"
	@echo "  test         pytest with coverage gate"
	@echo "  lint         flake8"
	@echo "  typecheck    mypy"
	@echo "  audit        bandit + pip-audit"
	@echo "  smoke        fast smoke: imports + CLI --help"
	@echo "  regression   fresh-install + full gates (./scripts/regression.sh)"
	@echo "  run          launch the assistant"
	@echo "  clean        rm build artefacts"

install:
	pip install --upgrade pip setuptools wheel
	pip install -e ".[all,dev]" mcp

dev: install

test:
	pytest --cov=akande --cov-fail-under=63 -q

lint:
	flake8

typecheck:
	mypy akande

audit:
	bandit -r akande -ll -q
	pip-audit --strict

smoke:
	python -m tests.smoke_imports
	python -m akande --help > /dev/null
	@echo "✓ smoke passed"

regression:
	./scripts/regression.sh

run:
	python -m akande

clean:
	rm -rf __pycache__
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -f  coverage.xml .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
