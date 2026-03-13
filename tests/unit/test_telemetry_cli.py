"""Test that CLI entry point calls init_telemetry."""

from unittest.mock import patch


def test_main_calls_init_telemetry():
    """main() should call init_telemetry() before cli()."""
    with patch("binex.cli.main.init_telemetry") as mock_init, \
         patch("binex.cli.main.cli") as mock_cli:
        from binex.cli.main import main

        try:
            main()
        except SystemExit:
            pass
        mock_init.assert_called_once()
