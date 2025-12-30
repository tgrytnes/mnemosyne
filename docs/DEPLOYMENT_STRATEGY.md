# Mnemosyne Deployment Strategy

**Date**: 2025-12-27
**Status**: Complete deployment and branching strategy

## Overview

Mnemosyne uses a **3-environment strategy** optimized for a single-developer personal project deploying to Raspberry Pi 5.

---

## 🌍 Environment Strategy

### Environment Tiers

| Environment | Purpose | Location | Data | Deployment | Runtime |
|-------------|---------|----------|------|------------|---------|
| **Development** | Active coding, debugging | Local laptop | Test data (50 files) | Manual, on-demand | On-demand |
| **Testing** | Automated CI/CD tests | GitHub Actions | Test data (50 files) | Automatic on push/PR | On-demand |
| **Staging** | Pre-production validation | Raspberry Pi 5 (Docker) | Subset of real data (100 files) | Automated on merge to `staging` branch | **Always running** |
| **Production** | Live system | Raspberry Pi 5 (Docker) | Full vault (512 files) | Manual deployment | **On-demand only** |

### Raspberry Pi Setup

**Both staging and production run on the same Raspberry Pi 5** in separate Docker containers:

- **Staging**: Always running, continuous validation
  - Ports: 8082 (Weaviate), 5433 (PostgreSQL)
  - Docker network: `mnemosyne_staging_net`
  - Auto-deploys from `staging` branch

- **Production**: Only runs when needed
  - Ports: 8081 (Weaviate), 5432 (PostgreSQL)
  - Docker network: `mnemosyne_net`
  - Manually started/stopped
  - Saves resources when not in use

---

## 📁 Environment Configurations

### 1. Development Environment

**File**: `.env.development`

**Purpose**: Fast iteration with test data

**Characteristics**:
- Test data: 50 vault files, 1000 emails
- Debug logging
- Fast polling intervals (10 seconds)
- Small embedding batches (5)
- Local Docker services
- Separate collections: `TheMuses_Dev`, `TheLethe_Dev`

**Usage**:
```bash
make env-dev
make services-up
make test
```

**Data Location**:
```
test_data/
├── test_vault/           # 50 sample markdown files
├── test_emails/          # Sample emails
└── cleaned_emails_sample.tsv
```

---

### 2. Staging Environment ✨ NEW

**File**: `.env.staging` (to be created)

**Purpose**: Pre-production validation with real data subset

**Characteristics**:
- **Data subset**: 100 recent vault files (last 3 months)
- **Data subset**: 10,000 recent emails
- INFO logging
- Production-like settings
- Same Raspberry Pi as production
- Separate collections: `TheMuses_Staging`, `TheLethe_Staging`
- Separate database: `mnemosyne_staging`
- Separate Docker network: `mnemosyne_staging_net`

**Usage**:
```bash
# On Raspberry Pi
make env-staging
docker-compose -f docker-compose.staging.yml up -d
```

**Data Location** (Raspberry Pi):
```
/mnt/sda1/mnemosyne_staging/
├── vault/                # Symlink to latest 100 files
├── emails/               # Latest 10k emails
└── state/
    ├── ingestion_state.db
    └── langgraph_checkpoints.db
```

**Why Staging Always Running?**
- ✅ Test with real data without affecting production
- ✅ Validate migrations before production
- ✅ Test performance on actual hardware (Pi 5)
- ✅ Catch edge cases in real vault structure
- ✅ Validate Telegram bot integration
- ✅ Test backup/restore procedures
- ✅ **Always available** for quick testing
- ✅ **Lower resource usage** than production (subset of data)

---

### 3. Production Environment

**File**: `.env.production`

**Purpose**: Live system with full vault (on-demand use only)

