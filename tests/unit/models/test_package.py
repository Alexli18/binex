"""Smoke tests for binex package."""

import tomllib
from pathlib import Path

import pytest

import binex

_PYPROJECT = Path(__file__).resolve().parents[3] / "pyproject.toml"


def test_version():
    # Check version is a valid semver string, not a specific value
    parts = binex.__version__.split(".")
    assert len(parts) == 3, f"Expected semver, got {binex.__version__}"
    assert all(p.isdigit() for p in parts), f"Non-numeric version parts: {binex.__version__}"


@pytest.mark.skipif(not _PYPROJECT.is_file(), reason="not running from a source checkout")
def test_version_matches_pyproject():
    """`binex.__version__` must track the packaged version.

    It is served to the Web UI and is the version a user sees from `import
    binex`, but nothing derived it from the package metadata — so it silently
    sat at 0.6.5 while 0.7.0 and 0.7.5 shipped. Release bumps have to touch both
    files; this turns forgetting one into a failing test.
    """
    packaged = tomllib.loads(_PYPROJECT.read_text())["project"]["version"]

    assert binex.__version__ == packaged, (
        f"binex.__version__ is {binex.__version__} but pyproject.toml says "
        f"{packaged} — bump both."
    )
