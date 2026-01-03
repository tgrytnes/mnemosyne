"""
Integration tests for PostgreSQL (The Ananke)
Requires PostgreSQL to be running
"""

from datetime import datetime, timedelta

import pytest


@pytest.mark.integration
@pytest.mark.postgres
class TestProjectsTable:
    """Test projects table operations"""

    def test_insert_project(self, ananke_test_db):
        """Test inserting a project into The Ananke"""
        cursor = ananke_test_db.cursor()

        cursor.execute(
            """
            INSERT INTO projects (
                title,
                description,
                discovered_by,
                confidence_score,
                status
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                "Test Project",
                "A test project for integration testing",
                "latent_scout",
                0.85,
                "candidate",
            ),
        )

        project_id = cursor.fetchone()[0]
        assert project_id is not None

    def test_query_projects_by_status(self, ananke_test_db):
        """Test querying projects by status"""
        cursor = ananke_test_db.cursor()

        # Insert test projects
        statuses = ["active", "candidate", "paused"]
        for status in statuses:
            cursor.execute(
                """
                INSERT INTO projects (title, status)
                VALUES (%s, %s)
                """,
                (f"Project {status}", status),
            )

        cursor.connection.commit()

        # Query active projects
        cursor.execute("SELECT title FROM projects WHERE status = %s", ("active",))
        results = cursor.fetchall()

        assert len(results) == 1
        assert results[0][0] == "Project active"

    def test_update_pressure_score(self, ananke_test_db):
        """Test updating pressure scores"""
        cursor = ananke_test_db.cursor()

        # Insert project
        cursor.execute(
            """
            INSERT INTO projects (title, status, deadline)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            ("Urgent Project", "active", datetime.now() + timedelta(days=3)),
        )

        project_id = cursor.fetchone()[0]
        cursor.connection.commit()

        # Update pressure score
        pressure = 5.2
        cursor.execute(
            """
            UPDATE projects
            SET pressure_score = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (pressure, datetime.now(), project_id),
        )

        cursor.connection.commit()

        # Verify update
        cursor.execute("SELECT pressure_score FROM projects WHERE id = %s", (project_id,))
        result = cursor.fetchone()

        assert result[0] == pressure

    def test_projects_with_approaching_deadlines(self, ananke_test_db):
        """Test querying projects with approaching deadlines"""
        cursor = ananke_test_db.cursor()

        # Insert projects with various deadlines
        now = datetime.now()

        test_projects = [
            ("Due Soon", now + timedelta(days=2)),  # Within 3 days
            ("Due Later", now + timedelta(days=10)),  # Not approaching
            ("Overdue", now - timedelta(days=1)),  # Past due
        ]

        for title, deadline in test_projects:
            cursor.execute(
                """
                INSERT INTO projects (title, status, deadline)
                VALUES (%s, %s, %s)
                """,
                (title, "active", deadline),
            )

        cursor.connection.commit()

        # Query for approaching deadlines (within 3 days)
        cursor.execute(
            """
            SELECT title FROM projects
            WHERE status = 'active'
              AND deadline IS NOT NULL
              AND deadline BETWEEN NOW() AND NOW() + INTERVAL '3 days'
            ORDER BY deadline
            """
        )

        results = cursor.fetchall()
        assert len(results) == 1
        assert results[0][0] == "Due Soon"


@pytest.mark.integration
@pytest.mark.postgres
class TestGatekeeperAudit:
    """Test gatekeeper audit trail"""

    def test_log_approval_decision(self, ananke_test_db):
        """Test logging gatekeeper decisions"""
        cursor = ananke_test_db.cursor()

        # Create a project
        cursor.execute(
            """
            INSERT INTO projects (title, status)
            VALUES (%s, %s)
            RETURNING id
            """,
            ("Approved Project", "candidate"),
        )

        project_id = cursor.fetchone()[0]
        cursor.connection.commit()

        # Log approval
        cursor.execute(
            """
            INSERT INTO gatekeeper_audit (
                approval_id,
                approved,
                project_id,
                decided_at
            ) VALUES (%s, %s, %s, %s)
            """,
            ("test-approval-123", True, project_id, datetime.now()),
        )

        cursor.connection.commit()

        # Verify audit log
        cursor.execute(
            "SELECT approved, project_id FROM gatekeeper_audit WHERE approval_id = %s",
            ("test-approval-123",),
        )

        result = cursor.fetchone()
        assert result[0] is True  # approved
        assert result[1] == project_id

    def test_rejection_logged(self, ananke_test_db):
        """Test rejection is logged without project_id"""
        cursor = ananke_test_db.cursor()

        cursor.execute(
            """
            INSERT INTO gatekeeper_audit (
                approval_id,
                approved,
                decided_at
            ) VALUES (%s, %s, %s)
            """,
            ("rejected-approval-456", False, datetime.now()),
        )

        cursor.connection.commit()

        cursor.execute(
            "SELECT approved, project_id FROM gatekeeper_audit WHERE approval_id = %s",
            ("rejected-approval-456",),
        )

        result = cursor.fetchone()
        assert result[0] is False  # rejected
        assert result[1] is None  # no project created


@pytest.mark.integration
@pytest.mark.postgres
@pytest.mark.slow
def test_concurrent_project_updates(ananke_test_db):
    """Test concurrent updates to projects"""
    import threading

    cursor = ananke_test_db

    # Create project
    cursor.execute(
        """
        INSERT INTO projects (title, status, pressure_score)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        ("Concurrent Test", "active", 0.0),
    )

    project_id = cursor.fetchone()[0]
    cursor.connection.commit()

    def update_pressure(value):
        """Update pressure score"""
        import psycopg2

        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="ananke_test",
            user="postgres",
            password="test",
        )
        cur = conn.cursor()

        cur.execute(
            "UPDATE projects SET pressure_score = %s WHERE id = %s",
            (value, project_id),
        )

        conn.commit()
        conn.close()

    # Run concurrent updates
    threads = []
    for i in range(5):
        t = threading.Thread(target=update_pressure, args=(i * 1.0,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Verify final state (one of the values should win)
    cursor.execute("SELECT pressure_score FROM projects WHERE id = %s", (project_id,))
    result = cursor.fetchone()

    assert result[0] in [0.0, 1.0, 2.0, 3.0, 4.0]