**Characteristics**:
- **Full data**: 512 vault files, 30k-100k emails
- INFO logging
- Optimized settings
- Production polling (5 minutes)
- Large batches (20)
- Collections: `TheMuses`, `TheLethe`, `DiscoveryDB`
- Database: `mnemosyne`
- Docker network: `mnemosyne_net`
- **Runtime**: On-demand only (not always running)

**Usage**:
```bash
# On Raspberry Pi - Start production when needed
make env-prod
docker-compose -f docker-compose.prod.yml up -d

# Stop production when done to free resources
docker-compose -f docker-compose.prod.yml down
```

**Why On-Demand?**
- ✅ **Saves resources** - Staging uses less RAM/CPU
- ✅ **Staging is primary** - Used for most development validation
- ✅ **Production only when needed** - For actual use of full system
- ✅ **Can coexist with staging** - Different ports prevent conflicts

**Data Location** (Raspberry Pi):
```
/mnt/sda1/digital_vault/
├── 02_active/notes/Obsidian/     # 512 files
├── raw_email_archive/             # Full archive
├── cleaned_emails_full.tsv
└── mnemosyne_data/
    ├── ingestion_state.db
    ├── gatekeeper_approvals.db
    ├── semantic_cache.db
    └── langgraph_checkpoints.db
```

---

## 🔀 Branch Strategy

### Git Branching Model

**Model**: **GitHub Flow** (simplified for single developer)

```
main (production)
  ↑
  └─ staging (pre-production)
       ↑
       └─ develop (integration)
            ↑
            ├─ feature/story-000-obsidian-ingestion
            ├─ feature/story-024-email-ingestion
            ├─ bugfix/fix-weaviate-connection
            └─ hotfix/critical-telegram-bug
```

### Branch Descriptions

#### **`main`** - Production Branch
- **Purpose**: Live production code running on Raspberry Pi
- **Protection**:
  - Requires PR approval
  - Must pass all CI checks
  - Requires successful staging deployment
- **Auto-deploys to**: Production environment (manual approval)
- **Naming**: Always `main`

#### **`staging`** - Pre-Production Branch
- **Purpose**: Pre-production validation
- **Protection**:
  - Requires PR approval
  - Must pass all CI checks
- **Auto-deploys to**: Staging environment (automatic)
- **Naming**: Always `staging`

#### **`develop`** - Integration Branch
- **Purpose**: Integration of completed features
- **Protection**: Must pass CI checks
- **Deploys to**: Nothing (local development only)
- **Naming**: Always `develop`

#### **Feature Branches**
- **Purpose**: Individual story implementation
- **Naming**: `feature/<story-number>-<short-description>`
  - `feature/000-obsidian-ingestion`
  - `feature/010-scout-pattern-detection`
- **Lifecycle**:
  1. Branch from `develop`
  2. Implement with TDD
  3. PR to `develop` when complete
  4. Delete after merge

#### **Bugfix Branches**
- **Purpose**: Non-critical bug fixes
- **Naming**: `bugfix/<issue-description>`
  - `bugfix/fix-weaviate-timeout`
- **Lifecycle**: Branch from `develop`, PR to `develop`

#### **Hotfix Branches**
- **Purpose**: Critical production bugs
- **Naming**: `hotfix/<critical-issue>`
  - `hotfix/telegram-bot-crash`
- **Lifecycle**:
  1. Branch from `main`
  2. Fix and test
  3. PR to `main` AND `develop`
  4. Emergency deploy to production

---

## 🚀 Deployment Automation

### Deployment Workflow

```mermaid
graph TD
    A[Develop locally] -->|PR| B[Merge to develop]
    B -->|PR| C[Merge to staging]
    C -->|Auto-deploy| D[Staging Environment]
    D -->|Validation| E{Tests pass?}
    E -->|Yes| F[Manual approval]
    E -->|No| G[Fix issues]
    G -->|PR| C
    F -->|Merge to main| H[Main Branch]
    H -->|Manual trigger| I[Production Deployment]
```

### GitHub Actions Workflows

