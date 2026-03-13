"""E2E tests: Plugin System & Framework Adapters.

Real subprocess calls testing binex plugins CLI and plugin discovery.
QA Plan v6 — TC-E2E-P01 through TC-E2E-P22.
"""

from __future__ import annotations

import json

from .conftest import extract_run_id, run_binex, write_workflow


# =============================================================================
# Category 1: binex plugins list (TC-E2E-P01 — TC-E2E-P05)
# =============================================================================


def test_e2e_p01_plugins_list_shows_builtins(binex_env):
    """TC-E2E-P01: `binex plugins list` shows 4 built-in adapters."""
    env, _, _ = binex_env

    result = run_binex("plugins", "list", env=env)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    output = result.stdout

    assert "Built-in adapters:" in output
    for prefix in ("local://", "llm://", "human://", "a2a://"):
        assert prefix in output, f"Missing built-in prefix: {prefix}"


def test_e2e_p02_plugins_list_shows_framework_plugins(binex_env):
    """TC-E2E-P02: `binex plugins list` shows framework plugins."""
    env, _, _ = binex_env

    result = run_binex("plugins", "list", env=env)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    output = result.stdout

    # Framework adapters registered as entry points
    for prefix in ("langchain://", "crewai://", "autogen://"):
        assert prefix in output, f"Missing plugin prefix: {prefix}"


def test_e2e_p03_plugins_list_json_valid(binex_env):
    """TC-E2E-P03: `binex plugins list --json` returns valid JSON."""
    env, _, _ = binex_env

    result = run_binex("plugins", "list", "--json", env=env)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    data = json.loads(result.stdout)
    assert "builtins" in data
    assert "plugins" in data
    assert isinstance(data["builtins"], list)
    assert isinstance(data["plugins"], list)
    assert len(data["builtins"]) == 4


def test_e2e_p04_plugins_list_json_fields(binex_env):
    """TC-E2E-P04: JSON plugins contain prefix, package, version fields."""
    env, _, _ = binex_env

    result = run_binex("plugins", "list", "--json", env=env)
    data = json.loads(result.stdout)

    for plugin in data["plugins"]:
        assert "prefix" in plugin, f"Missing 'prefix' in plugin: {plugin}"
        assert "package" in plugin, f"Missing 'package' in plugin: {plugin}"
        assert "version" in plugin, f"Missing 'version' in plugin: {plugin}"


def test_e2e_p05_plugins_list_exit_code(binex_env):
    """TC-E2E-P05: `binex plugins list` exit code is 0."""
    env, _, _ = binex_env

    result = run_binex("plugins", "list", env=env)
    assert result.returncode == 0


# =============================================================================
# Category 2: binex plugins check (TC-E2E-P06 — TC-E2E-P11)
# =============================================================================


def test_e2e_p06_plugins_check_builtins_only(binex_env):
    """TC-E2E-P06: check workflow with only built-ins exits 0."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "builtins", """
name: e2e-builtins
nodes:
  step1:
    agent: "local://echo"
    outputs: [r1]
  step2:
    agent: "local://echo"
    outputs: [r2]
    depends_on: [step1]
""")

    result = run_binex("plugins", "check", str(wf), env=env)
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_e2e_p07_plugins_check_known_plugin(binex_env):
    """TC-E2E-P07: check workflow with known plugin prefix exits 0."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "with-plugin", """
name: e2e-plugin
nodes:
  chain:
    agent: "langchain://mymodule.MyChain"
    outputs: [result]
""")

    result = run_binex("plugins", "check", str(wf), env=env)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "langchain://mymodule.MyChain" in result.stdout


def test_e2e_p08_plugins_check_unknown_prefix(binex_env):
    """TC-E2E-P08: check workflow with unknown prefix exits 1."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "unknown", """
name: e2e-unknown
nodes:
  step:
    agent: "foobar://something"
    outputs: [r1]
""")

    result = run_binex("plugins", "check", str(wf), env=env)
    assert result.returncode == 1
    assert "not found" in result.stdout
    assert "missing" in result.stdout.lower()


def test_e2e_p09_plugins_check_symbols(binex_env):
    """TC-E2E-P09: output shows checkmark/cross for resolved/missing."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "mixed-check", """
name: e2e-mixed-check
nodes:
  good:
    agent: "local://echo"
    outputs: [r1]
  bad:
    agent: "nonexistent://thing"
    outputs: [r2]
""")

    result = run_binex("plugins", "check", str(wf), env=env)
    output = result.stdout
    # ✓ for resolved
    assert "\u2713" in output or "✓" in output
    # ✗ for missing
    assert "\u2717" in output or "✗" in output


def test_e2e_p10_plugins_check_mixed_builtin_plugin(binex_env):
    """TC-E2E-P10: check workflow with mixed built-in + plugin prefixes exits 0."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "mixed", """
name: e2e-mixed
nodes:
  local_step:
    agent: "local://echo"
    outputs: [r1]
  chain_step:
    agent: "langchain://mymod.Chain"
    outputs: [r2]
    depends_on: [local_step]
  crew_step:
    agent: "crewai://mymod.Crew"
    outputs: [r3]
    depends_on: [chain_step]
""")

    result = run_binex("plugins", "check", str(wf), env=env)
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"


def test_e2e_p11_plugins_check_empty_workflow(binex_env):
    """TC-E2E-P11: check workflow with no nodes shows message."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "empty", """
