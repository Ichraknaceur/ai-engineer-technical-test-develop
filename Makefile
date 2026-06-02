.DEFAULT_GOAL := help

UV_CACHE_DIR ?= .uv-cache
export UV_CACHE_DIR

ifeq ($(OS),Windows_NT)
UV_COMMAND := $(shell where uv 2>NUL)
COPY_ENV_COMMAND = if not exist .env copy .env.example .env
else
UV_COMMAND := $(shell command -v uv 2> /dev/null)
COPY_ENV_COMMAND = cp .env.example .env || true
endif

RUFF_TARGETS := backend tests pyproject.toml

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Display this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Guards ────────────────────────────────────────────────────────────────────

.PHONY: check-uv
check-uv: ## Check if uv is installed
ifndef UV_COMMAND
	$(error "uv is not installed. Please visit https://docs.astral.sh/uv for installation instructions.")
endif

.PHONY: check-docker
check-docker: ## Check that Docker and Docker Compose are available
	@command -v docker >/dev/null 2>&1 || { echo "docker not found"; exit 1; }
	@docker compose version >/dev/null 2>&1 || { echo "docker compose not found"; exit 1; }

# ── Setup ─────────────────────────────────────────────────────────────────────

.PHONY: install
install: check-uv pyproject.toml ## Synchronize dependencies
	uv sync

.PHONY: init
init: check-uv pyproject.toml .pre-commit-config.yaml install ## Initialize project (first installation)
	uv run -- pre-commit install
	$(COPY_ENV_COMMAND)

.PHONY: bootstrap
bootstrap: check-docker init ## Full first-time setup (Docker + DB migrations)
	docker compose build
	docker compose run --rm backend alembic upgrade head
	@echo "Ready. Run: docker compose up"

.PHONY: all
all: check-uv install format lint check ## Run format, lint, and all checks

# ── Run ───────────────────────────────────────────────────────────────────────

.PHONY: run
run: check-uv install ## Run the local API server (no Docker)
	uv run -- uvicorn backend.infrastructure.api.main:app --host 127.0.0.1 --port 8000 --reload

.PHONY: up
up: check-docker ## Start all services via Docker Compose
	docker compose up

.PHONY: down
down: check-docker ## Stop all services
	docker compose down

.PHONY: extract
extract: check-docker ## Run an extraction  (LAT=... LON=... RADIUS_KM=...)
	@[ -n "$(LAT)" ] && [ -n "$(LON)" ] && [ -n "$(RADIUS_KM)" ] || { echo "Usage: make extract LAT=... LON=... RADIUS_KM=..."; exit 1; }
	@curl -s -X POST http://localhost:8000/api/jobs -H "Content-Type: application/json" \
		-d '{"latitude": $(LAT), "longitude": $(LON), "radius_km": $(RADIUS_KM)}' | python3 -m json.tool

# ── Code quality ──────────────────────────────────────────────────────────────

.PHONY: format
format: check-uv ## Format code with ruff
	uv run -- ruff format $(RUFF_TARGETS)
	uv run -- ruff check --fix $(RUFF_TARGETS)

.PHONY: lint
lint: check-uv ## Run linting checks (ruff)
	uv run -- ruff check $(RUFF_TARGETS)

.PHONY: typecheck
typecheck: check-uv ## Run type checking with ty (pure layers only)
	uv run -- ty check backend/domain backend/ports backend/application

.PHONY: precommit
precommit: check-uv install ## Run pre-commit hooks on all files
	uv run -- pre-commit run --all-files

.PHONY: check
check: check-uv install ## Run all checks (precommit + tests)
	$(MAKE) precommit
	$(MAKE) test

# ── Tests ─────────────────────────────────────────────────────────────────────

.PHONY: test
test: check-uv ## Run full test suite with coverage
	uv run -- pytest

.PHONY: test-unit
test-unit: check-uv ## Run unit tests only
	uv run -- pytest tests/unit/ -v

.PHONY: diff-cover
diff-cover: check-uv test coverage.xml ## Show coverage diff against main branch
	uv run -- diff-cover coverage.xml

.PHONY: eval
eval: check-uv install ## Run evaluation against ground truth
	uv run -- python tests/eval/score.py

# ── Documentation ─────────────────────────────────────────────────────────────

.PHONY: docs
docs: check-uv install ## Build documentation (output → site/)
	uv run -- mkdocs build

.PHONY: docs-serve
docs-serve: check-uv install ## Serve documentation locally at http://localhost:8090
	uv run -- mkdocs serve --dev-addr 0.0.0.0:8090

.PHONY: docs-deploy
docs-deploy: check-uv install ## Deploy documentation to GitHub Pages
	uv run -- mkdocs gh-deploy

# ── Build ─────────────────────────────────────────────────────────────────────

.PHONY: build
build: check-uv install ## Build the Python package
	uv build

# ── Utilities ─────────────────────────────────────────────────────────────────

.PHONY: gitignore
gitignore: ## Regenerate .gitignore for Python/macOS/Linux/VSCode
	curl -L https://www.gitignore.io/api/windows,macos,linux,git,pycharm,visualstudiocode,python > .gitignore

.PHONY: clean
clean: ## Remove temporary files and build artifacts
	rm -rf .pytest_cache/ .coverage coverage.xml htmlcov/ .ruff_cache/ site/ dist/ build/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
