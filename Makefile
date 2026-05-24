PYTHON := python
PIP := pip

ARG1 := $(word 2,$(MAKECMDGOALS))
ARG2 := $(word 3,$(MAKECMDGOALS))
FORMAT ?= flac

.PHONY: help install install-dev test lint format typecheck check clean tree encode decode version

help:
	@echo "Usage:"
	@echo "  make encode file.pdf"
	@echo "  make encode image.jpg"
	@echo "  make encode archive.zip"
	@echo "  make encode file.bin FORMAT=wav"
	@echo "  make decode file.flac"
	@echo "  make decode file.flac restored.pdf"
	@echo ""
	@echo "Input files are resolved from current path or data/input/"
	@echo "Encoded audio is written to data/audio/"
	@echo "Decoded files are written to data/output/"
	@echo ""
	@echo "Supported lossless audio formats: wav, flac"
	@echo "MP3 is rejected because it is lossy."

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"

version:
	$(PYTHON) -m cypher.main --version

test:
	pytest

lint:
	ruff check src tests

format:
	ruff format src tests

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
		-path "./__pycache__" -prune -o \
		-print

encode:
	@if [ -z "$(ARG1)" ]; then \
		echo "Usage: make encode file.pdf"; \
		exit 1; \
	fi
	$(PYTHON) -m cypher.main encode "$(ARG1)" --format "$(FORMAT)"

decode:
	@if [ -z "$(ARG1)" ]; then \
		echo "Usage: make decode file.flac [output_name]"; \
		exit 1; \
	fi
	@if [ -z "$(ARG2)" ]; then \
		$(PYTHON) -m cypher.main decode "$(ARG1)"; \
	else \
		$(PYTHON) -m cypher.main decode "$(ARG1)" "$(ARG2)"; \
	fi

%:
	@:
