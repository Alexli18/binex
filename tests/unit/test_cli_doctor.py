"""Tests for binex doctor CLI command."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from binex.cli.doctor import doctor_cmd, _check_binary, _check_docker_running, _check_http_service, _check_store_backend


class TestCheckBinary:
    def test_binary_found(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/docker"):
            result = _check_binary("docker")
            assert result["status"] == "ok"
            assert result["detail"] == "/usr/bin/docker"

    def test_binary_missing(self) -> None:
        with patch("shutil.which", return_value=None):
            result = _check_binary("docker")
            assert result["status"] == "missing"


class TestCheckDockerRunning:
    def test_docker_running(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = _check_docker_running()
            assert result["status"] == "ok"

    def test_docker_not_running(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            result = _check_docker_running()
            assert result["status"] == "error"

    def test_docker_not_installed(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = _check_docker_running()
            assert result["status"] == "error"


class TestCheckHttpService:
    def test_service_healthy(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("httpx.get", return_value=mock_resp):
            result = _check_http_service("http://localhost:8000/health", "Registry")
            assert result["status"] == "ok"

    def test_service_degraded(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch("httpx.get", return_value=mock_resp):
            result = _check_http_service("http://localhost:8000/health", "Registry")
            assert result["status"] == "degraded"

    def test_service_unreachable(self) -> None:
        import httpx
        with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
            result = _check_http_service("http://localhost:8000/health", "Registry")
            assert result["status"] == "unreachable"

    def test_service_timeout(self) -> None:
        import httpx
        with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
            result = _check_http_service("http://localhost:8000/health", "Registry")
            assert result["status"] == "timeout"


class TestCheckStoreBackend:
    def test_store_exists(self, tmp_path) -> None:
        settings = MagicMock()
        settings.store_path = str(tmp_path)
        with patch("binex.settings.Settings", return_value=settings):
            result = _check_store_backend()
            assert result["status"] == "ok"

    def test_store_not_initialized(self, tmp_path) -> None:
        settings = MagicMock()
        settings.store_path = str(tmp_path / "nonexistent")
        with patch("binex.settings.Settings", return_value=settings):
            result = _check_store_backend()
            assert result["status"] == "not initialized"


class TestDoctorCommand:
    def test_doctor_human_output(self) -> None:
        checks = [
            {"name": "Docker", "status": "ok", "detail": "/usr/bin/docker"},
            {"name": "Registry", "status": "unreachable", "detail": "connection refused"},
        ]
        with patch("binex.cli.doctor.run_checks", return_value=checks):
            runner = CliRunner()
            result = runner.invoke(doctor_cmd)
            assert "Docker" in result.output
            assert "Registry" in result.output
            assert result.exit_code == 1  # has errors

    def test_doctor_json_output(self) -> None:
        checks = [
            {"name": "Docker", "status": "ok", "detail": "/usr/bin/docker"},
        ]
        with patch("binex.cli.doctor.run_checks", return_value=checks):
            runner = CliRunner()
            result = runner.invoke(doctor_cmd, ["--json"])
            parsed = json.loads(result.output)
            assert len(parsed) == 1
            assert parsed[0]["name"] == "Docker"

    def test_doctor_all_healthy(self) -> None:
        checks = [
            {"name": "Docker", "status": "ok", "detail": "running"},
            {"name": "Store", "status": "not initialized", "detail": "will be created"},
        ]
        with patch("binex.cli.doctor.run_checks", return_value=checks):
            runner = CliRunner()
            result = runner.invoke(doctor_cmd)
            assert result.exit_code == 0
            assert "All checks passed" in result.output