#### **1. CI/CD Pipeline** (`.github/workflows/ci.yml`)

**Triggers**:
- Push to any branch
- Pull requests to `develop`, `staging`, `main`

**Jobs**:
```yaml
jobs:
  unit-tests:
    # Run on all branches

  integration-tests:
    # Run on all branches

  code-quality:
    # Black, Ruff, mypy

  deploy-staging:
    if: github.ref == 'refs/heads/staging'
    needs: [unit-tests, integration-tests, code-quality]
    # Auto-deploy to staging environment

  notify-production-ready:
    if: github.ref == 'refs/heads/main'
    needs: [unit-tests, integration-tests, code-quality]
    # Notify that production deployment can proceed
```

#### **2. Staging Deployment** (`.github/workflows/deploy-staging.yml`)

**Trigger**: Push to `staging` branch

**Steps**:
```yaml
deploy-staging:
  runs-on: ubuntu-latest
  steps:
    - name: SSH to Raspberry Pi
      uses: appleboy/ssh-action@v1
      with:
        host: ${{ secrets.PI_HOST }}
        username: ${{ secrets.PI_USER }}
        key: ${{ secrets.PI_SSH_KEY }}
        script: |
          cd /home/tgrytnes/projects/Mnemosyne
          git fetch origin
          git checkout staging
          git pull origin staging

          # Switch to staging environment
          make env-staging

          # Rebuild containers
          docker-compose -f docker-compose.staging.yml down
          docker-compose -f docker-compose.staging.yml up -d --build

          # Run health checks
          ./scripts/health_check.sh staging

          # Send Telegram notification
          ./scripts/notify_telegram.sh "Staging deployed: $(git rev-parse --short HEAD)"
```

#### **3. Production Deployment** (`.github/workflows/deploy-production.yml`)

**Trigger**: Manual (`workflow_dispatch`)

**Requires**:
- Successful staging deployment
- Manual approval

**Steps**:
```yaml
deploy-production:
  runs-on: ubuntu-latest
  environment: production  # GitHub environment with approvers

  steps:
    - name: Verify staging success
      run: |
        # Check staging deployment status

    - name: Create backup
      uses: appleboy/ssh-action@v1
      with:
        script: |
          # Backup production database
          ./scripts/backup_production.sh

    - name: Deploy to production
      uses: appleboy/ssh-action@v1
      with:
        script: |
          cd /home/tgrytnes/projects/Mnemosyne
          git fetch origin
          git checkout main
          git pull origin main

          # Switch to production environment
          make env-prod

          # Zero-downtime deployment
          docker-compose -f docker-compose.prod.yml up -d --no-deps --build mnemosyne

          # Health checks
          ./scripts/health_check.sh production

          # Telegram notification
          ./scripts/notify_telegram.sh "Production deployed: $(git rev-parse --short HEAD)"
```

---

## 📋 Deployment Procedures

### Feature Development Workflow

```bash
# 1. Start new feature
git checkout develop
git pull origin develop
git checkout -b feature/000-obsidian-ingestion

# 2. Develop with TDD
make env-dev
make test           # Unit tests
make test-all       # All tests

# 3. Commit and push
git add .
git commit -m "Implement Story 000: Obsidian Vault Ingestion

- Add ObsidianIngestor class
- Implement markdown cleaning
- Add text chunking with overlap
- Store in Weaviate TheMuses collection

🤖 Generated with Claude Code
Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

git push origin feature/000-obsidian-ingestion

# 4. Create PR to develop
gh pr create --base develop --title "Story 000: Obsidian Vault Ingestion"

# 5. Merge after CI passes
gh pr merge --squash

# 6. Delete feature branch
git checkout develop
git branch -d feature/000-obsidian-ingestion
```

### Staging Deployment

