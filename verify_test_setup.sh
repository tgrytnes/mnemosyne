#!/bin/bash
# Verify test infrastructure setup for Mnemosyne

set -e

echo "🔍 Verifying Mnemosyne Test Infrastructure Setup"
echo "================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $1"
        return 0
    else
        echo -e "${RED}✗${NC} $1 (missing)"
        return 1
    fi
}

check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} $1/"
        return 0
    else
        echo -e "${RED}✗${NC} $1/ (missing)"
        return 1
    fi
}

echo "Configuration Files:"
check_file "pyproject.toml"
check_file "pytest.ini"
check_file "Makefile"
check_file "TESTING.md"
check_file ".github/workflows/test.yml"
echo ""

echo "Test Directories:"
check_dir "tests"
check_dir "tests/unit"
check_dir "tests/integration"
check_dir "tests/e2e"
check_dir "tests/fixtures"
echo ""

echo "Test Files:"
check_file "tests/__init__.py"
check_file "tests/conftest.py"
check_file "tests/README.md"
check_file "tests/QUICK_REFERENCE.md"
check_file "tests/SETUP_SUMMARY.md"
echo ""

echo "Unit Tests:"
check_file "tests/unit/__init__.py"
check_file "tests/unit/test_ingestor.py"
check_file "tests/unit/test_gatekeeper.py"
check_file "tests/unit/test_scout.py"
check_file "tests/unit/test_project_manager.py"
echo ""

echo "Integration Tests:"
check_file "tests/integration/__init__.py"
check_file "tests/integration/test_weaviate_integration.py"
check_file "tests/integration/test_postgres_integration.py"
echo ""

# Check if Poetry is installed
echo "Dependencies:"
if command -v poetry &> /dev/null; then
    echo -e "${GREEN}✓${NC} Poetry installed"

    # Check if dependencies are installed
    if poetry show pytest &> /dev/null; then
        echo -e "${GREEN}✓${NC} pytest installed"
    else
        echo -e "${YELLOW}⚠${NC} pytest not installed (run: poetry install --with dev)"
    fi
else
    echo -e "${YELLOW}⚠${NC} Poetry not installed (install from: https://python-poetry.org/docs/#installation)"
fi
echo ""

# Check Docker services
echo "Docker Services (optional for integration tests):"
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓${NC} Docker installed"

    # Check if docker-compose is available
    if command -v docker-compose &> /dev/null || docker compose version &> /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} docker-compose available"

        # Check if services are running
        if docker ps | grep -q weaviate; then
            echo -e "${GREEN}✓${NC} Weaviate running"
        else
            echo -e "${YELLOW}⚠${NC} Weaviate not running (start: make services-up)"
        fi

        if docker ps | grep -q postgres; then
            echo -e "${GREEN}✓${NC} PostgreSQL running"
        else
            echo -e "${YELLOW}⚠${NC} PostgreSQL not running (start: make services-up)"
        fi
    else
        echo -e "${YELLOW}⚠${NC} docker-compose not found"
    fi
else
    echo -e "${YELLOW}⚠${NC} Docker not installed (optional for integration tests)"
fi
echo ""

# Test count
echo "Test Statistics:"
UNIT_TESTS=$(find tests/unit -name "test_*.py" | wc -l)
INTEGRATION_TESTS=$(find tests/integration -name "test_*.py" | wc -l)
TOTAL_TESTS=$((UNIT_TESTS + INTEGRATION_TESTS))

echo "  Unit test files: $UNIT_TESTS"
echo "  Integration test files: $INTEGRATION_TESTS"
echo "  Total test files: $TOTAL_TESTS"
echo ""

# Summary
echo "================================================"
echo -e "${GREEN}✓${NC} Test infrastructure setup verified!"
echo ""
echo "Next steps:"
echo "  1. Install dependencies: poetry install --with dev"
echo "  2. Run unit tests:       make test"
echo "  3. Start services:       make services-up"
echo "  4. Run all tests:        make test-all"
echo "  5. View coverage:        make coverage"
echo ""
echo "Documentation:"
echo "  - Quick start:  TESTING.md"
echo "  - Full guide:   tests/README.md"
echo "  - Quick ref:    tests/QUICK_REFERENCE.md"
echo "  - Setup info:   tests/SETUP_SUMMARY.md"
echo ""
