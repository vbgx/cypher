PYTHON := python
PIP := pip

ARG1 := $(word 2,$(MAKECMDGOALS))
ARG2 := $(word 3,$(MAKECMDGOALS))
FORMAT ?= flac

.PHONY: help install install-dev clean tree version keygen keygen-force encode bundle decode inspect gui

help:
	@echo "Usage:"
	@echo "  make keygen"
	@echo "  make keygen-force"
	@echo "  make encode file.pdf"
	@echo "  make bundle file1 file2 folder/"
	@echo "  make decode file.flac"
	@echo "  make decode file.flac output_name_or_dir"
	@echo "  make inspect file.flac"
	@echo "  make gui"

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

bundle:
	@if [ -z "$(ARG1)" ]; then \
		echo "Usage: make bundle file1 file2 folder/"; \
		exit 1; \
	fi
	$(PYTHON) -m cypher.main bundle $(filter-out $@,$(MAKECMDGOALS)) --format "$(FORMAT)"

decode:
	@if [ -z "$(ARG1)" ]; then \
		echo "Usage: make decode file.flac [output_name_or_dir]"; \
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

gui:
	$(PYTHON) -m cypher.gui

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