```bash
# 1. Create PR from develop to staging
git checkout staging
git pull origin staging
gh pr create --base staging --head develop --title "Deploy Phase 0 stories to staging"

# 2. Review changes
gh pr view

# 3. Merge (triggers auto-deployment)
gh pr merge --squash

# 4. Monitor staging deployment
# GitHub Actions will:
# - Run all tests
# - Deploy to Raspberry Pi staging environment
# - Run health checks
# - Send Telegram notification

# 5. Validate in staging
ssh pi5
cd /home/tgrytnes/projects/Mnemosyne
make env-staging
docker-compose -f docker-compose.staging.yml logs -f

# Test with real data subset
# Check Telegram bot integration
# Verify Weaviate ingestion
```

### Production Deployment

```bash
# 1. Verify staging is healthy
# Check logs, Telegram bot, ingestion metrics

# 2. Create PR from staging to main
git checkout main
git pull origin main
gh pr create --base main --head staging --title "Release: Phase 0 - Ingestion & Hygiene"

# 3. Review production PR
gh pr view

# 4. Merge to main
gh pr merge --squash

# 5. Trigger manual production deployment
gh workflow run deploy-production.yml

# 6. Approve deployment
# GitHub will request approval via environment protection

# 7. Monitor production deployment
# Check health checks
# Monitor Telegram notifications
# Verify full vault ingestion (512 files)

# 8. Tag release
git tag -a v0.1.0 -m "Release: Phase 0 - Ingestion & Hygiene"
git push origin v0.1.0
```

### Hotfix Workflow

```bash
# 1. Critical bug in production
git checkout main
git pull origin main
git checkout -b hotfix/telegram-bot-crash

# 2. Fix and test locally
make env-dev
make test-all

# 3. Deploy to staging first
git push origin hotfix/telegram-bot-crash
gh pr create --base staging --title "Hotfix: Telegram bot crash on startup"
gh pr merge --squash

# Wait for staging validation

# 4. Deploy to production
gh pr create --base main --head staging --title "Hotfix: Telegram bot crash"
gh pr merge --squash
gh workflow run deploy-production.yml

# 5. Backport to develop
git checkout develop
git merge main
git push origin develop

# 6. Delete hotfix branch
git branch -d hotfix/telegram-bot-crash
```

---

## 🔐 Secrets Management

### GitHub Secrets (Repository Settings)

```yaml
# Raspberry Pi SSH
PI_HOST: "192.168.1.100"  # Or hostname
PI_USER: "tgrytnes"
PI_SSH_KEY: "-----BEGIN OPENSSH PRIVATE KEY-----..."

# Production Secrets
TELEGRAM_BOT_TOKEN: "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
TELEGRAM_USER_ID: "123456789"
LINEAR_API_KEY: "lin_api_jgaqAtna0sBPk4Xd3qm0HXED"

# Database Passwords
POSTGRES_PROD_PASSWORD: "secure_production_password"
POSTGRES_STAGING_PASSWORD: "staging_password"
```

### Raspberry Pi Secrets

**Location**: `/home/tgrytnes/.secrets/mnemosyne/`

```
/home/tgrytnes/.secrets/mnemosyne/
├── production/
│   ├── telegram_bot_token
│   ├── postgres_password
│   └── linear_api_key
└── staging/
    ├── telegram_bot_token
    ├── postgres_password
    └── linear_api_key
```

**Loading secrets in Docker Compose**:
```yaml
services:
  mnemosyne:
    environment:
      TELEGRAM_BOT_TOKEN_FILE: /run/secrets/telegram_bot_token
    secrets:
      - telegram_bot_token

secrets:
  telegram_bot_token:
    file: /home/tgrytnes/.secrets/mnemosyne/production/telegram_bot_token
```

---

## 🐳 Docker Compose Files

### `docker-compose.staging.yml`

