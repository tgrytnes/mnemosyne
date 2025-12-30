# Integration Testing Guide

Guide for running integration tests for Mnemosyne components.

---

## Story 000: Obsidian Vault Ingestion

### Prerequisites

1. **Docker & Docker Compose** installed
2. **Python virtual environment** activated
3. **Sufficient disk space** (~2GB for Ollama model)

### Quick Start

Run the automated test script:

```bash
./scripts/run_integration_tests.sh
```

This script will:
1. ✅ Start Weaviate and Ollama containers
2. ✅ Pull qwen3-embedding:0.6b model (~600MB)
3. ✅ Run 13 integration tests
4. ✅ Clean up containers

### Manual Testing

If you prefer to run tests manually:

```bash
# 1. Start services
docker-compose -f docker-compose.test.yml up -d

# 2. Wait for services to be ready
curl http://localhost:8080/v1/.well-known/ready  # Weaviate
curl http://localhost:11434/                     # Ollama

# 3. Pull embedding model
docker exec mnemosyne_test_ollama ollama pull qwen3-embedding:0.6b

# 4. Run tests
source .venv/bin/activate
pytest tests/integration/test_obsidian_ingestion_integration.py -v -m integration

# 5. Cleanup
docker-compose -f docker-compose.test.yml down -v
```

---

## Integration Tests Overview

### What's Tested

**13 Integration Tests covering:**

1. **Service Connectivity**
   - Weaviate connection
   - Ollama connection
   - Embedding model availability

2. **Pipeline Components**
   - Weaviate collection creation
   - Single file ingestion
   - Complete vault ingestion

3. **Data Storage**
   - Chunks stored in Weaviate
   - Embeddings generated (1024 dimensions)
   - Metadata completeness

4. **Functionality**
   - Semantic search works
   - Markdown cleaning applied
   - Incremental ingestion
   - State persistence

### Test Markers

```bash
# Run only integration tests
pytest -m integration

# Run only unit tests
pytest -m "not integration"

# Run all tests
pytest
```

---

## Troubleshooting

### Weaviate won't start

```bash
# Check if port 8080 is already in use
sudo lsof -i :8080

# Check Docker logs
docker logs mnemosyne_test_weaviate
```

### Ollama model download fails

```bash
# Pull model manually
docker exec -it mnemosyne_test_ollama bash
ollama pull qwen3-embedding:0.6b
```

### Tests fail with connection errors

```bash
# Verify services are healthy
docker-compose -f docker-compose.test.yml ps

# Restart services
docker-compose -f docker-compose.test.yml restart
```

### Cleanup stuck containers

```bash
# Force remove containers
docker-compose -f docker-compose.test.yml down -v --remove-orphans

# Or manually
docker stop mnemosyne_test_weaviate mnemosyne_test_ollama
docker rm mnemosyne_test_weaviate mnemosyne_test_ollama
```

---

## Performance Expectations

### First Run (Cold Start)

- **Ollama model download**: ~2-5 minutes (600MB)
- **Test execution**: ~30-60 seconds
- **Total time**: ~3-7 minutes

### Subsequent Runs (Warm Start)

- **Service startup**: ~10 seconds
- **Test execution**: ~30-60 seconds
- **Total time**: ~1 minute

---

## Test Data

Integration tests use temporary test vaults:

- **3 test markdown files**
- **~10-15 chunks** total
- **~1,500 characters** of content
- **Temporary directories** (auto-cleaned)

No real vault data is used.

---

## CI/CD Integration

### GitHub Actions

Add to `.github/workflows/integration.yml`:

```yaml
name: Integration Tests

on:
  push:
    branches: [develop, staging, main]
  pull_request:
    branches: [develop]

jobs:
  integration-tests:
    runs-on: ubuntu-latest

    services:
      weaviate:
        image: cr.weaviate.io/semitechnologies/weaviate:latest
        ports:
          - 8080:8080
        env:
          AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
          PERSISTENCE_DATA_PATH: '/tmp/weaviate'

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-mock

      - name: Start Ollama
        run: |
          docker run -d -p 11434:11434 --name ollama ollama/ollama
          docker exec ollama ollama pull qwen3-embedding:0.6b

      - name: Run integration tests
        env:
          WEAVIATE_HTTP_HOST: localhost
          WEAVIATE_HTTP_PORT: 8080
          OLLAMA_BASE_URL: http://localhost:11434
        run: |
          pytest tests/integration/ -v -m integration
```

---

## Next Steps

After integration tests pass:

1. **Deploy to Staging** - Raspberry Pi staging environment
2. **Real Vault Testing** - Test with actual Obsidian vault
3. **Performance Profiling** - Measure ingestion speed
4. **Story 024** - Email archive ingestion

---

**Last Updated**: 2025-12-27
