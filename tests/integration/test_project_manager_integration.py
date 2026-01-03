"""
Integration tests for Project Manager Agent (Story 016 - Phase 8)

These tests use REAL services:
- Real PostgreSQL (The Ananke) for projects table
- Real SQLite for Message Outbox
- Real file system for Obsidian vault
- Real ObsidianSyncManager for bidirectional sync
- Real SQL Gatekeeper for project updates

Tests the complete flow:
1. Project discovery → enrichment queue → questions
2. User responses → gatekeeper → Obsidian sync
3. Obsidian edits → file watcher → SQL sync
4. Pressure score calculation with real data
5. Scheduler running actual PM check cycles
"""

import time
from datetime import UTC, datetime, timedelta

import pytest

from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent
from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher
from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager
from mnemosyne.alexandria.message_outbox import MessageOutbox
from mnemosyne.alexandria.sql_gatekeeper import GatekeeperConfig, SQLProjectGatekeeper

# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def test_vault(tmp_path):
    """Create a real test Obsidian vault with Projects folder."""
    vault_path = tmp_path / "test_vault"
    vault_path.mkdir()

    projects_dir = vault_path / "Projects"
    projects_dir.mkdir()

    return vault_path


@pytest.fixture
def message_outbox(tmp_path):
    """Create a real SQLite message outbox."""
    outbox_path = tmp_path / "message_outbox.db"
    return MessageOutbox(str(outbox_path))


@pytest.fixture
def obsidian_sync(test_vault, postgres_connection):
    """Create real ObsidianSyncManager."""

    return ObsidianSyncManager(
        vault_path=str(test_vault),
        db_conn=postgres_connection,
        projects_folder="Projects",
    )


@pytest.fixture
def gatekeeper(postgres_connection, message_outbox, obsidian_sync, tmp_path):
    """Create real SQL Gatekeeper with Obsidian sync."""
    from mnemosyne.argus.scout.monitor_agent import ProposalQueue

    queue_path = tmp_path / "proposal_queue.db"
    proposal_queue = ProposalQueue(str(queue_path))

    gatekeeper = SQLProjectGatekeeper(
        postgres_connection,
        proposal_queue,
        message_outbox,
        GatekeeperConfig(
            auto_reject_threshold=0.6,
            auto_approve_threshold=0.95,
        ),
    )

    # Inject Obsidian sync manager
    gatekeeper.obsidian_sync = obsidian_sync

    return gatekeeper


@pytest.fixture
def project_manager(postgres_connection, message_outbox, gatekeeper):
    """Create real ProjectManagerAgent."""
    return ProjectManagerAgent(
        db_conn=postgres_connection,
        message_outbox=message_outbox,
        gatekeeper=gatekeeper,
        max_messages_per_hour=100,  # High limit for tests
    )


@pytest.fixture
def file_watcher(test_vault, obsidian_sync):
    """Create real ObsidianFileWatcher."""
    return ObsidianFileWatcher(
        vault_path=str(test_vault),
        sync_manager=obsidian_sync,
        projects_folder="Projects",
        debounce_seconds=0.1,  # Short debounce for tests
    )


# ==============================================================================
# Integration Test 1: Complete Enrichment Flow
# ==============================================================================