```yaml
version: '3.8'

networks:
  mnemosyne_staging_net:
    driver: bridge

volumes:
  weaviate_staging_data:
  postgres_staging_data:

services:
  weaviate:
    image: semitechnologies/weaviate:1.27.0
    container_name: mnemosyne_weaviate_staging
    restart: unless-stopped
    networks:
      - mnemosyne_staging_net
    ports:
      - "8082:8080"  # Different port for staging
      - "50052:50051"
    environment:
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
      PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
      DEFAULT_VECTORIZER_MODULE: 'none'
    volumes:
      - weaviate_staging_data:/var/lib/weaviate

  postgres:
    image: postgres:15-alpine
    container_name: mnemosyne_postgres_staging
    restart: unless-stopped
    networks:
      - mnemosyne_staging_net
    ports:
      - "5433:5432"  # Different port for staging
    environment:
      POSTGRES_DB: mnemosyne_staging
      POSTGRES_USER: mnemosyne_user
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
    volumes:
      - postgres_staging_data:/var/lib/postgresql/data
    secrets:
      - postgres_password

  mnemosyne:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: mnemosyne_app_staging
    restart: unless-stopped
    networks:
      - mnemosyne_staging_net
    depends_on:
      - weaviate
      - postgres
    env_file:
      - .env.staging
    volumes:
      - /mnt/sda1/mnemosyne_staging/vault:/data/vault:ro
      - /mnt/sda1/mnemosyne_staging/state:/data/state
    secrets:
      - telegram_bot_token
      - linear_api_key

secrets:
  postgres_password:
    file: /home/tgrytnes/.secrets/mnemosyne/staging/postgres_password
  telegram_bot_token:
    file: /home/tgrytnes/.secrets/mnemosyne/staging/telegram_bot_token
  linear_api_key:
    file: /home/tgrytnes/.secrets/mnemosyne/staging/linear_api_key
```

### `docker-compose.prod.yml`

```yaml
version: '3.8'

networks:
  mnemosyne_net:
    driver: bridge

volumes:
  weaviate_data:
  postgres_data:

services:
  weaviate:
    image: semitechnologies/weaviate:1.27.0
    container_name: mnemosyne_weaviate
    restart: always
    networks:
      - mnemosyne_net
    ports:
      - "8081:8080"
      - "50051:50051"
    environment:
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
      PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
      DEFAULT_VECTORIZER_MODULE: 'none'
    volumes:
      - weaviate_data:/var/lib/weaviate
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/v1/.well-known/ready"]
      interval: 30s
      timeout: 10s
      retries: 3

  postgres:
    image: postgres:15-alpine
    container_name: mnemosyne_postgres
    restart: always
    networks:
      - mnemosyne_net
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: mnemosyne
      POSTGRES_USER: mnemosyne_user
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    secrets:
      - postgres_password
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mnemosyne_user -d mnemosyne"]
      interval: 30s
      timeout: 10s
      retries: 3

  mnemosyne:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        - BUILD_ENV=production
    container_name: mnemosyne_app
    restart: always
    networks:
      - mnemosyne_net
    depends_on:
      weaviate:
        condition: service_healthy
      postgres:
        condition: service_healthy
    env_file:
      - .env.production
    volumes:
      - /mnt/sda1/digital_vault/02_active/notes/Obsidian:/data/vault:ro
      - /mnt/sda1/digital_vault/cleaned_emails_full.tsv:/data/emails.tsv:ro
      - /mnt/sda1/digital_vault/mnemosyne_data:/data/state
    secrets:
      - telegram_bot_token
      - linear_api_key
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 60s
      timeout: 10s
      retries: 3

secrets:
  postgres_password:
    file: /home/tgrytnes/.secrets/mnemosyne/production/postgres_password
  telegram_bot_token:
    file: /home/tgrytnes/.secrets/mnemosyne/production/telegram_bot_token
  linear_api_key:
    file: /home/tgrytnes/.secrets/mnemosyne/production/linear_api_key
```

---

## 📊 Deployment Checklist

### Pre-Deployment (Staging)

