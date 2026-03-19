"""Unit tests for cao_sessions CRUD in SqliteExecutionStore."""

from __future__ import annotations

import pytest

from binex.stores.backends.sqlite import SqliteExecutionStore


@pytest.fixture()
async def store(tmp_path):
    """In-memory-like SQLite store in temp dir."""
    db_path = str(tmp_path / "test.db")
    s = SqliteExecutionStore(db_path)
    await s.initialize()
    yield s
    await s.close()


class TestCreateCaoSession:
    async def test_create_session(self, store):
        await store.create_cao_session("term_1", "run_a", "node_x")
        sessions = await store.get_cao_sessions()
        assert len(sessions) == 1
        assert sessions[0]["terminal_id"] == "term_1"
        assert sessions[0]["run_id"] == "run_a"
        assert sessions[0]["node_name"] == "node_x"
        assert sessions[0]["status"] == "active"

    async def test_create_multiple_sessions(self, store):
        await store.create_cao_session("term_1", "run_a", "node_x")
        await store.create_cao_session("term_2", "run_a", "node_y")
        sessions = await store.get_cao_sessions()
        assert len(sessions) == 2

    async def test_create_duplicate_terminal_id_fails(self, store):
        await store.create_cao_session("term_1", "run_a", "node_x")
        with pytest.raises(Exception):
            await store.create_cao_session("term_1", "run_b", "node_y")


class TestCompleteCaoSession:
    async def test_complete_marks_session_completed(self, store):
        await store.create_cao_session("term_1", "run_a", "node_x")
        await store.complete_cao_session("term_1")
        sessions = await store.get_cao_sessions()
        assert len(sessions) == 1
        assert sessions[0]["status"] == "completed"

    async def test_complete_nonexistent_session(self, store):
        # Should not raise
        await store.complete_cao_session("nonexistent")


class TestGetCaoSessions:
    async def test_filter_by_status(self, store):
        await store.create_cao_session("term_1", "run_a", "node_x")
        await store.create_cao_session("term_2", "run_a", "node_y")

        # Mark one orphaned
        await store.mark_cao_sessions_orphaned(["term_1"])

        active = await store.get_cao_sessions(status="active")
        assert len(active) == 1
        assert active[0]["terminal_id"] == "term_2"

        orphaned = await store.get_cao_sessions(status="orphaned")
        assert len(orphaned) == 1
        assert orphaned[0]["terminal_id"] == "term_1"

    async def test_get_all_sessions(self, store):
        await store.create_cao_session("term_1", "run_a", "node_x")
        await store.create_cao_session("term_2", "run_a", "node_y")
        sessions = await store.get_cao_sessions()
        assert len(sessions) == 2


class TestOrphanedSessions:
    async def test_get_orphaned_sessions(self, store):
        await store.create_cao_session("term_1", "run_a", "node_x")
        await store.mark_cao_sessions_orphaned(["term_1"])

        orphaned = await store.get_orphaned_cao_sessions()
        assert len(orphaned) == 1
        assert orphaned[0]["status"] == "orphaned"

    async def test_mark_empty_list_does_nothing(self, store):
        await store.create_cao_session("term_1", "run_a", "node_x")
        await store.mark_cao_sessions_orphaned([])
        sessions = await store.get_cao_sessions(status="active")
        assert len(sessions) == 1

    async def test_mark_multiple_orphaned(self, store):
        await store.create_cao_session("term_1", "run_a", "node_x")
        await store.create_cao_session("term_2", "run_a", "node_y")
        await store.create_cao_session("term_3", "run_a", "node_z")

        await store.mark_cao_sessions_orphaned(["term_1", "term_3"])

        orphaned = await store.get_orphaned_cao_sessions()
        assert len(orphaned) == 2
        ids = {s["terminal_id"] for s in orphaned}
        assert ids == {"term_1", "term_3"}

        active = await store.get_cao_sessions(status="active")
        assert len(active) == 1
        assert active[0]["terminal_id"] == "term_2"


class TestDeleteCaoSession:
    async def test_delete_existing(self, store):
        await store.create_cao_session("term_1", "run_a", "node_x")
        deleted = await store.delete_cao_session("term_1")
        assert deleted is True
        sessions = await store.get_cao_sessions()
        assert len(sessions) == 0

    async def test_delete_nonexistent(self, store):
        deleted = await store.delete_cao_session("nonexistent")
        assert deleted is False


class TestAutoOrphanOnStartup:
    """Verify that active sessions become orphaned when store re-initializes."""

    async def test_active_sessions_orphaned_on_reinit(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        store1 = SqliteExecutionStore(db_path)
        await store1.initialize()

        # Create active sessions
        await store1.create_cao_session("term_1", "run_a", "node_x")
        await store1.create_cao_session("term_2", "run_a", "node_y")

        # Simulate crash — close without completing sessions
        await store1.close()

        # Re-open store — initialize() should auto-orphan
        store2 = SqliteExecutionStore(db_path)
        await store2.initialize()

        orphaned = await store2.get_cao_sessions(status="orphaned")
        assert len(orphaned) == 2
        ids = {s["terminal_id"] for s in orphaned}
        assert ids == {"term_1", "term_2"}

        active = await store2.get_cao_sessions(status="active")
        assert len(active) == 0

        await store2.close()

    async def test_completed_sessions_not_orphaned(self, tmp_path):
        """Only active sessions should be orphaned, not already-completed ones."""
        db_path = str(tmp_path / "test.db")
        store1 = SqliteExecutionStore(db_path)
        await store1.initialize()

        await store1.create_cao_session("term_1", "run_a", "node_x")
        await store1.complete_cao_session("term_1")  # properly closed

        await store1.close()

        store2 = SqliteExecutionStore(db_path)
        await store2.initialize()

        # term_1 was completed by complete_cao_session, so not orphaned
        all_sessions = await store2.get_cao_sessions()
        assert len(all_sessions) == 1
        assert all_sessions[0]["status"] == "completed"

        await store2.close()

    async def test_empty_table_no_error(self, tmp_path):
        """Re-init with no active sessions should be a noop."""
        db_path = str(tmp_path / "test.db")
        store1 = SqliteExecutionStore(db_path)
        await store1.initialize()
        await store1.close()

        store2 = SqliteExecutionStore(db_path)
        await store2.initialize()

        all_sessions = await store2.get_cao_sessions()
        assert len(all_sessions) == 0

        await store2.close()


class TestCaoSessionName:
    async def test_create_session_with_session_name(self, tmp_path):
        store = SqliteExecutionStore(str(tmp_path / "test.db"))
        await store.initialize()
        try:
            await store.create_cao_session(
                terminal_id="t1", run_id="r1", node_name="n1",
                session_name="binex-r1",
            )
            sessions = await store.get_cao_sessions()
            assert sessions[0]["session_name"] == "binex-r1"
        finally:
            await store.close()

    async def test_create_session_without_session_name(self, tmp_path):
        store = SqliteExecutionStore(str(tmp_path / "test.db"))
        await store.initialize()
        try:
            await store.create_cao_session(
                terminal_id="t2", run_id="r2", node_name="n2",
            )
            sessions = await store.get_cao_sessions()
            assert sessions[0]["session_name"] is None
        finally:
            await store.close()


class TestCaoSessionsTableCreation:
    async def test_table_exists_after_init(self, store):
        """Verify cao_sessions table was created during initialize()."""
        db = await store._ensure_initialized()
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cao_sessions'"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "cao_sessions"
