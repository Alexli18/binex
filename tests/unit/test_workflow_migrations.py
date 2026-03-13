"""Tests for workflow migration framework."""

import pytest

from binex.workflow_spec.migrations import (
    CURRENT_VERSION,
    UnsupportedVersionError,
    migrate_workflow,
)


def test_current_version_is_1():
    assert CURRENT_VERSION == 1


def test_migrate_no_version_defaults_to_1():
    """Workflow without version field gets version=1."""
    data = {"name": "test", "nodes": {}}
    result = migrate_workflow(data)
    assert result["version"] == 1


def test_migrate_current_version_is_noop():
    """Workflow at current version passes through unchanged."""
    data = {"version": 1, "name": "test", "nodes": {}}
    result = migrate_workflow(data)
    assert result == data


def test_migrate_future_version_raises():
    """Workflow with version > CURRENT_VERSION raises error."""
    data = {"version": 999, "name": "test", "nodes": {}}
    with pytest.raises(UnsupportedVersionError, match="999"):
        migrate_workflow(data)


def test_migrate_chain_applies_sequentially():
    """Migration chain transforms v1 -> v2 -> ... -> current."""
    from binex.workflow_spec import migrations

    original_migrations = migrations.MIGRATIONS.copy()
    original_version = migrations.CURRENT_VERSION

    try:
        def v1_to_v2(data):
            data["migrated_v2"] = True
            data["version"] = 2
            return data

        migrations.MIGRATIONS[(1, 2)] = v1_to_v2
        migrations.CURRENT_VERSION = 2

        data = {"version": 1, "name": "test", "nodes": {}}
        result = migrate_workflow(data)
        assert result["version"] == 2
        assert result["migrated_v2"] is True
    finally:
        migrations.MIGRATIONS = original_migrations
        migrations.CURRENT_VERSION = original_version
