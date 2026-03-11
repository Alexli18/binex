"""Integration tests for binex start wizard (Phase 8)."""

from __future__ import annotations

import yaml
from click.testing import CliRunner

from binex.cli.start import start_cmd


class TestFullFlowCategoryTemplateSave:
    """T061: Category → template → save → verify workflow.yaml."""

    def test_category_template_save(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # cat=1(General), tpl=1(Research), user_input=n,
        # provider=1(ollama), model=default, name=integ1, run=n
        result = runner.invoke(
            start_cmd, input="1\n1\nn\n1\n\ninteg1\nn\n",
        )
        assert result.exit_code == 0, result.output
        proj = tmp_path / "integ1"
        assert (proj / "workflow.yaml").is_file()
        data = yaml.safe_load((proj / "workflow.yaml").read_text())
        assert "nodes" in data
        assert len(data["nodes"]) > 0


class TestFullFlowEmptyConstructor:
    """T062: Custom → DSL → configure → save."""

    def test_custom_dsl_save(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # c=custom, 1=DSL mode, "A -> B"
        # node A: type=1(LLM), prov=1(ollama), model=llama3.2, prompt=1,
        #         back_edge=n, adv=n
        # node B: same
        # save=y, name=integ2, run=n
        result = runner.invoke(
            start_cmd,
            input=(
                "c\n1\nA -> B\n"
                "1\n1\nllama3.2\n1\nn\nn\n"
                "1\n1\nllama3.2\n1\nn\nn\n"
                "y\ninteg2\nn\n"
            ),
        )
        assert result.exit_code == 0, result.output
        proj = tmp_path / "integ2"
        assert (proj / "workflow.yaml").is_file()
        data = yaml.safe_load((proj / "workflow.yaml").read_text())
        assert set(data["nodes"].keys()) == {"A", "B"}


class TestBackNavigation:
    """T063: Back navigation from template to category."""

    def test_back_from_template_to_category(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # cat=1(General), back=b, cat=2(Development), tpl=1,
        # user_input=n, provider=1, model=default, name=integ3, run=n
        result = runner.invoke(
            start_cmd, input="1\nb\n2\n1\nn\n1\n\ninteg3\nn\n",
        )
        assert result.exit_code == 0, result.output
        # Should have shown categories multiple times
        assert result.output.count("General") >= 2
        proj = tmp_path / "integ3"
        assert (proj / "workflow.yaml").is_file()
