"""Smoke tests for binex package."""

import re
import tomllib
from pathlib import Path

import pytest

import binex

_PYPROJECT = Path(__file__).resolve().parents[3] / "pyproject.toml"

# X.Y.Z, optionally with a PEP 440 pre/post/dev suffix. Release-candidate builds
# are a normal part of publishing (a prerelease goes to TestPyPI first), so the
# check has to accept `0.8.0rc1` — an earlier "three all-digit parts" assertion
# rejected exactly the versions a release dry-run needs.
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?(?:\.post\d+)?(?:\.dev\d+)?$")


def test_version():
    assert _VERSION_RE.match(binex.__version__), (
        f"Not a valid release version: {binex.__version__!r}"
    )


@pytest.mark.parametrize(
    "version", ["0.8.0", "1.0.0", "0.8.0rc1", "0.8.0a2", "0.8.0b1", "1.2.3.post1"],
)
def test_version_pattern_accepts_valid_releases(version: str):
    assert _VERSION_RE.match(version)


@pytest.mark.parametrize(
    "version", ["0.8", "0.8.0.1", "v0.8.0", "0.8.0-rc1", "0.8.x", "", "rc1"],
)
def test_version_pattern_rejects_invalid(version: str):
    assert not _VERSION_RE.match(version)


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
