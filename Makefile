PYTHON := python
PIP := pip

ARG1 := $(word 2,$(MAKECMDGOALS))
ARG2 := $(word 3,$(MAKECMDGOALS))
FORMAT ?= flac

.PHONY: help install install-dev clean tree version keygen encode decode

help:
	@echo "Usage:"
	@echo "  make keygen"
	@echo "  make encode file.pdf"
	@echo "  make decode file.flac"
	@echo "  make decode file.flac output.pdf"

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"

version:
	$(PYTHON) -m cypher.main --version

keygen:
	$(PYTHON) -m cypher.main keygen \
		--private-key .keys/cypher_private.pem \
		--public-key .keys/cypher_public.pem

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

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

tree:
	find . \
		-path "./.git" -prune -o \
		-path "./.venv" -prune -o \
		-path "./.keys" -prune -o \
		-print

%:
	@:
