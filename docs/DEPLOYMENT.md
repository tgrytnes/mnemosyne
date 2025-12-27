# Mnemosyne Deployment Strategy

Multi-environment setup: Development → Testing → Production (Docker on Raspberry Pi)

## 🏗️ Environment Overview

| Environment | Location | Purpose | Data | Services |
|-------------|----------|---------|------|----------|
| **Development** | Local laptop/desktop | Active coding, debugging | Test data (50 files) | Local Docker or system services |
| **Testing** | Local or CI/CD | Integration tests, validation | Test data | Docker Compose |
| **Production** | Raspberry Pi 5 | Live system, real vault | Full vault (512 files) | Docker Compose |

---

## 📁 Environment Configuration

### Strategy: Environment-Specific `.env` Files

```
.env.development    # Development settings (test data, debug mode)
.env.testing        # Testing settings (CI/CD, test data)
.env.production     # Production settings (full data, optimized)
.env                # Active environment (symlink or copy)
```

### Usage

```bash
# Development
cp .env.development .env
python -m Aletheia.ingestor

# Testing
cp .env.testing .env
pytest tests/integration -v

# Production (on Raspberry Pi)
cp .env.production .env
docker-compose up -d
```

---

## 🔧 Environment Files

### `.env.development` (Local Development)

```bash
# Environment
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# Ollama (local or Pi)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=qwen3-embedding:0.6b
OLLAMA_LLM_MODEL=qwen3:0.6b

# Weaviate (local Docker)
WEAVIATE_HTTP_HOST=localhost
WEAVIATE_HTTP_PORT=8081
WEAVIATE_GRPC_PORT=50051

# PostgreSQL (local Docker)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=mnemosyne_dev
POSTGRES_USER=postgres
POSTGRES_PASSWORD=devpassword

# Redis (local Docker)
REDIS_HOST=localhost
REDIS_PORT=6379

# Test Data (fast iteration)
VAULT_PATH=test_data/test_vault
EMAIL_ARCHIVE_PATH=test_data/test_emails
PDF_SCAN_PATH=test_data/test_pdfs
EMAIL_TSV=test_data/cleaned_emails_sample.tsv

# Collection Names
WEAVIATE_COLLECTION_MUSES=TheMuses_Dev
WEAVIATE_COLLECTION_LETHE=TheLethe_Dev
WEAVIATE_COLLECTION_DISCOVERY=DiscoveryDB_Dev

# Development Settings
CHUNK_SIZE=400
CHUNK_OVERLAP=100
WATCHER_INTERVAL=10  # Fast polling for dev
EMBEDDING_BATCH_SIZE=5  # Small batches for debugging

# Telegram (optional in dev)
TELEGRAM_BOT_TOKEN=
TELEGRAM_USER_ID=
```

### `.env.testing` (CI/CD & Integration Tests)

```bash
# Environment
ENVIRONMENT=testing
LOG_LEVEL=INFO

# Services (Docker Compose in CI)
OLLAMA_BASE_URL=http://ollama:11434
WEAVIATE_HTTP_HOST=weaviate
WEAVIATE_HTTP_PORT=8080
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=mnemosyne_test
POSTGRES_USER=test_user
POSTGRES_PASSWORD=test_password
REDIS_HOST=redis
REDIS_PORT=6379

# Test Data
VAULT_PATH=/app/test_data/test_vault
EMAIL_TSV=/app/test_data/cleaned_emails_sample.tsv

# Collection Names (isolated)
WEAVIATE_COLLECTION_MUSES=TheMuses_Test
WEAVIATE_COLLECTION_LETHE=TheLethe_Test
WEAVIATE_COLLECTION_DISCOVERY=DiscoveryDB_Test

# Testing Settings
CHUNK_SIZE=400
CHUNK_OVERLAP=100
WATCHER_INTERVAL=60
EMBEDDING_BATCH_SIZE=10
```

### `.env.production` (Raspberry Pi)

```bash
# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO

# Services (all in Docker network)
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_EMBEDDING_MODEL=qwen3-embedding:0.6b
OLLAMA_LLM_MODEL=qwen3:0.6b

WEAVIATE_HTTP_HOST=weaviate
WEAVIATE_HTTP_PORT=8080
WEAVIATE_GRPC_PORT=50051

POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=mnemosyne
POSTGRES_USER=mnemosyne_user
POSTGRES_PASSWORD=<strong_password_here>

REDIS_HOST=redis
REDIS_PORT=6379

# Production Data (mounted volumes)
VAULT_PATH=/data/vault
EMAIL_ARCHIVE_PATH=/data/email_archive
PDF_SCAN_PATH=/data/pdf_scans
EMAIL_TSV=/data/cleaned_emails_full.tsv

# Collection Names (production)
WEAVIATE_COLLECTION_MUSES=TheMuses
WEAVIATE_COLLECTION_LETHE=TheLethe
WEAVIATE_COLLECTION_DISCOVERY=DiscoveryDB

# Production Settings
CHUNK_SIZE=400
CHUNK_OVERLAP=100
WATCHER_INTERVAL=300  # 5 minutes
EMBEDDING_BATCH_SIZE=20  # Larger batches
SCOUT_RUN_INTERVAL=24  # Hours

# Telegram (production bot)
TELEGRAM_BOT_TOKEN=<your_production_bot_token>
TELEGRAM_USER_ID=<your_telegram_id>

# Linear (production tracking)
LINEAR_API_KEY=<your_linear_api_key>
```

---

## 🐳 Docker Setup

### Development: `docker-compose.dev.yml`

For local development with services only (no app container):

```yaml
version: '3.8'

services:
  weaviate:
    image: semitechnologies/weaviate:1.27.0
    ports:
      - "8081:8080"
      - "50051:50051"
    environment:
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
      PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
      DEFAULT_VECTORIZER_MODULE: 'none'
      ENABLE_MODULES: ''
    volumes:
      - weaviate_dev_data:/var/lib/weaviate

  postgres:
    image: postgres:15
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: mnemosyne_dev
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: devpassword
    volumes:
      - postgres_dev_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_dev_data:/data

  # Ollama already running on host:11434

volumes:
  weaviate_dev_data:
  postgres_dev_data:
  redis_dev_data:
```

**Usage**:
```bash
# Start dev services
docker-compose -f docker-compose.dev.yml up -d

# Run app locally
python -m Aletheia.ingestor
```

### Testing: `docker-compose.test.yml`

For CI/CD and integration tests:

```yaml
version: '3.8'

services:
  weaviate:
    image: semitechnologies/weaviate:1.27.0
    environment:
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
      PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
      DEFAULT_VECTORIZER_MODULE: 'none'

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: mnemosyne_test
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_password

  redis:
    image: redis:7-alpine

  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_test_data:/root/.ollama

  mnemosyne:
    build:
      context: .
      dockerfile: Dockerfile
    depends_on:
      - weaviate
      - postgres
      - redis
      - ollama
    environment:
      - ENVIRONMENT=testing
    volumes:
      - ./test_data:/app/test_data

volumes:
  ollama_test_data:
```

**Usage**:
```bash
# Run tests in Docker
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

### Production: `docker-compose.yml` (Raspberry Pi)

Full production stack:

```yaml
version: '3.8'

services:
  # Layer 1: Aletheia (Ingestor)
  aletheia:
    image: mnemosyne:latest
    container_name: mnemosyne_aletheia
    restart: unless-stopped
    depends_on:
      - weaviate
      - postgres
      - ollama
    env_file:
      - .env.production
    volumes:
      - /mnt/sda1/digital_vault/02_active/notes/Obsidian:/data/vault:ro
      - /mnt/sda1/digital_vault/raw_email_archive:/data/email_archive:ro
      - /mnt/sda1/digital_vault/01_inbox/scans:/data/pdf_scans:ro
      - /mnt/sda1/digital_vault/cleaned_emails_full.tsv:/data/cleaned_emails_full.tsv:ro
      - ingestion_state:/app/state
    command: python -m Aletheia.ingestor
    networks:
      - mnemosyne_net

  # Layer 3: Argus (Scout)
  argus:
    image: mnemosyne:latest
    container_name: mnemosyne_argus
    restart: unless-stopped
    depends_on:
      - weaviate
      - postgres
    env_file:
      - .env.production
    command: python -m Argus.scout
    networks:
      - mnemosyne_net

  # Layer 5: Hermes (Telegram Bot)
  hermes:
    image: mnemosyne:latest
    container_name: mnemosyne_hermes
    restart: unless-stopped
    depends_on:
      - postgres
    env_file:
      - .env.production
    command: python -m Hermes.telegram_bot
    networks:
      - mnemosyne_net

  # Weaviate (Vector DB)
  weaviate:
    image: semitechnologies/weaviate:1.27.0
    container_name: mnemosyne_weaviate
    restart: unless-stopped
    ports:
      - "8081:8080"
      - "50051:50051"
    environment:
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
      PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
      DEFAULT_VECTORIZER_MODULE: 'none'
      ENABLE_MODULES: ''
      QUERY_DEFAULTS_LIMIT: 25
    volumes:
      - weaviate_data:/var/lib/weaviate
    networks:
      - mnemosyne_net

  # PostgreSQL (The Ananke)
  postgres:
    image: postgres:15
    container_name: mnemosyne_postgres
    restart: unless-stopped
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: mnemosyne
      POSTGRES_USER: mnemosyne_user
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
    secrets:
      - postgres_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init_db.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - mnemosyne_net

  # Redis (Caching)
  redis:
    image: redis:7-alpine
    container_name: mnemosyne_redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - mnemosyne_net

  # Ollama (already running on host, or add container)
  # ollama:
  #   Use existing host:11434 via network_mode: host
  #   Or run in container with GPU passthrough

networks:
  mnemosyne_net:
    driver: bridge

volumes:
  weaviate_data:
  postgres_data:
  redis_data:
  ingestion_state:

secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
```

---

## 🚀 Deployment Workflow

### 1. Development (Local)

```bash
# Setup
cp .env.development .env
docker-compose -f docker-compose.dev.yml up -d

# Develop
python -m Aletheia.ingestor --vault test_data/test_vault

# Test
make test
make test-integration

# Iterate
# Edit code → Run tests → Repeat
```

### 2. Testing (CI/CD)

```bash
# In GitHub Actions or locally
cp .env.testing .env
docker-compose -f docker-compose.test.yml up --abort-on-container-exit

# Or with Make
make ci
```

### 3. Production Deployment (Raspberry Pi)

```bash
# On Raspberry Pi
cd /home/tgrytnes/projects/Mnemosyne

# Build image
docker build -t mnemosyne:latest .

# Copy production config
cp .env.production .env

# Start services
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f aletheia

# Monitor
docker stats
```

---

## 📦 Dockerfile

Create a production-ready Dockerfile:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml poetry.lock ./

# Install Python dependencies
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi

# Copy application
COPY Aletheia/ ./Aletheia/
COPY Alexandria/ ./Alexandria/
COPY Argus/ ./Argus/
COPY Iris/ ./Iris/
COPY Hermes/ ./Hermes/
COPY Prometheus/ ./Prometheus/

# Create state directory
RUN mkdir -p /app/state

# Run as non-root
RUN useradd -m -u 1000 mnemosyne && \
    chown -R mnemosyne:mnemosyne /app
USER mnemosyne

# Default command (override in docker-compose)
CMD ["python", "-m", "Aletheia.ingestor"]
```

---

## 🔄 Data Flow Between Environments

### Development → Testing
```bash
# Export test data
./setup_test_data.sh

# Commit test data structure (not files)
git add test_data/.gitkeep
git commit -m "Add test data structure"
```

### Testing → Production
```bash
# On dev machine: Build and push
docker build -t mnemosyne:v1.0.0 .
docker save mnemosyne:v1.0.0 | gzip > mnemosyne-v1.0.0.tar.gz

# Copy to Raspberry Pi
scp mnemosyne-v1.0.0.tar.gz pi@raspberrypi:/home/tgrytnes/

# On Raspberry Pi: Load and deploy
ssh pi@raspberrypi
docker load < mnemosyne-v1.0.0.tar.gz
docker tag mnemosyne:v1.0.0 mnemosyne:latest
docker-compose up -d
```

---

## 🎯 Environment Selection

### Automatic (Recommended)

```python
# In your Python code
import os
from pathlib import Path
from dotenv import load_dotenv

# Auto-detect environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Load appropriate .env file
env_file = Path(f".env.{ENVIRONMENT}")
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv()  # Fall back to .env

# Use environment-specific settings
if ENVIRONMENT == "production":
    LOG_LEVEL = "INFO"
    ENABLE_MONITORING = True
elif ENVIRONMENT == "development":
    LOG_LEVEL = "DEBUG"
    ENABLE_MONITORING = False
```

### Manual Switch

```bash
# Makefile target
make env-dev     # cp .env.development .env
make env-test    # cp .env.testing .env
make env-prod    # cp .env.production .env
```

---

## 📊 Environment Comparison

| Feature | Development | Testing | Production |
|---------|------------|---------|------------|
| **Data Size** | 50 files | 50 files | 512 files |
| **Services** | Local Docker | Docker Compose | Docker Compose |
| **Log Level** | DEBUG | INFO | INFO |
| **Watcher Interval** | 10s | 60s | 300s (5min) |
| **Batch Size** | 5 | 10 | 20 |
| **Collections** | *_Dev | *_Test | Production |
| **Monitoring** | No | No | Yes (Prometheus) |
| **Backups** | No | No | Yes (daily) |
| **Auto-restart** | No | No | Yes |

---

## 🔒 Secrets Management

### Development
```bash
# .env.development (committed to git with dummy values)
POSTGRES_PASSWORD=devpassword
```

### Production
```bash
# Use Docker secrets (NOT in .env file)
echo "strong_password_here" > secrets/postgres_password.txt
chmod 600 secrets/postgres_password.txt

# Add to .gitignore
echo "secrets/" >> .gitignore
```

---

## 📝 Next Steps

1. **Create environment files**:
   ```bash
   cp .env.example .env.development
   cp .env.example .env.testing
   cp .env.example .env.production
   # Edit each with appropriate values
   ```

2. **Add to Makefile**:
   ```makefile
   env-dev:
       cp .env.development .env

   env-test:
       cp .env.testing .env

   env-prod:
       cp .env.production .env
   ```

3. **Update .gitignore**:
   ```
   .env
   .env.local
   secrets/
   ```

4. **Test locally**:
   ```bash
   make env-dev
   docker-compose -f docker-compose.dev.yml up -d
   python -m Aletheia.ingestor
   ```

5. **Deploy to Pi**:
   ```bash
   # Build, transfer, deploy (see above)
   ```

---

**🎯 Summary**:
- Development = Local with test data
- Testing = Docker with test data
- Production = Docker on Pi with full data
- Use environment-specific `.env` files
- Docker Compose orchestrates all services on Pi