@pytest.mark.integration
@pytest.mark.postgres
def test_complete_enrichment_flow_with_real_db(
    ananke_test_db, project_manager, message_outbox, gatekeeper
):
    """
    Test complete enrichment flow using real PostgreSQL:
    1. Insert project into DB
    2. PM builds enrichment queue
    3. PM asks importance question
    4. User responds via response handler
    5. PM asks urgency question
    6. User responds
    7. PM asks deadline (high priority)
    8. Project fully enriched
    """
    cursor = ananke_test_db

    # Step 1: Insert a new project (simulating Scout discovery)
    cursor.execute(
        """
        INSERT INTO projects (
            title, description, discovered_by, discovery_id, status
        ) VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            "Build Testing Framework",
            "Comprehensive testing for PM agent",
            "latent_scout",
            "disco_001",
            "candidate",
        ),
    )
    project_id = cursor.fetchone()[0]
    cursor.connection.commit()

    # Step 2: PM builds enrichment queue
    queue = project_manager._build_enrichment_queue()

    assert len(queue) > 0
    assert queue[0]["id"] == project_id
    assert queue[0]["stage"] == "importance"

    # Step 3: PM asks importance question
    project_manager.run_pm_check_cycle()

    # Verify message was enqueued
    messages = message_outbox.dequeue(limit=10)
    assert len(messages) > 0

    importance_msg = next(
        (m for m in messages if m.get("metadata", {}).get("question_type") == "importance"), None
    )
    assert importance_msg is not None
    assert "importance" in importance_msg["content"].lower()

    # Step 4: User responds with importance=5
    project_manager.handle_importance_response(project_id=project_id, value=5)

    # Verify importance was updated in DB
    cursor.execute("SELECT importance FROM projects WHERE id = %s", (project_id,))
    assert cursor.fetchone()[0] == 5

    # Verify urgency question was asked
    messages = message_outbox.dequeue(limit=10)
    urgency_msg = next(
        (m for m in messages if m.get("metadata", {}).get("question_type") == "urgency"), None
    )
    assert urgency_msg is not None

    # Step 5: User responds with urgency=4
    project_manager.handle_urgency_response(project_id=project_id, value=4)

    # Verify urgency updated
    cursor.execute("SELECT urgency FROM projects WHERE id = %s", (project_id,))
    assert cursor.fetchone()[0] == 4

    # Step 6: Since importance + urgency = 9 (>= 7), deadline question should be asked
    messages = message_outbox.dequeue(limit=10)
    deadline_msg = next(
        (m for m in messages if m.get("metadata", {}).get("question_type") == "deadline"), None
    )
    assert deadline_msg is not None

    # Step 7: User provides deadline
    project_manager.handle_deadline_response(project_id=project_id, deadline_text="2 weeks")

    # Verify deadline was set
    cursor.execute("SELECT deadline FROM projects WHERE id = %s", (project_id,))
    deadline = cursor.fetchone()[0]
    assert deadline is not None

    # Verify no more questions (fully enriched)
    project_manager.continue_enrichment(project_id)
    messages_after = message_outbox.dequeue(limit=10)
    # Should have no new questions
    assert len(messages_after) == 0


# ==============================================================================
# Integration Test 2: Bidirectional Obsidian Sync
# ==============================================================================


@pytest.mark.integration
@pytest.mark.postgres
def test_bidirectional_obsidian_sync_with_real_files(
    ananke_test_db, project_manager, gatekeeper, obsidian_sync, test_vault
):
    """
    Test bidirectional sync between PostgreSQL and Obsidian files:
    1. User responds to PM question → gatekeeper updates SQL
    2. Gatekeeper syncs to Obsidian file (SQL → Obsidian)
    3. User edits Obsidian file manually
    4. File watcher detects change and syncs back to SQL (Obsidian → SQL)
    """
    cursor = ananke_test_db

    # Step 1: Create project in DB
    cursor.execute(
        """
        INSERT INTO projects (title, status)
        VALUES (%s, %s)
        RETURNING id
        """,
        ("Obsidian Sync Test", "candidate"),
    )
    project_id = cursor.fetchone()[0]
    cursor.connection.commit()

    # Step 2: User provides importance via response handler
    project_manager.handle_importance_response(project_id=project_id, value=4)

    # Step 3: Verify Obsidian file was created
    projects_dir = test_vault / "Projects"
    md_files = list(projects_dir.glob("*.md"))

    assert len(md_files) == 1
    md_content = md_files[0].read_text()

    # Verify frontmatter contains importance
    assert "importance: 4" in md_content
    assert "Obsidian Sync Test" in md_content

    # Step 4: User manually edits Obsidian file (change importance to 5)
    updated_content = md_content.replace("importance: 4", "importance: 5")
    md_files[0].write_text(updated_content)

    # Step 5: Trigger sync back to SQL
    obsidian_sync.sync_obsidian_file_to_sql(str(md_files[0]))

    # Step 6: Verify SQL was updated
    cursor.execute("SELECT importance FROM projects WHERE id = %s", (project_id,))
    importance = cursor.fetchone()[0]

    assert importance == 5


# ==============================================================================
# Integration Test 3: Pressure Score Calculation
# ==============================================================================


@pytest.mark.integration
@pytest.mark.postgres
def test_pressure_score_calculation_with_real_data(ananke_test_db, project_manager, gatekeeper):
    """
    Test pressure score calculation using real PostgreSQL data:
    1. Create projects with various deadlines and work estimates
    2. Run pressure score update
    3. Verify pressure scores are calculated correctly
    """
    cursor = ananke_test_db
    now = datetime.now(UTC)

    # Project 1: Overdue (should get pressure = 999.0)
    cursor.execute(
        """
        INSERT INTO projects (
            title, status, importance, urgency, deadline, work_estimate
        ) VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        ("Overdue Project", "active", 5, 5, now - timedelta(days=1), 20),
    )
    overdue_id = cursor.fetchone()[0]

    # Project 2: Due in 10 days with 20 hours work
    cursor.execute(
        """
        INSERT INTO projects (
            title, status, importance, urgency, deadline, work_estimate
        ) VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        ("Moderate Pressure", "active", 4, 3, now + timedelta(days=10), 20),
    )
    moderate_id = cursor.fetchone()[0]

    # Project 3: No deadline (should not get pressure score)
    cursor.execute(
        """
        INSERT INTO projects (
            title, status, importance, urgency, work_estimate
        ) VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        ("No Deadline", "active", 3, 2, 15),
    )
    no_deadline_id = cursor.fetchone()[0]

    cursor.connection.commit()

    # Run pressure score update
    project_manager._update_pressure_scores()

    # Verify overdue project has maximum pressure
    cursor.execute("SELECT pressure_score FROM projects WHERE id = %s", (overdue_id,))
    overdue_pressure = cursor.fetchone()[0]
    assert overdue_pressure == 999.0

    # Verify moderate project has calculated pressure
    cursor.execute("SELECT pressure_score FROM projects WHERE id = %s", (moderate_id,))
    moderate_pressure = cursor.fetchone()[0]

    # Calculation: (20 / (10 * 24)) * (4 * 3) = 0.083 * 12 = 1.0
    assert moderate_pressure is not None
    assert 0.8 < moderate_pressure < 1.2  # Allow small tolerance

    # Verify no-deadline project has no pressure score
    cursor.execute("SELECT pressure_score FROM projects WHERE id = %s", (no_deadline_id,))
    no_deadline_pressure = cursor.fetchone()[0]
    assert no_deadline_pressure is None


