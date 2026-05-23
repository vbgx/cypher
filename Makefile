PYTHON := python
PIP := pip

INPUT_DIR := data/input
AUDIO_DIR := data/audio
OUTPUT_DIR := data/output

CMD := $(firstword $(MAKECMDGOALS))
ARG1 := $(word 2,$(MAKECMDGOALS))
ARG2 := $(word 3,$(MAKECMDGOALS))

ENCODE_STEM := $(basename $(ARG1))
DECODE_STEM := $(basename $(ARG2))

.PHONY: help install install-dev test lint format typecheck check clean tree encode decode

help:
	@echo "Usage:"
	@echo "  make encode image.jpg"
	@echo "  make encode image.png"
	@echo "  make decode image.flac restored.jpg"
	@echo "  make decode image.wav restored.png"
	@echo ""
	@echo "Encode:"
	@echo "  data/input/image.jpg -> data/audio/image.flac"
	@echo ""
	@echo "Decode:"
	@echo "  data/audio/image.flac -> data/output/restored.jpg"

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
	@if [ -z "$(ARG1)" ]; then \
		echo "Usage: make encode image.jpg"; \
		exit 1; \
	fi
	cypher encode "$(ARG1)" --format flac

decode:
	@if [ -z "$(ARG1)" ] || [ -z "$(ARG2)" ]; then \
		echo "Usage: make decode image.flac restored.jpg"; \
		exit 1; \
	fi
	cypher decode "$(ARG1)"
	@if [ "$(DECODE_STEM)" != "" ]; then \
		mv "$(OUTPUT_DIR)/$(basename $(ARG1)).png" "$(OUTPUT_DIR)/$(ARG2)"; \
	fi

%:
	@:
