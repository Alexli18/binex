"""Smoke tests for binex package."""

import binex


def test_version():
    assert binex.__version__ == "0.4.0"
