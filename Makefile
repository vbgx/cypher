PYTHON := python
PIP := pip

ARG1 := $(word 2,$(MAKECMDGOALS))
ARG2 := $(word 3,$(MAKECMDGOALS))
FORMAT ?= flac

.PHONY: help install install-dev clean tree version keygen keygen-force encode decode inspect

help:
	@echo "Usage:"
	@echo "  make keygen"
	@echo "  make keygen-force"
	@echo "  make encode file.pdf"
	@echo "  make decode file.flac"
	@echo "  make decode file.flac output.pdf"
	@echo "  make inspect file.flac"

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"

version:
	$(PYTHON) -m cypher.main --version

keygen:
	$(PYTHON) -m cypher.main keygen

keygen-force:
	$(PYTHON) -m cypher.main keygen --force

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

inspect:
	@if [ -z "$(ARG1)" ]; then \
		echo "Usage: make inspect file.flac"; \
		exit 1; \
	fi
	$(PYTHON) -m cypher.main inspect "$(ARG1)"

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

bundle:
	$(PYTHON) -m cypher.main bundle $(filter-out $@,$(MAKECMDGOALS))

unbundle:
	@if [ -z "$(ARG1)" ]; then \
		echo "Usage: make unbundle file.flac"; \
		exit 1; \
	fi
	$(PYTHON) -m cypher.main unbundle "$(ARG1)"

gui:
	$(PYTHON) -m cypher.gui