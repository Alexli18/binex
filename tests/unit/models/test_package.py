"""Smoke tests for binex package."""

import binex


def test_version():
    # Check version is a valid semver string, not a specific value
    parts = binex.__version__.split(".")
    assert len(parts) == 3, f"Expected semver, got {binex.__version__}"
    assert all(p.isdigit() for p in parts), f"Non-numeric version parts: {binex.__version__}"
