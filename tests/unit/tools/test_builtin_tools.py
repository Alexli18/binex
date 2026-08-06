"""Tests for built-in tools registry and builtin:// resolver."""

import json
import os

import pytest

from binex.tools import resolve_tools
from binex.tools.builtins import get_builtin, list_builtins


class TestBuiltinResolver:
    def test_builtin_uri_resolves(self):
        tools = resolve_tools(["builtin://calculator"])
        assert len(tools) == 1
        assert tools[0].name == "calculator"
        assert tools[0].callable is not None

    def test_builtin_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown built-in tool"):
            resolve_tools(["builtin://nonexistent"])

    def test_builtin_mixed_with_inline(self):
        tools = resolve_tools([
            "builtin://calculator",
            {"name": "my_tool", "description": "test"},
        ])
        assert len(tools) == 2
        assert tools[0].name == "calculator"
        assert tools[1].name == "my_tool"


class TestBuiltinRegistry:
    def test_get_builtin(self):
        calc = get_builtin("calculator")
        assert calc.name == "calculator"

    def test_get_builtin_unknown(self):
        with pytest.raises(ValueError, match="Unknown built-in tool"):
            get_builtin("nonexistent")

    def test_list_builtins_all_10(self):
        names = list_builtins()
        expected = [
            "calculator", "dice_roll", "fetch_url", "http_request",
            "json_parse", "random_choice", "read_file", "shell_command",
            "web_search", "write_file",
        ]
        assert names == expected


class TestCalculator:
    def test_simple_math(self):
        calc = get_builtin("calculator")
        assert calc.callable(expression="2 + 3") == "5"

    def test_complex_math(self):
        calc = get_builtin("calculator")
        assert calc.callable(expression="2 ** 10") == "1024"

    def test_math_functions(self):
        calc = get_builtin("calculator")
        assert calc.callable(expression="sqrt(16)") == "4.0"

    def test_invalid_expression(self):
        calc = get_builtin("calculator")
        result = calc.callable(expression="import os")
        assert "Error" in result

    def test_no_builtins_access(self):
        calc = get_builtin("calculator")
        result = calc.callable(expression="__import__('os')")
        assert "Error" in result


class TestDiceRoll:
    def test_simple_roll(self):
        dice = get_builtin("dice_roll")
        result = dice.callable(notation="1d6")
        assert "1d6" in result
        assert "=" in result

    def test_with_modifier(self):
        dice = get_builtin("dice_roll")
        result = dice.callable(notation="2d6+3")
        assert "2d6+3" in result
        assert "=" in result

    def test_negative_modifier(self):
        dice = get_builtin("dice_roll")
        result = dice.callable(notation="1d20-2")
        assert "=" in result

    def test_invalid_notation(self):
        dice = get_builtin("dice_roll")
        result = dice.callable(notation="invalid")
        assert "Error" in result

    def test_too_many_dice(self):
        dice = get_builtin("dice_roll")
        result = dice.callable(notation="200d6")
        assert "Error" in result


class TestFetchUrl:
    def test_is_async(self):
        fetch = get_builtin("fetch_url")
        assert fetch.is_async is True
        assert fetch.callable is not None


class TestHttpRequest:
    def test_is_async(self):
        hr = get_builtin("http_request")
        assert hr.is_async is True
        assert hr.callable is not None


class TestWebSearch:
    def test_is_async(self):
        ws = get_builtin("web_search")
        assert ws.is_async is True
        assert ws.callable is not None


class TestReadFile:
    def test_read_relative_path(self, tmp_path):
        (tmp_path / "test.txt").write_text("hello world")
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            read = get_builtin("read_file")
            result = read.callable(path="test.txt")
            assert result == "hello world"
        finally:
            os.chdir(old_cwd)

    def test_read_blocks_dotdot(self):
        read = get_builtin("read_file")
        result = read.callable(path="../etc/passwd")
        assert "Error" in result

    def test_read_blocks_absolute(self):
        read = get_builtin("read_file")
        result = read.callable(path="/etc/passwd")
        assert "Error" in result

    def test_read_nonexistent(self, tmp_path):
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            read = get_builtin("read_file")
            result = read.callable(path="nonexistent.txt")
            assert "Error" in result
        finally:
            os.chdir(old_cwd)


class TestWriteFile:
    def test_write_relative_path(self, tmp_path):
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            write = get_builtin("write_file")
            result = write.callable(path="output.txt", content="hello")
            assert "Written" in result
            assert (tmp_path / "output.txt").read_text() == "hello"
        finally:
            os.chdir(old_cwd)

    def test_write_creates_dirs(self, tmp_path):
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            write = get_builtin("write_file")
            result = write.callable(path="sub/dir/file.txt", content="nested")
            assert "Written" in result
            assert (tmp_path / "sub" / "dir" / "file.txt").read_text() == "nested"
        finally:
            os.chdir(old_cwd)

    def test_write_blocks_absolute(self):
        write = get_builtin("write_file")
        result = write.callable(path="/tmp/evil.txt", content="bad")
        assert "Error" in result

    def test_write_blocks_dotdot(self):
        write = get_builtin("write_file")
        result = write.callable(path="../evil.txt", content="bad")
        assert "Error" in result

    def test_write_blocks_oversized(self, tmp_path):
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            write = get_builtin("write_file")
            big = "x" * (10 * 1024 * 1024 + 1)
            result = write.callable(path="big.txt", content=big)
            assert "Error" in result
            assert "10MB" in result
        finally:
            os.chdir(old_cwd)


