"""
Shared pytest fixtures for Mnemosyne tests
"""

import os
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
import weaviate

# ============================================================================
# Configuration Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def test_config():
    """Test environment configuration"""
    return {
        "weaviate_http_host": os.getenv("TEST_WEAVIATE_HOST", "localhost"),
        "weaviate_http_port": int(os.getenv("TEST_WEAVIATE_PORT", "8080")),
        "weaviate_grpc_port": int(os.getenv("TEST_WEAVIATE_GRPC_PORT", "50051")),
        "postgres_host": os.getenv("TEST_POSTGRES_HOST", "localhost"),
        "postgres_port": int(os.getenv("TEST_POSTGRES_PORT", "5432")),
        "postgres_db": os.getenv("TEST_POSTGRES_DB", "ananke_test"),
        "postgres_user": os.getenv("TEST_POSTGRES_USER", "postgres"),
        "postgres_password": os.getenv("TEST_POSTGRES_PASSWORD", "test"),
        "ollama_url": os.getenv("TEST_OLLAMA_URL", "http://localhost:11434"),
        "telegram_bot_token": os.getenv("TEST_TELEGRAM_BOT_TOKEN", "test_token"),
    }


# ============================================================================
# File System Fixtures
# ============================================================================


@pytest.fixture
def temp_vault(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary Obsidian vault for testing"""
    vault = tmp_path / "test_vault"
    vault.mkdir()

    # Create sample notes
    (vault / "note1.md").write_text(
        """---
tags: [test, sample]
---
# Test Note 1

This is a test note with [[note2]] link and #tag.

## Section
Some content here.
"""
    )

    (vault / "note2.md").write_text(
        """# Test Note 2

This note is linked from [[note1]].

It contains different content for testing chunking.
"""
    )

    # Create nested structure
    (vault / "subfolder").mkdir()
    (vault / "subfolder" / "nested_note.md").write_text(
        """# Nested Note

This tests directory structure handling.
"""
    )

    yield vault


@pytest.fixture
def temp_shadow_vault(tmp_path: Path) -> Generator[Path, None, None]:
    """Create temporary shadow vault"""
    shadow = tmp_path / "shadow_vault"
    shadow.mkdir()
    yield shadow


@pytest.fixture
def sample_markdown_file(tmp_path: Path) -> Path:
    """Create a sample markdown file for testing"""
    file_path = tmp_path / "sample.md"
    file_path.write_text(
        """---
title: Sample Document
tags: [project, deadline]
created: 2024-01-01
---

# Sample Project Document

This is a sample document for testing.

## Goals
- Complete Phase 1
- Test implementation
- Deploy to production

## Timeline
- Week 1: Planning
- Week 2: Development
- Week 3: Testing

This document has multiple sections for chunking tests.
"""
    )
    return file_path


# ============================================================================
# Weaviate Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def weaviate_client(test_config):
    """
    Create Weaviate client for integration tests
    Requires Weaviate to be running (e.g., via docker-compose)
    """
    try:
        client = weaviate.connect_to_custom(
            http_host=test_config["weaviate_http_host"],
            http_port=test_config["weaviate_http_port"],
            http_secure=False,
            grpc_host=test_config["weaviate_http_host"],
            grpc_port=test_config["weaviate_grpc_port"],
            grpc_secure=False,
        )

        # Verify connection
        if not client.is_ready():
            pytest.skip("Weaviate is not available")

        yield client

        client.close()
    except Exception as e:
        pytest.skip(f"Could not connect to Weaviate: {e}")


@pytest.fixture
def clean_weaviate_collection(weaviate_client):
    """Clean up test collections before and after tests"""
    test_collections = ["TestCollection", "TheMuses", "TheMuses_Test", "TheLethe_Test"]

    # Clean before
    for collection_name in test_collections:
        if weaviate_client.collections.exists(collection_name):
            weaviate_client.collections.delete(collection_name)

    yield

    # Clean after
    for collection_name in test_collections:
        if weaviate_client.collections.exists(collection_name):
            weaviate_client.collections.delete(collection_name)


# ============================================================================
# PostgreSQL Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def postgres_connection(test_config):
    """
    Create PostgreSQL connection for integration tests
    Requires PostgreSQL to be running
    """
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=test_config["postgres_host"],
            port=test_config["postgres_port"],
            database=test_config["postgres_db"],
            user=test_config["postgres_user"],
            password=test_config["postgres_password"],
        )

        yield conn

        conn.close()
    except Exception as e:
        pytest.skip(f"Could not connect to PostgreSQL: {e}")


@pytest.fixture
def ananke_test_db(postgres_connection):
    """Create and clean test database schema"""
    cursor = postgres_connection.cursor()

    # Create projects table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            discovered_by TEXT,
            discovery_id TEXT,
            cluster_ids TEXT[],
            confidence_score FLOAT,
            verified_by_user BOOLEAN DEFAULT FALSE,
            verified_at TIMESTAMP,
            status TEXT DEFAULT 'candidate',
            deadline TIMESTAMP,
            pressure_score FLOAT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """
    )

    # Create gatekeeper audit table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS gatekeeper_audit (
            id SERIAL PRIMARY KEY,
            approval_id TEXT NOT NULL,
            approved BOOLEAN NOT NULL,
            project_id INTEGER REFERENCES projects(id),
            decided_at TIMESTAMP DEFAULT NOW(),
            decided_by TEXT DEFAULT 'telegram_user'
        )
    """
    )

    postgres_connection.commit()

    yield cursor

    # Clean up
    cursor.execute("DROP TABLE IF EXISTS gatekeeper_audit CASCADE")
    cursor.execute("DROP TABLE IF EXISTS projects CASCADE")
    postgres_connection.commit()


# ============================================================================
# Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_ollama_client():
    """Mock Ollama client for unit tests"""
    client = Mock()

    # Mock embedding generation
    client.embeddings.return_value = {"embedding": [0.1] * 1024}  # 1024-dimensional mock vector

    # Mock text generation
    client.generate.return_value = {"response": "Mocked LLM response"}

    return client


@pytest.fixture
def mock_telegram_bot():
    """Mock Telegram bot for unit tests"""
    bot = Mock()
    bot.send_message.return_value = Mock(message_id=1)
    return bot


@pytest.fixture
def mock_discovery():
    """Mock discovery record for testing"""
    return Mock(
        id="test-discovery-123",
        title="Test Project Candidate",
        description="A test project discovered by Scout",
        confidence_score=0.85,
        cluster_ids=["cluster-1", "cluster-2"],
        metadata={
            "sources": ["note1.md", "note2.md"],
            "evidence": ["Goal: Complete Phase 1", "Timeline: Week 1-3"],
        },
        detected_at=datetime(2024, 1, 15, 10, 0, 0),
    )


@pytest.fixture
def mock_cluster():
    """Mock cluster metadata"""
    return Mock(
        id="cluster-1",
        profile=Mock(
            theme_summary="Project management and deadlines",
            tags=["project", "deadline", "tracking"],
            note_count=15,
            centroid_embedding=[0.2] * 1024,
        ),
    )


# ============================================================================
# Data Fixtures
# ============================================================================


@pytest.fixture
def sample_chunks():
    """Sample text chunks for testing"""
    return [
        {
            "text": "This is the first chunk of text for testing embeddings.",
            "source_file": "test1.md",
            "chunk_index": 0,
        },
        {
            "text": "This is the second chunk with different content.",
            "source_file": "test1.md",
            "chunk_index": 1,
        },
        {
            "text": "A third chunk from a different file.",
            "source_file": "test2.md",
            "chunk_index": 0,
        },
    ]


@pytest.fixture
def sample_email():
    """Sample email data for testing"""
    return {
        "subject": "Project Update: Q1 Planning",
        "from": "sender@example.com",
        "to": "recipient@example.com",
        "date": datetime(2024, 1, 15, 9, 30, 0),
        "body": """
Hi team,

I wanted to provide an update on our Q1 planning process.

Key deliverables:
1. Complete architecture review
2. Implement new features
3. Deploy to production

Let's discuss this in our next meeting.

Best regards,
Sender
        """,
    }


# ============================================================================
# Utility Fixtures
# ============================================================================


@pytest.fixture
def freeze_time():
    """Import freezegun for time mocking"""
    from freezegun import freeze_time

    return freeze_time


@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment variables after each test"""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)
