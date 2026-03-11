"""Tests for `binex start` wizard command."""

from __future__ import annotations

import yaml
from click.testing import CliRunner

from binex.cli.dsl_parser import PATTERNS
from binex.cli.start import TEMPLATES, build_start_workflow, start_cmd

# ---------------------------------------------------------------------------
# Phase 1: Template registry
# ---------------------------------------------------------------------------

class TestTemplateRegistry:
    """T002: Verify TEMPLATES dict contents."""

    def test_template_count(self):
        assert len(TEMPLATES) == 4

    def test_template_keys(self):
        assert set(TEMPLATES.keys()) == {
            "research", "content-review", "data-processing", "decision",
        }

    def test_research_template(self):
        t = TEMPLATES["research"]
        assert t["pattern"] == "research"
        assert t["default_name"] == "my-research-pipeline"
        assert "label" in t
        assert "description" in t
        assert "prompt" in t

    def test_content_review_template(self):
        t = TEMPLATES["content-review"]
        assert t["pattern"] == "chain-with-review"
        assert t["default_name"] == "my-content-review"

    def test_data_processing_template(self):
        t = TEMPLATES["data-processing"]
        assert t["pattern"] == "map-reduce"
        assert t["default_name"] == "my-data-pipeline"

    def test_decision_template(self):
        t = TEMPLATES["decision"]
        assert t["pattern"] == "human-approval"
        assert t["default_name"] == "my-decision-pipeline"


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

    def test_all_templates_valid(self):
        for key, tpl in TEMPLATES.items():
            dsl = PATTERNS[tpl["pattern"]]
            result, _ = build_start_workflow(
                dsl=dsl, agent_prefix="llm://", model="gpt-4o",
                user_input=False,
            )
            data = yaml.safe_load(result)
            assert "nodes" in data, f"Template {key} missing nodes"
            assert len(data["nodes"]) > 0, f"Template {key} has no nodes"

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
        # research, user_input=n, ollama, default model, run=n
        result = runner.invoke(start_cmd, input="1\nn\n1\n\ntest-proj\nn\n")
        assert result.exit_code == 0
        assert (tmp_path / "test-proj" / "workflow.yaml").exists()
        data = yaml.safe_load((tmp_path / "test-proj" / "workflow.yaml").read_text())
        # Research pattern nodes
        assert "planner" in data["nodes"]

    def test_custom_dsl(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # custom DSL, user_input=n, ollama, default model, run=n
        result = runner.invoke(start_cmd, input="5\nX -> Y -> Z\nn\n1\n\ncust\nn\n")
        assert result.exit_code == 0
        data = yaml.safe_load((tmp_path / "cust" / "workflow.yaml").read_text())
        assert set(data["nodes"].keys()) == {"X", "Y", "Z"}

    def test_custom_pattern_name(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # custom pattern "linear", user_input=n, ollama, run=n
        result = runner.invoke(start_cmd, input="5\nlinear\nn\n1\n\nlin\nn\n")
        assert result.exit_code == 0
        data = yaml.safe_load((tmp_path / "lin" / "workflow.yaml").read_text())
        # linear = A -> B -> C
        assert set(data["nodes"].keys()) == {"A", "B", "C"}


class TestStartWizardUserInput:
    """T009: User input option in wizard."""

    def test_user_input_yes_adds_node(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(start_cmd, input="1\ny\n1\n\nui-yes\nn\n")
        assert result.exit_code == 0
        data = yaml.safe_load((tmp_path / "ui-yes" / "workflow.yaml").read_text())
        assert "user_input" in data["nodes"]

    def test_user_input_no_skips_node(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(start_cmd, input="1\nn\n1\n\nui-no\nn\n")
        assert result.exit_code == 0
        data = yaml.safe_load((tmp_path / "ui-no" / "workflow.yaml").read_text())
        assert "user_input" not in data["nodes"]


class TestStartWizardProvider:
    """T010: Provider selection in wizard."""

    def test_openai_creates_env_with_key(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # research, user_input=n, openai, api_key=sk-test123, run=n
        result = runner.invoke(start_cmd, input="1\nn\n2\n\nsk-test123\noai\nn\n")
        assert result.exit_code == 0
        env_content = (tmp_path / "oai" / ".env").read_text()
        assert "OPENAI_API_KEY=sk-test123" in env_content

    def test_ollama_no_api_key_prompt(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # template=1, user_input=n, provider=1 (ollama), model=default, name=oll, run=n
        result = runner.invoke(start_cmd, input="1\nn\n1\n\noll\nn\n")
        assert result.exit_code == 0
        env_content = (tmp_path / "oll" / ".env").read_text()
        assert env_content.strip() == ""


class TestStartWizardProjectCreation:
    """T011: Project directory creation."""

    def test_creates_directory_with_all_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(start_cmd, input="1\nn\n1\n\nmy-proj\nn\n")
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
        result = runner.invoke(start_cmd, input="1\nn\n1\n\ntaken\n")
        assert result.exit_code == 1
        assert "already exists and is not empty" in result.output or \
               "already exists and is not empty" in (result.stderr or "")


# ---------------------------------------------------------------------------
# Phase 4: Custom DSL E2E
# ---------------------------------------------------------------------------

class TestStartE2EFlow:
    """T016, T023: End-to-end flows."""

    def test_full_flow_custom_dsl_no_user_input(self, tmp_path, monkeypatch):
        """T016: Custom DSL with OpenAI provider, verify nodes and .env."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # custom=5, dsl="fetcher -> parser -> writer", user_input=n, provider=2 (openai),
        # model=default, api_key=sk-abc, name=e2e-custom, run=n
        result = runner.invoke(
            start_cmd,
            input="5\nfetcher -> parser -> writer\nn\n2\n\nsk-abc\ne2e-custom\nn\n",
        )
        assert result.exit_code == 0
        proj = tmp_path / "e2e-custom"
        data = yaml.safe_load((proj / "workflow.yaml").read_text())
        assert set(data["nodes"].keys()) == {"fetcher", "parser", "writer"}
        assert "OPENAI_API_KEY=sk-abc" in (proj / ".env").read_text()

    def test_full_flow_research_with_user_input(self, tmp_path, monkeypatch):
        """T023: Research template with user input."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(start_cmd, input="1\ny\n1\n\nresearch-ui\nn\n")
        assert result.exit_code == 0
        proj = tmp_path / "research-ui"
        data = yaml.safe_load((proj / "workflow.yaml").read_text())
        assert "user_input" in data["nodes"]
        assert "planner" in data["nodes"]
        assert "user_input" in data["nodes"]["planner"]["depends_on"]

    def test_all_four_templates_generate_valid_projects(self, tmp_path, monkeypatch):
        """T023: All 4 templates produce valid projects."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        for i, key in enumerate(TEMPLATES, 1):
            name = f"proj-{key}"
            result = runner.invoke(start_cmd, input=f"{i}\nn\n1\n\n{name}\nn\n")
            assert result.exit_code == 0, f"Template {key} failed: {result.output}"
            proj = tmp_path / name
            assert proj.is_dir()
            data = yaml.safe_load((proj / "workflow.yaml").read_text())
            assert len(data["nodes"]) > 0, f"Template {key} has no nodes"


# ---------------------------------------------------------------------------
# Phase 5: Run workflow decline path
# ---------------------------------------------------------------------------

class TestStartRunDecline:
    """T019: Verify 'n' to run produces next-steps output."""

    def test_decline_run_shows_next_steps(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(start_cmd, input="1\nn\n1\n\ndecline-run\nn\n")
        assert result.exit_code == 0
        assert "Next steps" in result.output
        assert "binex run workflow.yaml" in result.output