- [ ] All tests pass locally
- [ ] Code reviewed (self-review for solo project)
- [ ] Feature branch merged to `develop`
- [ ] PR created from `develop` to `staging`
- [ ] CI/CD pipeline passes
- [ ] Database migrations tested locally

### Staging Validation

- [ ] Auto-deployment completes successfully
- [ ] Health checks pass
- [ ] Weaviate collections created
- [ ] PostgreSQL tables created
- [ ] Ingestion works with real data subset
- [ ] Telegram bot responds
- [ ] No errors in logs (24 hour monitoring)
- [ ] Performance acceptable on Pi 5

### Pre-Deployment (Production)

- [ ] Staging validated for 24+ hours
- [ ] PR created from `staging` to `main`
- [ ] CI/CD pipeline passes
- [ ] Production backup created
- [ ] Rollback plan documented
- [ ] Deployment window scheduled
- [ ] Users notified (yourself via Telegram)

### Production Deployment

- [ ] Manual approval granted
- [ ] Deployment completes successfully
- [ ] Health checks pass
- [ ] All 512 vault files ingested
- [ ] PostgreSQL projects table accessible
- [ ] Telegram bot operational
- [ ] No errors in logs (1 hour monitoring)
- [ ] Git tag created (`v0.X.0`)
- [ ] Linear updated

### Post-Deployment

- [ ] Monitor for 24 hours
- [ ] Check Telegram notifications
- [ ] Verify Scout runs (if Phase 4+)
- [ ] Document any issues
- [ ] Update Linear story status

---

## 🔄 Rollback Procedures

### Staging Rollback

```bash
# SSH to Pi
ssh pi5

# Rollback to previous commit
cd /home/tgrytnes/projects/Mnemosyne
git checkout staging
git reset --hard HEAD~1
git push origin staging --force

# Redeploy
make env-staging
docker-compose -f docker-compose.staging.yml down
docker-compose -f docker-compose.staging.yml up -d

# Restore database from backup
./scripts/restore_backup.sh staging latest
```

### Production Rollback

```bash
# 1. Stop services
ssh pi5
cd /home/tgrytnes/projects/Mnemosyne
docker-compose -f docker-compose.prod.yml down

# 2. Restore database backup
./scripts/restore_backup.sh production <backup-timestamp>

# 3. Rollback code
git checkout main
git reset --hard <previous-good-commit>

# 4. Redeploy
make env-prod
docker-compose -f docker-compose.prod.yml up -d

# 5. Verify
./scripts/health_check.sh production

# 6. Notify
./scripts/notify_telegram.sh "Production rolled back to <commit>"

# 7. Document incident
# Create postmortem document
```

---

## 📝 Summary

### Files to Create

1. **Environment Files**:
   - ✅ `.env.development` (exists)
   - ✅ `.env.testing` (exists)
   - ❌ `.env.staging` (to create)
   - ✅ `.env.production` (exists)

2. **Docker Compose**:
   - ❌ `docker-compose.dev.yml`
   - ❌ `docker-compose.staging.yml`
   - ❌ `docker-compose.prod.yml`

3. **GitHub Workflows**:
   - ✅ `.github/workflows/test.yml` (exists)
   - ❌ `.github/workflows/deploy-staging.yml`
   - ❌ `.github/workflows/deploy-production.yml`

4. **Scripts**:
   - ❌ `scripts/health_check.sh`
   - ❌ `scripts/backup_production.sh`
   - ❌ `scripts/restore_backup.sh`
   - ❌ `scripts/notify_telegram.sh`

5. **Dockerfile**:
   - ❌ `Dockerfile` (application container)

### Branch Setup

```bash
# Create branches
git checkout -b develop
git push origin develop

git checkout -b staging
git push origin staging

# Protect branches on GitHub
gh repo edit --enable-branch-protection
```

---

**Status**: Strategy complete, ready for implementation

**Next Steps**: Create staging environment files and Docker Compose configurations

**Last Updated**: 2025-12-27