class TestShellCommand:
    def test_simple_command(self):
        shell = get_builtin("shell_command")
        result = shell.callable(command="echo hello")
        assert "hello" in result

    def test_command_with_error(self):
        shell = get_builtin("shell_command")
        result = shell.callable(command="ls /nonexistent_dir_12345")
        assert "Exit code" in result or "Error" in result or "No such file" in result

    def test_dangerous_command_blocked_by_default(self):
        shell = get_builtin("shell_command")
        result = shell.callable(command="rm -rf /tmp/whatever")
        assert "not permitted by the shell allowlist" in result
        assert "rm" in result

    def test_absolute_path_cannot_bypass_allowlist(self):
        shell = get_builtin("shell_command")
        result = shell.callable(command="/usr/bin/curl http://example.com")
        assert "not permitted" in result

    def test_empty_command(self):
        shell = get_builtin("shell_command")
        assert shell.callable(command="") == "Error: empty command"

    def test_allowlist_extension_via_env(self, monkeypatch):
        monkeypatch.setenv("BINEX_SHELL_ALLOW", "python3")
        shell = get_builtin("shell_command")
        result = shell.callable(command="python3 -c \"print(6*7)\"")
        assert "42" in result

    def test_allow_all_disables_allowlist(self, monkeypatch):
        monkeypatch.setenv("BINEX_SHELL_ALLOW_ALL", "1")
        shell = get_builtin("shell_command")
        # `true` is not in the default allowlist but runs with ALLOW_ALL.
        result = shell.callable(command="true")
        assert "not permitted" not in result


class TestJsonParse:
    def test_parse_and_extract(self):
        jp = get_builtin("json_parse")
        result = jp.callable(
            json_string='{"name": "Alice", "age": 30, "city": "NYC"}',
            fields="name,age",
        )
        parsed = json.loads(result)
        assert parsed["name"] == "Alice"
        assert parsed["age"] == 30

    def test_parse_full(self):
        jp = get_builtin("json_parse")
        result = jp.callable(json_string='{"key": "value"}', fields="")
        parsed = json.loads(result)
        assert parsed["key"] == "value"

    def test_parse_invalid_json(self):
        jp = get_builtin("json_parse")
        result = jp.callable(json_string="not json", fields="x")
        assert "Error" in result

    def test_missing_field(self):
        jp = get_builtin("json_parse")
        result = jp.callable(json_string='{"a": 1}', fields="b")
        parsed = json.loads(result)
        assert parsed["b"] is None


class TestRandomChoice:
    def test_choice_from_list(self):
        rc = get_builtin("random_choice")
        result = rc.callable(options="red,green,blue")
        assert result in ("red", "green", "blue")

    def test_single_option(self):
        rc = get_builtin("random_choice")
        assert rc.callable(options="only") == "only"

    def test_empty_options(self):
        rc = get_builtin("random_choice")
        result = rc.callable(options="")
        assert "Error" in result

    def test_strips_whitespace(self):
        rc = get_builtin("random_choice")
        result = rc.callable(options=" a , b , c ")
        assert result in ("a", "b", "c")


class TestMcpResolver:
    def test_mcp_uri_without_manager_raises(self):
        with pytest.raises(ValueError, match="mcp_servers"):
            resolve_tools(["mcp://my_server"])

    def test_mcp_uri_with_manager_returns_placeholder(self):
        from binex.models.workflow import McpServerConfig
        from binex.tools.mcp_client import McpClientManager

        mgr = McpClientManager({
            "my_server": McpServerConfig(command="npx", args=["test"]),
        })
        tools = resolve_tools(["mcp://my_server"], mcp_manager=mgr)
        assert len(tools) == 1
        assert tools[0].name == "__mcp_pending_my_server"
        assert hasattr(tools[0], "_mcp_server")
        assert tools[0]._mcp_server == "my_server"

    def test_mcp_mixed_with_builtin(self):
        from binex.models.workflow import McpServerConfig
        from binex.tools.mcp_client import McpClientManager

        mgr = McpClientManager({
            "files": McpServerConfig(command="npx", args=["test"]),
        })
        tools = resolve_tools(
            ["builtin://calculator", "mcp://files"],
            mcp_manager=mgr,
        )
        assert len(tools) == 2
        assert tools[0].name == "calculator"
        assert tools[1].name == "__mcp_pending_files"