name: e2e-empty
nodes: {}
""")

    result = run_binex("plugins", "check", str(wf), env=env)
    assert result.returncode == 0
    assert "No nodes" in result.stdout or "no nodes" in result.stdout.lower()


# =============================================================================
# Category 3: Plugin Discovery during binex run (TC-E2E-P12 — TC-E2E-P14)
# =============================================================================


def test_e2e_p12_run_local_still_works(binex_env):
    """TC-E2E-P12: binex run with local:// works — plugin system doesn't break existing."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "local-run", """
name: e2e-local
nodes:
  producer:
    agent: "local://echo"
    outputs: [result]
  consumer:
    agent: "local://echo"
    outputs: [final]
    depends_on: [producer]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["status"] == "completed"
    assert data["completed_nodes"] == 2

    # Verify real files
    assert (store_path / "binex.db").exists()


def test_e2e_p13_run_unknown_prefix_error(binex_env):
    """TC-E2E-P13: binex run with unknown prefix gives clear error."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "bad-prefix", """
name: e2e-bad
nodes:
  step:
    agent: "unknown_thing://model"
    outputs: [result]
""")

    result = run_binex("run", str(wf), env=env)
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "No adapter found" in output or "no adapter" in output.lower() or "Error" in output


def test_e2e_p14_run_json_output_contract(binex_env):
    """TC-E2E-P14: binex run --json with local:// produces valid JSON."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "json-contract", """
name: e2e-json-contract
nodes:
  step:
    agent: "local://echo"
    outputs: [out]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert "run_id" in data
    assert "status" in data
    assert data["status"] == "completed"


# =============================================================================
# Category 4: Framework Adapter Discovery (TC-E2E-P15 — TC-E2E-P18)
# =============================================================================


def test_e2e_p15_framework_plugins_in_json(binex_env):
    """TC-E2E-P15: all 3 framework plugins appear in JSON output."""
    env, _, _ = binex_env

    result = run_binex("plugins", "list", "--json", env=env)
    data = json.loads(result.stdout)
    prefixes = {p["prefix"] for p in data["plugins"]}

    assert "langchain" in prefixes, f"Missing langchain, got: {prefixes}"
    assert "crewai" in prefixes, f"Missing crewai, got: {prefixes}"
    assert "autogen" in prefixes, f"Missing autogen, got: {prefixes}"


def test_e2e_p16_check_resolves_langchain(binex_env):
    """TC-E2E-P16: plugins check resolves langchain:// as plugin."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "lc", """
name: e2e-lc
nodes:
  chain:
    agent: "langchain://mymod.MyChain"
    outputs: [r]
""")

    result = run_binex("plugins", "check", str(wf), env=env)
    assert result.returncode == 0
    assert "plugin" in result.stdout.lower()


def test_e2e_p17_check_resolves_crewai(binex_env):
    """TC-E2E-P17: plugins check resolves crewai:// as plugin."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "crew", """
name: e2e-crew
nodes:
  crew:
    agent: "crewai://mymod.MyCrew"
    outputs: [r]
""")

    result = run_binex("plugins", "check", str(wf), env=env)
    assert result.returncode == 0
    assert "plugin" in result.stdout.lower()


def test_e2e_p18_check_resolves_autogen(binex_env):
    """TC-E2E-P18: plugins check resolves autogen:// as plugin."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "ag", """
name: e2e-ag
nodes:
  team:
    agent: "autogen://mymod.MyTeam"
    outputs: [r]
""")

    result = run_binex("plugins", "check", str(wf), env=env)
    assert result.returncode == 0
    assert "plugin" in result.stdout.lower()


# =============================================================================
# Category 5: Error Handling & Edge Cases (TC-E2E-P19 — TC-E2E-P22)
# =============================================================================


def test_e2e_p19_check_nonexistent_file(binex_env):
    """TC-E2E-P19: plugins check on nonexistent file gives error."""
    env, _, _ = binex_env

    result = run_binex("plugins", "check", "/tmp/nonexistent_workflow_42.yaml", env=env)
    assert result.returncode != 0


def test_e2e_p20_check_invalid_yaml(binex_env):
    """TC-E2E-P20: plugins check on invalid YAML gives error."""
    env, _, tmp_path = binex_env

    bad_file = tmp_path / "bad.yaml"
    bad_file.write_text("{{{{not valid yaml: [[[")

    result = run_binex("plugins", "check", str(bad_file), env=env)
    assert result.returncode != 0


def test_e2e_p21_run_local_full_json_contract(binex_env):
    """TC-E2E-P21: binex run with local-only workflow preserves full JSON contract."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "full-contract", """
name: e2e-full-contract
nodes:
  a:
    agent: "local://echo"
    outputs: [r1]
  b:
    agent: "local://echo"
    outputs: [r2]
    depends_on: [a]
  c:
    agent: "local://echo"
    outputs: [r3]
    depends_on: [b]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)

    # Full output contract
    assert data["status"] == "completed"
    assert data["total_nodes"] == 3
    assert data["completed_nodes"] == 3
    assert "run_id" in data
    assert "workflow_name" in data


def test_e2e_p22_plugins_commands_registered(binex_env):
    """TC-E2E-P22: plugins list and check are registered CLI commands."""
    env, _, _ = binex_env

    # binex plugins --help should show list and check
    result = run_binex("plugins", "--help", env=env)
    assert result.returncode == 0
    output = result.stdout
    assert "list" in output
    assert "check" in output