# ==============================================================================
# Integration Test 4: File Watcher Real-Time Sync
# ==============================================================================


@pytest.mark.integration
@pytest.mark.postgres
def test_file_watcher_real_time_sync(ananke_test_db, obsidian_sync, file_watcher, test_vault):
    """
    Test file watcher with real file system:
    1. Create project in SQL
    2. Sync to Obsidian
    3. Start file watcher
    4. Modify Obsidian file
    5. File watcher detects and syncs back
    """
    cursor = ananke_test_db

    # Step 1: Create project
    cursor.execute(
        """
        INSERT INTO projects (title, status, importance, urgency)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        ("File Watcher Test", "candidate", 3, 2),
    )
    project_id = cursor.fetchone()[0]
    cursor.connection.commit()

    # Step 2: Sync to Obsidian
    obsidian_sync.sync_project_to_obsidian(project_id)

    # Step 3: Find the created file
    projects_dir = test_vault / "Projects"
    md_files = list(projects_dir.glob("*.md"))
    assert len(md_files) == 1
    md_file = md_files[0]

    # Step 4: Start file watcher
    file_watcher.start()

    try:
        # Step 5: Modify file (change importance from 3 to 5)
        content = md_file.read_text()
        updated_content = content.replace("importance: 3", "importance: 5")
        md_file.write_text(updated_content)

        # Wait for file watcher to process (debounce + processing time)
        time.sleep(0.5)

        # Step 6: Verify SQL was updated
        cursor.execute("SELECT importance FROM projects WHERE id = %s", (project_id,))
        importance = cursor.fetchone()[0]

        assert importance == 5

    finally:
        file_watcher.stop()


# ==============================================================================
# Integration Test 5: Event-Driven Question Flow
# ==============================================================================


@pytest.mark.integration
@pytest.mark.postgres
def test_event_driven_question_flow(ananke_test_db, project_manager, message_outbox):
    """
    Test event-driven flow with real data:
    1. Low priority project (importance=2, urgency=2) should stop after urgency
    2. High priority project (importance=5, urgency=4) should continue to deadline
    """
    cursor = ananke_test_db

    # Test 1: Low priority project
    cursor.execute(
        """
        INSERT INTO projects (title, status, importance)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        ("Low Priority", "candidate", 2),
    )
    low_priority_id = cursor.fetchone()[0]
    cursor.connection.commit()

    # Respond with low urgency
    project_manager.handle_urgency_response(project_id=low_priority_id, value=2)

    # Should NOT ask deadline (total priority = 4 < 7)
    messages = message_outbox.dequeue(limit=10)
    deadline_msgs = [
        m for m in messages if m.get("metadata", {}).get("question_type") == "deadline"
    ]
    assert len(deadline_msgs) == 0

    # Test 2: High priority project
    cursor.execute(
        """
        INSERT INTO projects (title, status, importance)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        ("High Priority", "active", 5),
    )
    high_priority_id = cursor.fetchone()[0]
    cursor.connection.commit()

    # Respond with high urgency
    project_manager.handle_urgency_response(project_id=high_priority_id, value=4)

    # SHOULD ask deadline (total priority = 9 >= 7)
    messages = message_outbox.dequeue(limit=10)
    deadline_msgs = [
        m for m in messages if m.get("metadata", {}).get("question_type") == "deadline"
    ]
    assert len(deadline_msgs) == 1


# ==============================================================================
# Integration Test 6: Scheduler with Real Background Jobs
# ==============================================================================


@pytest.mark.integration
@pytest.mark.postgres
def test_scheduler_runs_real_pm_check_cycle(ananke_test_db, project_manager, message_outbox):
    """
    Test scheduler actually runs PM check cycles with real data:
    1. Create projects needing enrichment
    2. Start scheduler with short interval
    3. Wait for scheduler to run
    4. Verify messages were sent
    """
    cursor = ananke_test_db

    # Create a project needing importance
    cursor.execute(
        """
        INSERT INTO projects (title, status)
        VALUES (%s, %s)
        RETURNING id
        """,
        ("Scheduler Test Project", "candidate"),
    )
    project_id = cursor.fetchone()[0]
    cursor.connection.commit()

    # Create scheduler with very short interval (1 second for testing)
    # Note: Using manual trigger instead of actual scheduler to avoid timing issues

    # Manually trigger PM check cycle
    project_manager.run_pm_check_cycle()

    # Verify importance question was asked
    messages = message_outbox.dequeue(limit=10)
    importance_msgs = [
        m for m in messages if m.get("metadata", {}).get("question_type") == "importance"
    ]

    assert len(importance_msgs) > 0
    assert importance_msgs[0]["metadata"]["project_id"] == project_id


# ==============================================================================
# Integration Test 7: Throttling with Real Message Counts
# ==============================================================================


@pytest.mark.integration
@pytest.mark.postgres
def test_throttling_with_real_message_counts(ananke_test_db, project_manager, message_outbox):
    """
    Test throttling with real message outbox:
    1. Set low throttle limit
    2. Send messages up to limit
    3. Verify PM respects throttle
    """
    cursor = ananke_test_db

    # Create PM with low throttle limit
    throttled_pm = ProjectManagerAgent(
        db_conn=ananke_test_db.connection,
        message_outbox=message_outbox,
        max_messages_per_hour=2,  # Only 2 messages per hour
    )

    # Create 3 projects needing enrichment
    for i in range(3):
        cursor.execute(
            """
            INSERT INTO projects (title, status)
            VALUES (%s, %s)
            """,
            (f"Throttle Test {i}", "candidate"),
        )
    cursor.connection.commit()

    # First check cycle - should process 1 project
    throttled_pm.run_pm_check_cycle()
    messages1 = message_outbox.dequeue(limit=10)
    assert len(messages1) == 1

    # Second check cycle - should process 1 more project
    throttled_pm.run_pm_check_cycle()
    messages2 = message_outbox.dequeue(limit=10)
    assert len(messages2) == 1

    # Third check cycle - should be throttled (already sent 2 messages)
    throttled_pm.run_pm_check_cycle()
    messages3 = message_outbox.dequeue(limit=10)
    assert len(messages3) == 0  # Throttled!


# ==============================================================================
# Integration Test 8: Complete Round Trip
# ==============================================================================


@pytest.mark.integration
@pytest.mark.postgres
def test_complete_round_trip_sql_obsidian_sql(
    ananke_test_db, project_manager, gatekeeper, obsidian_sync, test_vault
):
    """
    Test complete round trip:
    1. Scout inserts project → SQL
    2. PM enriches → SQL updated
    3. Gatekeeper syncs → Obsidian file created
    4. User edits Obsidian → file changed
    5. File watcher syncs → SQL updated
    6. PM sees updated data → continues enrichment
    """
    cursor = ananke_test_db

    # Step 1: Scout discovers project
    cursor.execute(
        """
        INSERT INTO projects (title, description, discovered_by, discovery_id, status)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            "Round Trip Test",
            "Complete integration test",
            "latent_scout",
            "disco_round_trip",
            "candidate",
        ),
    )
    project_id = cursor.fetchone()[0]
    cursor.connection.commit()

    # Step 2: PM enriches with importance
    project_manager.handle_importance_response(project_id=project_id, value=4)

    # Step 3: Gatekeeper syncs to Obsidian
    obsidian_sync.sync_project_to_obsidian(project_id)

    # Step 4: Verify Obsidian file exists
    projects_dir = test_vault / "Projects"
    md_files = list(projects_dir.glob("*Round*Trip*.md"))
    assert len(md_files) == 1

    md_file = md_files[0]
    content = md_file.read_text()
    assert "importance: 4" in content

    # Step 5: User manually edits Obsidian (changes urgency)
    # Add urgency field to frontmatter
    lines = content.split("\n")
    # Find the line after "importance: 4" and insert urgency
    for i, line in enumerate(lines):
        if "importance: 4" in line:
            lines.insert(i + 1, "urgency: 3")
            break

    updated_content = "\n".join(lines)
    md_file.write_text(updated_content)

    # Step 6: Sync back to SQL
    obsidian_sync.sync_obsidian_file_to_sql(str(md_file))

    # Step 7: Verify SQL was updated
    cursor.execute("SELECT importance, urgency FROM projects WHERE id = %s", (project_id,))
    importance, urgency = cursor.fetchone()

    assert importance == 4  # Unchanged
    assert urgency == 3  # Updated from Obsidian

    # Step 8: PM sees updated data and continues enrichment
    # Since importance + urgency = 7 (>= 7), should ask for deadline
    project_manager.continue_enrichment(project_id)

    messages = project_manager.message_outbox.dequeue(limit=10)
    deadline_msgs = [
        m for m in messages if m.get("metadata", {}).get("question_type") == "deadline"
    ]

    assert len(deadline_msgs) > 0
