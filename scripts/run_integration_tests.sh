#!/bin/bash
# Run integration tests for Story 000
# Starts Docker services, pulls Ollama model, runs tests, cleans up

set -e  # Exit on error

echo "🚀 Starting Integration Test Suite for Story 000"
echo "================================================"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Start Docker services
echo -e "\n${YELLOW}Step 1: Starting Docker services (Weaviate + Ollama)${NC}"
docker-compose -f docker-compose.test.yml up -d

# Step 2: Wait for services to be healthy
echo -e "\n${YELLOW}Step 2: Waiting for services to be ready...${NC}"
echo "Waiting for Weaviate..."
timeout 60 bash -c 'until curl -sf http://localhost:8080/v1/.well-known/ready > /dev/null; do sleep 2; done' || {
    echo -e "${RED}❌ Weaviate failed to start${NC}"
    exit 1
}
echo -e "${GREEN}✓ Weaviate is ready${NC}"

echo "Waiting for Ollama..."
timeout 60 bash -c 'until curl -sf http://localhost:11434/ > /dev/null; do sleep 2; done' || {
    echo -e "${RED}❌ Ollama failed to start${NC}"
    exit 1
}
echo -e "${GREEN}✓ Ollama is ready${NC}"

# Step 3: Pull Ollama embedding model
echo -e "\n${YELLOW}Step 3: Pulling Ollama embedding model (qwen3-embedding:0.6b)${NC}"
docker exec mnemosyne_test_ollama ollama pull qwen3-embedding:0.6b || {
    echo -e "${RED}❌ Failed to pull Ollama model${NC}"
    exit 1
}
echo -e "${GREEN}✓ Model pulled successfully${NC}"

# Step 4: Run integration tests
echo -e "\n${YELLOW}Step 4: Running integration tests${NC}"
echo "================================================"

# Activate virtual environment and run tests
source .venv/bin/activate
python -m pytest tests/integration/test_obsidian_ingestion_integration.py -v -m integration || {
    TEST_EXIT_CODE=$?
    echo -e "\n${RED}❌ Integration tests failed${NC}"

    # Cleanup on failure
    echo -e "\n${YELLOW}Cleaning up Docker services...${NC}"
    docker-compose -f docker-compose.test.yml down -v

    exit $TEST_EXIT_CODE
}

# Step 5: Cleanup
echo -e "\n${YELLOW}Step 5: Cleaning up Docker services${NC}"
docker-compose -f docker-compose.test.yml down -v

echo -e "\n${GREEN}================================================${NC}"
echo -e "${GREEN}✅ Integration tests completed successfully!${NC}"
echo -e "${GREEN}================================================${NC}"
