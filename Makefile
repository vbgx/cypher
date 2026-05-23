PYTHON := python
PIP := pip

.PHONY: help install install-dev test lint format typecheck check clean tree encode decode decore

CMD := $(firstword $(MAKECMDGOALS))
ARG := $(word 2,$(MAKECMDGOALS))

help:
	@echo "Usage:"
	@echo "  make encode example.jpg"
	@echo "  make encode image.png"
	@echo "  make decode example.flac"
	@echo "  make decode example.wav"
	@echo ""
	@echo "Default encode output: data/audio/<name>.flac"
	@echo "Default decode output: data/output/<name>.png"

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy src

check: lint typecheck test

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

tree:
	find . \
		-path "./.git" -prune -o \
		-path "./.venv" -prune -o \
		-print

encode:
	@if [ -z "$(ARG)" ]; then \
		echo "Usage: make encode example.jpg"; \
		exit 1; \
	fi
	cypher encode "$(ARG)"

decode:
	@if [ -z "$(ARG)" ]; then \
		echo "Usage: make decode example.flac"; \
		exit 1; \
	fi
	cypher decode "$(ARG)"

decore:
	@if [ -z "$(ARG)" ]; then \
		echo "Usage: make decore example.flac"; \
		exit 1; \
	fi
	cypher decore "$(ARG)"

%:
	@:
