"""Tests for `binex start` wizard command."""

from __future__ import annotations

import yaml
from click.testing import CliRunner

from binex.cli.dsl_parser import PATTERNS
from binex.cli.prompt_roles import TEMPLATE_CATEGORIES
from binex.cli.start import build_start_workflow, start_cmd

# ---------------------------------------------------------------------------
# Phase 2: build_start_workflow
# ---------------------------------------------------------------------------

class TestBuildWorkflow:
    """T004: Verify YAML generation from DSL + provider info."""

    def test_research_without_user_input(self):
        dsl = PATTERNS["research"]
        result, _ = build_start_workflow(
            dsl=dsl, agent_prefix="llm://ollama/", model="llama3.2",
            user_input=False,
        )
        data = yaml.safe_load(result)
        assert "nodes" in data
        assert "user_input" not in data["nodes"]
        # All nodes should have the correct agent
        for node in data["nodes"].values():
            assert node["agent"] == "llm://ollama/llama3.2"

    def test_research_with_user_input(self):
        dsl = PATTERNS["research"]
        result, _ = build_start_workflow(
            dsl=dsl, agent_prefix="llm://ollama/", model="llama3.2",
            user_input=True, user_prompt="What to research?",
        )
        data = yaml.safe_load(result)
        assert "user_input" in data["nodes"]
        assert data["nodes"]["user_input"]["agent"] == "human://input"
        assert data["nodes"]["user_input"]["system_prompt"] == "What to research?"
        # Root node(s) should depend on user_input
        # planner is the root node in research pattern
        assert "user_input" in data["nodes"]["planner"]["depends_on"]

    def test_model_with_provider_prefix_dedup(self):
        """Model like 'ollama/gemma3:4b' should not duplicate provider in URI."""
        dsl = PATTERNS["research"]
        result, _ = build_start_workflow(
            dsl=dsl, agent_prefix="llm://ollama/", model="ollama/gemma3:4b",
            user_input=False,
        )
        data = yaml.safe_load(result)
        for node in data["nodes"].values():
            assert node["agent"] == "llm://ollama/gemma3:4b"

    def test_all_general_templates_valid(self):
        for tpl in TEMPLATE_CATEGORIES["general"]:
            result, _ = build_start_workflow(
                dsl=tpl.dsl, agent_prefix="llm://", model="gpt-4o",
                user_input=False,
            )
            data = yaml.safe_load(result)
            assert "nodes" in data, f"Template {tpl.name} missing nodes"
            assert len(data["nodes"]) > 0, f"{tpl.name} has no nodes"

    def test_custom_dsl_with_user_input(self):
        result, _ = build_start_workflow(
            dsl="A -> B -> C", agent_prefix="llm://", model="gpt-4o",
            user_input=True,
        )
        data = yaml.safe_load(result)
        assert "user_input" in data["nodes"]
        assert "user_input" in data["nodes"]["A"]["depends_on"]
        assert data["nodes"]["B"]["depends_on"] == ["A"]

    def test_custom_dsl_without_user_input(self):
        result, _ = build_start_workflow(
            dsl="A -> B, C -> D", agent_prefix="llm://ollama/", model="llama3.2",
            user_input=False,
        )
        data = yaml.safe_load(result)
        assert set(data["nodes"].keys()) == {"A", "B", "C", "D"}
        assert "depends_on" not in data["nodes"]["A"]
        assert data["nodes"]["B"]["depends_on"] == ["A"]
        assert data["nodes"]["C"]["depends_on"] == ["A"]
        assert data["nodes"]["D"]["depends_on"] == ["B", "C"]


# ---------------------------------------------------------------------------
# Phase 3: Wizard command tests
# ---------------------------------------------------------------------------

class TestStartWizardTemplateSelection:
    """T008: Template selection in wizard."""

    def test_default_research_template(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # cat=1(General), tpl=1(Research), ui=n, ollama, model, name, run=n
        result = runner.invoke(start_cmd, input="1\n1\nn\n1\n\ntest-proj\nn\n")
        assert result.exit_code == 0
        assert (tmp_path / "test-proj" / "workflow.yaml").exists()
        data = yaml.safe_load((tmp_path / "test-proj" / "workflow.yaml").read_text())
        # Research pattern nodes
        assert "planner" in data["nodes"]

    def test_custom_dsl(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # custom=c, mode=1(dsl), topology="X -> Y -> Z"
        # node X: type=1(LLM), provider=1(ollama), model=default, prompt=1, back_edge=n, adv=n
        # node Y: same
        # node Z: same
        # save=y, project_name=cust, run=n
        result = runner.invoke(
            start_cmd,
            input=(
                "c\n1\nX -> Y -> Z\n"
                "1\n1\nllama3.2\n1\nn\nn\n"
                "1\n1\nllama3.2\n1\nn\nn\n"
                "1\n1\nllama3.2\n1\nn\nn\n"
                "y\ncust\nn\n"
            ),
        )
        assert result.exit_code == 0
        data = yaml.safe_load((tmp_path / "cust" / "workflow.yaml").read_text())
        assert set(data["nodes"].keys()) == {"X", "Y", "Z"}

    def test_custom_pattern_name(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # custom=c, mode=1(dsl), pattern="linear" (A -> B -> C)
        # node A,B,C: type=1(LLM), provider=1(ollama), model=default, prompt=1, back_edge=n, adv=n
        # save=y, project_name=lin, run=n
        result = runner.invoke(
            start_cmd,
            input=(
                "c\n1\nlinear\n"
                "1\n1\nllama3.2\n1\nn\nn\n"
                "1\n1\nllama3.2\n1\nn\nn\n"
                "1\n1\nllama3.2\n1\nn\nn\n"
                "y\nlin\nn\n"
            ),
        )
        assert result.exit_code == 0
        data = yaml.safe_load((tmp_path / "lin" / "workflow.yaml").read_text())
        # linear = A -> B -> C
        assert set(data["nodes"].keys()) == {"A", "B", "C"}


class TestStartWizardUserInput:
    """T009: User input option in wizard."""

    def test_user_input_yes_adds_node(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # cat=1(General), tpl=1(Research), user_input=y, provider=1, model=default, name, run=n
        result = runner.invoke(start_cmd, input="1\n1\ny\n1\n\nui-yes\nn\n")
        assert result.exit_code == 0
        data = yaml.safe_load((tmp_path / "ui-yes" / "workflow.yaml").read_text())
        assert "user_input" in data["nodes"]

    def test_user_input_no_skips_node(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # cat=1(General), tpl=1(Research), user_input=n, provider=1, model=default, name, run=n
        result = runner.invoke(start_cmd, input="1\n1\nn\n1\n\nui-no\nn\n")
        assert result.exit_code == 0
        data = yaml.safe_load((tmp_path / "ui-no" / "workflow.yaml").read_text())
        assert "user_input" not in data["nodes"]


class TestStartWizardProvider:
    """T010: Provider selection in wizard."""

    def test_openai_creates_env_with_key(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # cat=1, tpl=1, user_input=n, openai=2, model=default, api_key, name, run=n
        result = runner.invoke(start_cmd, input="1\n1\nn\n2\n\nsk-test123\noai\nn\n")
        assert result.exit_code == 0
        env_content = (tmp_path / "oai" / ".env").read_text()
        assert "OPENAI_API_KEY=sk-test123" in env_content

    def test_ollama_no_api_key_prompt(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # cat=1, tpl=1, user_input=n, provider=1(ollama), model=default, name=oll, run=n
        result = runner.invoke(start_cmd, input="1\n1\nn\n1\n\noll\nn\n")
        assert result.exit_code == 0
        env_content = (tmp_path / "oll" / ".env").read_text()
        assert env_content.strip() == ""


class TestStartWizardProjectCreation:
    """T011: Project directory creation."""

    def test_creates_directory_with_all_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(start_cmd, input="1\n1\nn\n1\n\nmy-proj\nn\n")
        assert result.exit_code == 0
        proj = tmp_path / "my-proj"
        assert proj.is_dir()
        assert (proj / "workflow.yaml").is_file()
        assert (proj / ".env").is_file()
        assert (proj / ".gitignore").is_file()
        gitignore = (proj / ".gitignore").read_text()
        assert ".binex/" in gitignore
        assert ".env" in gitignore

    def test_existing_nonempty_dir_aborts(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Create non-empty directory
        existing = tmp_path / "taken"
        existing.mkdir()
        (existing / "file.txt").write_text("occupied")
        runner = CliRunner()
        result = runner.invoke(start_cmd, input="1\n1\nn\n1\n\ntaken\n")
        assert result.exit_code == 1
        assert "already exists and is not empty" in result.output or \
               "already exists and is not empty" in (result.stderr or "")


# ---------------------------------------------------------------------------
# Phase 4: Custom DSL E2E
# ---------------------------------------------------------------------------

class TestStartE2EFlow:
    """T016, T023: End-to-end flows."""

    def test_full_flow_custom_dsl_no_user_input(self, tmp_path, monkeypatch):
        """T016: Custom DSL with per-node config, verify nodes."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # custom=c, mode=1(dsl), topology="fetcher -> parser -> writer"
        # each node: type=1(LLM), provider=1(ollama), model=default, prompt=1, back_edge=n, adv=n
        # save=y, name=e2e-custom, run=n
        result = runner.invoke(
            start_cmd,
            input=(
                "c\n1\nfetcher -> parser -> writer\n"
                "1\n1\nllama3.2\n1\nn\nn\n"
                "1\n1\nllama3.2\n1\nn\nn\n"
                "1\n1\nllama3.2\n1\nn\nn\n"
                "y\ne2e-custom\nn\n"
            ),
        )
        assert result.exit_code == 0
        proj = tmp_path / "e2e-custom"
        data = yaml.safe_load((proj / "workflow.yaml").read_text())
        assert set(data["nodes"].keys()) == {"fetcher", "parser", "writer"}

    def test_full_flow_research_with_user_input(self, tmp_path, monkeypatch):
        """T023: Research template with user input."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # cat=1, tpl=1, user_input=y, provider=1, model=default, name, run=n
        result = runner.invoke(start_cmd, input="1\n1\ny\n1\n\nresearch-ui\nn\n")
        assert result.exit_code == 0
        proj = tmp_path / "research-ui"
        data = yaml.safe_load((proj / "workflow.yaml").read_text())
        assert "user_input" in data["nodes"]
        assert "planner" in data["nodes"]
        assert "user_input" in data["nodes"]["planner"]["depends_on"]

    def test_general_templates_generate_valid_projects(self, tmp_path, monkeypatch):
        """T023: All General category templates produce valid projects."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        templates = TEMPLATE_CATEGORIES["general"]
        for i, tpl in enumerate(templates, 1):
            name = f"proj-{tpl.name}"
            # cat=1(General), tpl=i, user_input=n, provider=1, model=default, name, run=n
            result = runner.invoke(
                start_cmd,
                input=f"1\n{i}\nn\n1\n\n{name}\nn\n",
            )
            assert result.exit_code == 0, (
                f"Template {tpl.name} failed: {result.output}"
            )
            proj = tmp_path / name
            assert proj.is_dir()
            data = yaml.safe_load((proj / "workflow.yaml").read_text())
            assert len(data["nodes"]) > 0, (
                f"Template {tpl.name} has no nodes"
            )


# ---------------------------------------------------------------------------
# Phase 5: Run workflow decline path
# ---------------------------------------------------------------------------

class TestStartRunDecline:
    """T019: Verify 'n' to run produces next-steps output."""

    def test_decline_run_shows_next_steps(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # cat=1, tpl=1, user_input=n, provider=1, model=default, name, run=n
        result = runner.invoke(start_cmd, input="1\n1\nn\n1\n\ndecline-run\nn\n")
        assert result.exit_code == 0
        assert "Next steps" in result.output
        assert "binex run workflow.yaml" in result.output
