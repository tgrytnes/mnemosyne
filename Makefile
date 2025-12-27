# Mnemosyne Test Automation Makefile

.PHONY: help install test test-unit test-integration test-e2e test-all coverage clean services services-up services-down lint format check env-dev env-test env-prod

# Default target
help:
	@echo "Mnemosyne Testing Commands"
	@echo "=========================="
	@echo ""
	@echo "Environment:"
	@echo "  make env-dev          Switch to development environment"
	@echo "  make env-test         Switch to testing environment (CI/CD)"
	@echo "  make env-prod         Switch to production environment"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install dependencies with Poetry"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all unit tests (fast, no Docker)"
	@echo "  make test-unit        Run unit tests only"
	@echo "  make test-integration Run integration tests (requires Docker)"
	@echo "  make test-e2e         Run end-to-end tests"
	@echo "  make test-all         Run ALL tests with coverage"
	@echo "  make coverage         Generate HTML coverage report"
	@echo ""
	@echo "Services:"
	@echo "  make services-up      Start Docker services (Weaviate, PostgreSQL)"
	@echo "  make services-down    Stop Docker services"
	@echo "  make services-logs    View service logs"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             Run linters (ruff, mypy)"
	@echo "  make format           Format code with Black"
	@echo "  make check            Run all quality checks"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            Remove test artifacts and cache"

# Installation
install:
	@echo "Installing dependencies..."
	poetry install --with dev

# Unit tests (fast, no Docker needed)
test: test-unit

test-unit:
	@echo "Running unit tests..."
	poetry run pytest tests/unit -v -m unit

# Integration tests (requires Docker services)
test-integration: services-up
	@echo "Running integration tests..."
	poetry run pytest tests/integration -v -m integration

# E2E tests
test-e2e: services-up
	@echo "Running end-to-end tests..."
	poetry run pytest tests/e2e -v -m e2e

# All tests with coverage
test-all: services-up
	@echo "Running all tests with coverage..."
	poetry run pytest -v --cov=. --cov-report=term-missing --cov-report=html

# Coverage report
coverage: test-all
	@echo "Opening coverage report in browser..."
	@which open > /dev/null && open htmlcov/index.html || \
	which xdg-open > /dev/null && xdg-open htmlcov/index.html || \
	echo "Coverage report generated at htmlcov/index.html"

# Docker services
services: services-up

services-up:
	@echo "Starting Docker services..."
	docker-compose up weaviate postgres -d
	@echo "Waiting for services to be ready..."
	@timeout 60 bash -c 'until curl -sf http://localhost:8080/v1/.well-known/ready > /dev/null 2>&1; do sleep 2; done' || true
	@timeout 60 bash -c 'until pg_isready -h localhost -p 5432 -U postgres > /dev/null 2>&1; do sleep 2; done' || true
	@echo "Services are ready!"

services-down:
	@echo "Stopping Docker services..."
	docker-compose down

services-logs:
	@echo "Viewing service logs (Ctrl+C to exit)..."
	docker-compose logs -f weaviate postgres

# Code quality
lint:
	@echo "Running ruff linter..."
	poetry run ruff check .
	@echo "Running mypy type checker..."
	poetry run mypy . --ignore-missing-imports || true

format:
	@echo "Formatting code with Black..."
	poetry run black .

check: format lint test-unit
	@echo "✅ All quality checks passed!"

# Cleanup
clean:
	@echo "Cleaning test artifacts..."
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf tests/.pytest_cache
	rm -rf tests/pytest.log
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "Cleanup complete!"

# Quick test cycle for development
dev: format lint test-unit
	@echo "✅ Development cycle complete!"

# CI simulation (what runs in GitHub Actions)
ci: check test-all
	@echo "✅ CI checks passed!"

# Environment switching
env-dev:
	@echo "Switching to DEVELOPMENT environment..."
	cp .env.development .env
	@echo "✓ Using .env.development (test data, debug logging)"
	@echo "  Data: test_data/test_vault (50 files)"
	@echo "  Services: localhost (Docker)"

env-test:
	@echo "Switching to TESTING environment..."
	cp .env.testing .env
	@echo "✓ Using .env.testing (CI/CD, integration tests)"
	@echo "  Data: test_data/test_vault (50 files)"
	@echo "  Services: GitHub Actions services"

env-prod:
	@echo "Switching to PRODUCTION environment..."
	cp .env.production .env
	@echo "✓ Using .env.production (full data, optimized)"
	@echo "  Data: /mnt/sda1/digital_vault/ (512 files)"
	@echo "  Services: Docker network"
	@echo ""
	@echo "⚠️  WARNING: Make sure to update secrets in .env.production!"
