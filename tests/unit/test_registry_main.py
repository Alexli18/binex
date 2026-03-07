"""Tests for registry __main__ entry point."""

from __future__ import annotations

from unittest.mock import patch


def test_main_defaults():
    with patch("binex.registry.__main__.uvicorn") as mock_uvicorn:
        from binex.registry.__main__ import main

        main()
        mock_uvicorn.run.assert_called_once_with(
            "binex.registry.app:app", host="0.0.0.0", port=8000
        )


def test_main_custom_host_port(monkeypatch):
    monkeypatch.setenv("BINEX_REGISTRY_HOST", "127.0.0.1")
    monkeypatch.setenv("BINEX_REGISTRY_PORT", "9000")
    with patch("binex.registry.__main__.uvicorn") as mock_uvicorn:
        from binex.registry.__main__ import main

        main()
        mock_uvicorn.run.assert_called_once_with(
            "binex.registry.app:app", host="127.0.0.1", port=9000
        )
