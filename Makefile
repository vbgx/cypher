PYTHON := python
PIP := pip

ARG1 := $(word 2,$(MAKECMDGOALS))
ARG2 := $(word 3,$(MAKECMDGOALS))
FORMAT ?= flac

.PHONY: help install install-dev clean clean-cache clean-app tree version keygen keygen-force encode bundle decode inspect benchmark gui app lint typecheck test release-check

help:
	@echo "Usage:"
	@echo "  make keygen"
	@echo "  make keygen-force"
	@echo "  make encode file.pdf"
	@echo "  make bundle file1 file2 folder/"
	@echo "  make decode file.flac"
	@echo "  make decode file.flac output_name_or_dir"
	@echo "  make inspect file.flac"
	@echo "  make benchmark file.pdf"
	@echo "  make gui"
	@echo "  make app"
	@echo "  make clean"
	@echo "  make test"
	@echo "  make release-check"

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

benchmark:
	@if [ -z "$(ARG1)" ]; then \
		echo "Usage: make benchmark file.pdf"; \
		exit 1; \
	fi
	$(PYTHON) -m cypher.main benchmark "$(ARG1)"

gui:
	$(PYTHON) -m cypher.gui

app:
	$(PYTHON) -m PyInstaller packaging/macos/cypher.spec --noconfirm --clean

clean-app:
	rm -rf build dist

clean-cache:
	rm -rf .pytest_cache .mypy_cache .ruff_cache *.egg-info
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

clean: clean-cache clean-app

lint:
	$(PYTHON) -m ruff check src tests

typecheck:
	$(PYTHON) -m mypy --ignore-missing-imports src

test:
	$(PYTHON) -m ruff check tests --fix
	QT_QPA_PLATFORM=offscreen $(PYTHON) -m pytest tests -q
	$(PYTHON) -m coverage report -m

release-check:
	$(PYTHON) -m cypher.main --version
	$(PYTHON) -m cypher.main encode --help
	$(PYTHON) -m cypher.main bundle --help
	$(PYTHON) -m cypher.main decode --help
	$(PYTHON) -m cypher.main inspect --help
	$(PYTHON) -m cypher.main benchmark README.md
	$(PYTHON) -m ruff check src tests
	QT_QPA_PLATFORM=offscreen $(PYTHON) -m pytest tests -q
	$(PYTHON) -m coverage report -m
	git status --short

tree:
	find . \
		-path "./.git" -prune -o \
		-path "./.venv" -prune -o \
		-path "./.keys" -prune -o \
		-print

%:
	@:
