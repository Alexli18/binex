"""Workflow schema migration framework.

Migrations are Python functions that transform raw workflow dicts
from one schema version to the next. Applied at load time, in-memory only.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

CURRENT_VERSION = 1

# Keyed by (from_version, to_version) -> migration function
MIGRATIONS: dict[tuple[int, int], Callable[[dict[str, Any]], dict[str, Any]]] = {}


class UnsupportedVersionError(ValueError):
    """Raised when workflow version exceeds CURRENT_VERSION."""


def migrate_workflow(data: dict[str, Any]) -> dict[str, Any]:
    """Apply migration chain to bring workflow data to CURRENT_VERSION.

    Operates on raw dict before Pydantic validation.
    Does NOT modify the source YAML file.
    """
    if "version" not in data:
        logger.warning("No version field found in workflow, defaulting to version 1")
    version = data.get("version", 1)
    data.setdefault("version", version)

    if version > CURRENT_VERSION:
        raise UnsupportedVersionError(
            f"Workflow version {version} is not supported "
            f"(max supported: {CURRENT_VERSION}). "
            f"Please upgrade binex."
        )

    while version < CURRENT_VERSION:
        next_version = version + 1
        key = (version, next_version)
        migration_fn = MIGRATIONS.get(key)
        if migration_fn is None:
            raise ValueError(
                f"No migration found for version {version} -> {next_version}"
            )
        logger.info("Migrating workflow from v%d to v%d", version, next_version)
        data = migration_fn(data)
        version = next_version

    return data
