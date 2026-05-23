PYTHON := python
PIP := pip

SRC := src
TESTS := tests

.PHONY: help install install-dev test lint format typecheck check clean tree encode-demo decode-demo

help:
	@echo "Available commands:"
	@echo "  make install       Install package"
	@echo "  make install-dev   Install package with dev dependencies"
	@echo "  make test          Run tests"
	@echo "  make lint          Run ruff lint"
	@echo "  make format        Run ruff format"
	@echo "  make typecheck     Run mypy"
	@echo "  make check         Run lint + typecheck + tests"
	@echo "  make clean         Remove cache/build files"
	@echo "  make tree          Show project tree"
	@echo "  make encode-demo   Encode data/input/example.png"
	@echo "  make decode-demo   Decode data/audio/example.wav"

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
	mypy $(SRC)

check: lint typecheck test

clean:
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf build
	rm -rf dist
	rm -rf *.egg-info
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

tree:
	find . \
		-path "./.git" -prune -o \
		-path "./.venv" -prune -o \
		-path "./__pycache__" -prune -o \
		-print

encode-demo:
	cypher encode data/input/example.png data/audio/example.wav

decode-demo:
	cypher decode data/audio/example.wav data/output/restored.png \
		--width 100 \
		--height 100
